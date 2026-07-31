package com.crosshub.agent.service;

import com.crosshub.config.AgentProfileProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.web.server.ResponseStatusException;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentProfileServiceTest {
    @TempDir
    Path root;

    private AgentProfileService service;

    @BeforeEach
    void setUp() {
        SingleConnectionDataSource dataSource = new SingleConnectionDataSource("jdbc:sqlite::memory:", true);
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        jdbc.execute("""
                CREATE TABLE agent_browser_profile (
                  tenant_id INTEGER NOT NULL,
                  platform TEXT NOT NULL,
                  session_key TEXT NOT NULL,
                  platform_account_id TEXT NOT NULL DEFAULT '',
                  account TEXT NOT NULL DEFAULT '',
                  bundle_rel_path TEXT NOT NULL DEFAULT '',
                  bundle_sha256 TEXT NOT NULL DEFAULT '',
                  bundle_bytes INTEGER NOT NULL DEFAULT 0,
                  session_json TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL,
                  updated_by_agent_id TEXT NOT NULL DEFAULT '',
                  PRIMARY KEY (tenant_id, platform, session_key)
                )
                """);

        AgentProfileProperties properties = new AgentProfileProperties();
        properties.setEnabled(true);
        properties.setRoot(root.toString());
        service = new AgentProfileService(properties, jdbc, new ObjectMapper());
    }

    @Test
    void sanitizeSessionKey_rejectsPathTraversal() {
        assertThrows(IllegalArgumentException.class, () -> service.sanitizeSessionKey("../evil"));
    }

    @Test
    void bundleRelPath_matchesSpec() {
        assertEquals(
                "temu/tenant-5/account-18061740604/bundle.zip",
                service.bundleRelPath("temu", 5, "18061740604")
        );
    }

    @Test
    void putBundle_roundtrip() throws Exception {
        byte[] zip = buildMinimalZip(5, "18061740604");
        AgentProfileService.ProfileRow row = service.putBundle(5, "temu", "18061740604", zip, "", "agent-1");
        assertNotNull(row.bundleSha256());
        assertTrue(row.bundleBytes() > 0);
        byte[] downloaded = service.getBundle(5, "temu", "18061740604", "");
        assertNotNull(downloaded);
        assertEquals(row.bundleSha256(), service.headProfile(5, "temu", "18061740604").bundleSha256());
    }

    @Test
    void putBundle_rejectsMissingManifest() throws Exception {
        byte[] zip = buildZipWithoutManifest();
        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.putBundle(5, "temu", "18061740604", zip, "", "agent-1")
        );
        assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
    }

    @Test
    void updateSessionJsonOnly_skipsMissingRow() {
        service.updateSessionJsonOnly(5, "temu", "missing", "{\"ready\":true}");
        assertTrue(service.find(5, "temu", "missing").isEmpty());
    }

    private static byte[] buildMinimalZip(long tenantId, String sessionKey) throws Exception {
        String sessionJson = "{\"ready\":true,\"mall_id\":\"634\"}";
        String manifest = """
                {
                  "version": 1,
                  "platform": "temu",
                  "tenant_id": %d,
                  "session_key": "%s",
                  "platform_account_id": "",
                  "account": "%s",
                  "files": [],
                  "bundle_sha256": "",
                  "bundle_bytes": 0
                }
                """.formatted(tenantId, sessionKey, sessionKey);

        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(buffer)) {
            writeEntry(zip, ".crosshub-session.json", sessionJson.getBytes(StandardCharsets.UTF_8));
            writeEntry(zip, "manifest.json", manifest.getBytes(StandardCharsets.UTF_8));
        }
        return buffer.toByteArray();
    }

    private static byte[] buildZipWithoutManifest() throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(buffer)) {
            writeEntry(zip, ".crosshub-session.json", "{}".getBytes(StandardCharsets.UTF_8));
        }
        return buffer.toByteArray();
    }

    private static void writeEntry(ZipOutputStream zip, String name, byte[] data) throws Exception {
        ZipEntry entry = new ZipEntry(name);
        zip.putNextEntry(entry);
        zip.write(data);
        zip.closeEntry();
    }
}
