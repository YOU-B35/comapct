package com.crosshub.agent.service;

import com.crosshub.config.AgentProfileProperties;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

@Service
public class AgentProfileService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};

    private final AgentProfileProperties properties;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public AgentProfileService(AgentProfileProperties properties, JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.properties = properties;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    public record ProfileRow(
            long tenantId,
            String platform,
            String sessionKey,
            String platformAccountId,
            String account,
            String bundleRelPath,
            String bundleSha256,
            long bundleBytes,
            String sessionJson,
            String updatedAt,
            String updatedByAgentId
    ) {}

    public static boolean hasBundle(ProfileRow row) {
        return row != null && row.bundleSha256() != null && !row.bundleSha256().isBlank();
    }

    public void assertEnabled() {
        if (!properties.isEnabled()) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Profile 同步未启用");
        }
    }

    public String sanitizeSessionKey(String sessionKey) {
        if (sessionKey == null || sessionKey.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "session_key 不能为空");
        }
        String trimmed = sessionKey.trim();
        if (trimmed.contains("..") || trimmed.contains("/") || trimmed.contains("\\")) {
            throw new IllegalArgumentException("session_key 非法");
        }
        if (trimmed.length() > 48) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "session_key 过长");
        }
        return trimmed;
    }

    public String sanitizePlatform(String platform) {
        if (platform == null || platform.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "platform 不能为空");
        }
        String normalized = platform.trim().toLowerCase(Locale.ROOT);
        if (!normalized.matches("[a-z0-9_]+")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "platform 非法");
        }
        return normalized;
    }

    public String bundleRelPath(String platform, long tenantId, String sessionKey) {
        String safePlatform = sanitizePlatform(platform);
        String safeKey = sanitizeSessionKey(sessionKey);
        return safePlatform + "/tenant-" + tenantId + "/account-" + safeKey + "/bundle.zip";
    }

    public Optional<ProfileRow> find(long tenantId, String platform, String sessionKey) {
        String safePlatform = sanitizePlatform(platform);
        String safeKey = sanitizeSessionKey(sessionKey);
        List<ProfileRow> rows = jdbc.query(
                """
                SELECT tenant_id, platform, session_key, platform_account_id, account,
                       bundle_rel_path, bundle_sha256, bundle_bytes, session_json,
                       updated_at, updated_by_agent_id
                FROM agent_browser_profile
                WHERE tenant_id = ? AND platform = ? AND session_key = ?
                LIMIT 1
                """,
                (rs, rowNum) -> new ProfileRow(
                        rs.getLong("tenant_id"),
                        rs.getString("platform"),
                        rs.getString("session_key"),
                        rs.getString("platform_account_id"),
                        rs.getString("account"),
                        rs.getString("bundle_rel_path"),
                        rs.getString("bundle_sha256"),
                        rs.getLong("bundle_bytes"),
                        rs.getString("session_json"),
                        rs.getString("updated_at"),
                        rs.getString("updated_by_agent_id")
                ),
                tenantId,
                safePlatform,
                safeKey
        );
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }

    public List<ProfileRow> listByTenant(long tenantId, String platform) {
        String safePlatform = sanitizePlatform(platform);
        return jdbc.query(
                """
                SELECT tenant_id, platform, session_key, platform_account_id, account,
                       bundle_rel_path, bundle_sha256, bundle_bytes, session_json,
                       updated_at, updated_by_agent_id
                FROM agent_browser_profile
                WHERE tenant_id = ? AND platform = ?
                ORDER BY updated_at DESC
                """,
                (rs, rowNum) -> new ProfileRow(
                        rs.getLong("tenant_id"),
                        rs.getString("platform"),
                        rs.getString("session_key"),
                        rs.getString("platform_account_id"),
                        rs.getString("account"),
                        rs.getString("bundle_rel_path"),
                        rs.getString("bundle_sha256"),
                        rs.getLong("bundle_bytes"),
                        rs.getString("session_json"),
                        rs.getString("updated_at"),
                        rs.getString("updated_by_agent_id")
                ),
                tenantId,
                safePlatform
        );
    }

    public ProfileRow putBundle(
            long tenantId,
            String platform,
            String sessionKey,
            byte[] zipBytes,
            String ifMatch,
            String agentId
    ) {
        assertEnabled();
        if (zipBytes == null || zipBytes.length == 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "空 bundle");
        }
        if (zipBytes.length > properties.getMaxBytes()) {
            throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE, "bundle 超过大小限制");
        }

        String safePlatform = sanitizePlatform(platform);
        String safeKey = sanitizeSessionKey(sessionKey);
        String relPath = bundleRelPath(safePlatform, tenantId, safeKey);

        Optional<ProfileRow> existing = find(tenantId, safePlatform, safeKey);
        if (ifMatch != null && !ifMatch.isBlank()) {
            String currentSha = existing.map(ProfileRow::bundleSha256).orElse("");
            if (!ifMatch.trim().equalsIgnoreCase(currentSha)) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "If-Match 与服务器 sha 不一致");
            }
        }

        String zipSha = sha256Hex(zipBytes);
        validateZipEntries(zipBytes);
        Map<String, Object> manifest = readAndValidateManifest(zipBytes, tenantId, safePlatform, safeKey, zipSha);

        String platformAccountId = stringValue(manifest.get("platform_account_id"));
        String account = stringValue(manifest.get("account"));
        String sessionJson = readSessionJsonFromZip(zipBytes);

        Path bundlePath = properties.rootPath().resolve(relPath);
        Path bundleDir = bundlePath.getParent();
        Path tmpZip = bundleDir.resolve("bundle.zip.tmp");
        try {
            Files.createDirectories(bundleDir);
            Files.write(tmpZip, zipBytes);
            Files.move(tmpZip, bundlePath, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            Files.writeString(
                    bundleDir.resolve("manifest.json"),
                    objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(manifest),
                    StandardCharsets.UTF_8
            );
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "写入 bundle 失败", ex);
        } finally {
            try {
                Files.deleteIfExists(tmpZip);
            } catch (IOException ignored) {
                // ignore
            }
        }

        String updatedAt = now();
        String agent = agentId == null ? "" : agentId.trim();
        jdbc.update(
                """
                INSERT INTO agent_browser_profile (
                  tenant_id, platform, session_key, platform_account_id, account,
                  bundle_rel_path, bundle_sha256, bundle_bytes, session_json,
                  updated_at, updated_by_agent_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, platform, session_key) DO UPDATE SET
                  platform_account_id = excluded.platform_account_id,
                  account = excluded.account,
                  bundle_rel_path = excluded.bundle_rel_path,
                  bundle_sha256 = excluded.bundle_sha256,
                  bundle_bytes = excluded.bundle_bytes,
                  session_json = excluded.session_json,
                  updated_at = excluded.updated_at,
                  updated_by_agent_id = excluded.updated_by_agent_id
                """,
                tenantId,
                safePlatform,
                safeKey,
                platformAccountId,
                account,
                relPath,
                zipSha,
                zipBytes.length,
                sessionJson,
                updatedAt,
                agent
        );

        return find(tenantId, safePlatform, safeKey)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "写入后读取失败"));
    }

    public byte[] getBundle(long tenantId, String platform, String sessionKey, String ifNoneMatch) {
        assertEnabled();
        ProfileRow row = find(tenantId, platform, sessionKey)
                .filter(AgentProfileService::hasBundle)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Profile 不存在"));

        if (ifNoneMatch != null && !ifNoneMatch.isBlank()
                && ifNoneMatch.trim().equalsIgnoreCase(row.bundleSha256())) {
            return null;
        }

        Path bundlePath = properties.rootPath().resolve(row.bundleRelPath());
        if (!Files.isRegularFile(bundlePath)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "bundle 文件缺失");
        }
        try {
            return Files.readAllBytes(bundlePath);
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "读取 bundle 失败", ex);
        }
    }

    public ProfileRow headProfile(long tenantId, String platform, String sessionKey) {
        assertEnabled();
        return find(tenantId, platform, sessionKey)
                .filter(AgentProfileService::hasBundle)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Profile 不存在"));
    }

    public void updateSessionJsonOnly(long tenantId, String platform, String sessionKey, String sessionJson) {
        if (!properties.isEnabled()) {
            return;
        }
        Optional<ProfileRow> existing = find(tenantId, platform, sessionKey);
        if (existing.isEmpty()) {
            return;
        }
        jdbc.update(
                """
                UPDATE agent_browser_profile
                SET session_json = ?, updated_at = ?
                WHERE tenant_id = ? AND platform = ? AND session_key = ?
                """,
                sessionJson == null || sessionJson.isBlank() ? "{}" : sessionJson,
                now(),
                tenantId,
                sanitizePlatform(platform),
                sanitizeSessionKey(sessionKey)
        );
    }

    public Map<String, Object> toDto(ProfileRow row) {
        Map<String, Object> dto = new LinkedHashMap<>();
        dto.put("tenant_id", row.tenantId());
        dto.put("platform", row.platform());
        dto.put("session_key", row.sessionKey());
        dto.put("platform_account_id", row.platformAccountId());
        dto.put("account", row.account());
        dto.put("bundle_sha256", row.bundleSha256());
        dto.put("bundle_bytes", row.bundleBytes());
        dto.put("updated_at", row.updatedAt());
        try {
            dto.put("session_json", objectMapper.readValue(
                    row.sessionJson() == null || row.sessionJson().isBlank() ? "{}" : row.sessionJson(),
                    MAP_TYPE
            ));
        } catch (Exception ex) {
            dto.put("session_json", Map.of());
        }
        return dto;
    }

    private Map<String, Object> readAndValidateManifest(
            byte[] zipBytes,
            long tenantId,
            String platform,
            String sessionKey,
            String zipSha
    ) {
        Map<String, Object> manifest = extractManifest(zipBytes);
        if (manifest.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少 manifest.json");
        }
        long manifestTenant = longValue(manifest.get("tenant_id"), -1);
        if (manifestTenant != tenantId) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "manifest tenant_id 不匹配");
        }
        String manifestPlatform = stringValue(manifest.get("platform")).toLowerCase(Locale.ROOT);
        if (!platform.equals(manifestPlatform)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "manifest platform 不匹配");
        }
        if (!sessionKey.equals(stringValue(manifest.get("session_key")))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "manifest session_key 不匹配");
        }
        String manifestSha = stringValue(manifest.get("bundle_sha256"));
        if (!manifestSha.isBlank() && !manifestSha.equalsIgnoreCase(zipSha)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "manifest bundle_sha256 不匹配");
        }
        manifest.put("bundle_sha256", zipSha);
        manifest.putIfAbsent("bundle_bytes", zipBytes.length);
        return manifest;
    }

    private Map<String, Object> extractManifest(byte[] zipBytes) {
        try (ZipInputStream zis = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                if (entry.isDirectory()) {
                    continue;
                }
                String name = normalizeZipEntry(entry.getName());
                if (!"manifest.json".equals(name)) {
                    continue;
                }
                byte[] data = zis.readAllBytes();
                return objectMapper.readValue(data, MAP_TYPE);
            }
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "zip 损坏", ex);
        }
        return Map.of();
    }

    private String readSessionJsonFromZip(byte[] zipBytes) {
        try (ZipInputStream zis = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                if (entry.isDirectory()) {
                    continue;
                }
                String name = normalizeZipEntry(entry.getName());
                if (!".crosshub-session.json".equals(name)) {
                    continue;
                }
                return new String(zis.readAllBytes(), StandardCharsets.UTF_8);
            }
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "读取 session 缓存失败", ex);
        }
        return "{}";
    }

    static void validateZipEntries(byte[] zipBytes) {
        List<String> names = new ArrayList<>();
        try (ZipInputStream zis = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                if (entry.isDirectory()) {
                    continue;
                }
                String normalized = normalizeZipEntry(entry.getName());
                if (normalized.contains("..") || normalized.startsWith("/") || normalized.startsWith("\\")) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "zip slip 检测失败");
                }
                names.add(normalized);
            }
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "zip 损坏", ex);
        }
        if (names.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "空 zip");
        }
    }

    private static String normalizeZipEntry(String name) {
        return name.replace('\\', '/').trim();
    }

    private static String sha256Hex(byte[] data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(data));
        } catch (Exception ex) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "sha256 计算失败", ex);
        }
    }

    private static String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static long longValue(Object value, long defaultValue) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        try {
            return Long.parseLong(stringValue(value));
        } catch (NumberFormatException ex) {
            return defaultValue;
        }
    }

    private static String now() {
        return LocalDateTime.now().format(TS);
    }
}
