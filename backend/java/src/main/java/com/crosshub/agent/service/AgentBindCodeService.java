package com.crosshub.agent.service;

import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.repository.IntegrationAgentRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.security.SecureRandom;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class AgentBindCodeService {
    public static final Duration BIND_CODE_TTL = Duration.ofMinutes(10);
    public static final long HEARTBEAT_TTL_SECONDS = 90;
    public static final int EXPIRES_IN_SECONDS = 600;
    public static final String DEFAULT_DISPLAY_NAME = "本机助手";
    public static final String INVALID_BIND_CODE_MSG = "绑定码无效或已过期";

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final char[] CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789".toCharArray();
    private static final int CODE_LENGTH = 8;

    private final Clock clock;
    private final IntegrationAgentRepository agentRepository;
    private final ConcurrentHashMap<String, BindEntry> codes = new ConcurrentHashMap<>();
    private final SecureRandom random = new SecureRandom();

    @Autowired
    public AgentBindCodeService(IntegrationAgentRepository agentRepository) {
        this(Clock.systemDefaultZone(), agentRepository);
    }

    public AgentBindCodeService(Clock clock, IntegrationAgentRepository agentRepository) {
        this.clock = clock;
        this.agentRepository = agentRepository;
    }

    public CreateCodeResult createCode(Long userId, Long tenantId) {
        if (userId == null || tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        Instant expiresAt = clock.instant().plus(BIND_CODE_TTL);
        String code = generateUniqueCode();
        codes.put(code, new BindEntry(userId, tenantId, expiresAt));
        return new CreateCodeResult(code, expiresAt);
    }

    @Transactional
    public ConsumeResult consume(String code, String machineFingerprint, String displayName) {
        if (code == null || code.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, INVALID_BIND_CODE_MSG);
        }
        String normalizedCode = code.trim().toUpperCase();
        BindEntry entry = codes.remove(normalizedCode);
        if (entry == null || entry.expiresAt().isBefore(clock.instant())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, INVALID_BIND_CODE_MSG);
        }
        String fingerprint = machineFingerprint == null ? "" : machineFingerprint.trim();
        if (fingerprint.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少 machine_fingerprint");
        }
        String name = (displayName == null || displayName.isBlank()) ? DEFAULT_DISPLAY_NAME : displayName.trim();
        String token = UUID.randomUUID().toString().replace("-", "");
        String now = LocalDateTime.now(clock).format(TS);

        IntegrationAgent agent = agentRepository
                .findByTenantIdAndMachineFingerprint(entry.tenantId(), fingerprint)
                .orElseGet(IntegrationAgent::new);

        boolean isNew = agent.getId() == null || agent.getId().isBlank();
        if (isNew) {
            agent.setId(UUID.randomUUID().toString());
            agent.setCreatedAt(now);
            agent.setLastHeartbeatAt("");
            agent.setZiniaoOnline(0);
        }
        agent.setTenantId(entry.tenantId());
        agent.setBoundUserId(entry.userId());
        agent.setMachineFingerprint(fingerprint);
        agent.setName(name);
        agent.setAgentToken(token);
        agent.setStatus("active");
        agentRepository.save(agent);

        return new ConsumeResult(token, entry.tenantId(), entry.userId());
    }

    /**
     * 桌面端直接绑定：跳过一次性绑定码，用账密认证后直接注册 Agent。
     * 与 {@link #consume} 共用同一套 agent 入库逻辑，仅省去 bind code 校验。
     */
    @Transactional
    public ConsumeResult bindDirect(Long userId, Long tenantId, String machineFingerprint, String displayName) {
        if (userId == null || tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "账号或密码错误");
        }
        String fingerprint = machineFingerprint == null ? "" : machineFingerprint.trim();
        if (fingerprint.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少 machine_fingerprint");
        }
        String name = (displayName == null || displayName.isBlank()) ? DEFAULT_DISPLAY_NAME : displayName.trim();
        String token = UUID.randomUUID().toString().replace("-", "");
        String now = LocalDateTime.now(clock).format(TS);

        IntegrationAgent agent = agentRepository
                .findByTenantIdAndMachineFingerprint(tenantId, fingerprint)
                .orElseGet(IntegrationAgent::new);

        boolean isNew = agent.getId() == null || agent.getId().isBlank();
        if (isNew) {
            agent.setId(UUID.randomUUID().toString());
            agent.setCreatedAt(now);
            agent.setLastHeartbeatAt("");
            agent.setZiniaoOnline(0);
        }
        agent.setTenantId(tenantId);
        agent.setBoundUserId(userId);
        agent.setMachineFingerprint(fingerprint);
        agent.setName(name);
        agent.setAgentToken(token);
        agent.setStatus("active");
        agentRepository.save(agent);

        return new ConsumeResult(token, tenantId, userId);
    }

    public Map<String, Object> statusForTenant(Long tenantId) {
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        List<IntegrationAgent> agents = agentRepository.findByTenantIdOrderByLastHeartbeatAtDesc(tenantId);
        List<Map<String, Object>> rows = new ArrayList<>();
        String recommendedId = null;
        boolean anyOnline = false;
        for (IntegrationAgent agent : agents) {
            boolean online = isHeartbeatFresh(agent);
            if (online) {
                anyOnline = true;
                if (recommendedId == null) {
                    recommendedId = agent.getId();
                }
            }
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", agent.getId());
            row.put("name", agent.getName());
            row.put("machine_fingerprint", agent.getMachineFingerprint());
            row.put("last_heartbeat_at", agent.getLastHeartbeatAt() == null ? "" : agent.getLastHeartbeatAt());
            row.put("online", online);
            rows.add(row);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("online", anyOnline);
        out.put("agents", rows);
        out.put("recommended_agent_id", recommendedId == null ? "" : recommendedId);
        return out;
    }

    /** @deprecated use {@link #statusForTenant(Long)}; kept for transitional callers. */
    @Deprecated
    public Map<String, Object> statusForUser(Long userId) {
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        List<IntegrationAgent> agents = agentRepository.findByBoundUserIdOrderByLastHeartbeatAtDesc(userId);
        Long tenantId = agents.stream()
                .map(IntegrationAgent::getTenantId)
                .filter(id -> id != null)
                .findFirst()
                .orElse(null);
        if (tenantId != null) {
            return statusForTenant(tenantId);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("online", false);
        out.put("agents", List.of());
        out.put("recommended_agent_id", "");
        return out;
    }

    private boolean isHeartbeatFresh(IntegrationAgent agent) {
        if (agent == null || !"active".equalsIgnoreCase(agent.getStatus())) {
            return false;
        }
        LocalDateTime heartbeat = parseTime(agent.getLastHeartbeatAt());
        if (heartbeat == null) {
            return false;
        }
        return !heartbeat.plusSeconds(HEARTBEAT_TTL_SECONDS).isBefore(LocalDateTime.now(clock));
    }

    private LocalDateTime parseTime(String text) {
        if (text == null || text.isBlank()) {
            return null;
        }
        try {
            return LocalDateTime.parse(text, TS);
        } catch (Exception ex) {
            return null;
        }
    }

    private String generateUniqueCode() {
        for (int attempt = 0; attempt < 32; attempt++) {
            String code = randomCode();
            if (!codes.containsKey(code)) {
                return code;
            }
        }
        return UUID.randomUUID().toString().replace("-", "").substring(0, CODE_LENGTH).toUpperCase();
    }

    private String randomCode() {
        char[] buf = new char[CODE_LENGTH];
        for (int i = 0; i < CODE_LENGTH; i++) {
            buf[i] = CODE_ALPHABET[random.nextInt(CODE_ALPHABET.length)];
        }
        return new String(buf);
    }

    private record BindEntry(Long userId, Long tenantId, Instant expiresAt) {}

    public record CreateCodeResult(String code, Instant expiresAt) {}

    public record ConsumeResult(String agentToken, Long tenantId, Long userId) {}
}
