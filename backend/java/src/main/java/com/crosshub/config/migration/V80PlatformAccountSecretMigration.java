package com.crosshub.config.migration;

import com.crosshub.security.SecretValueService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Component
@Order(80)
public class V80PlatformAccountSecretMigration {
    private static final Logger log = LoggerFactory.getLogger(V80PlatformAccountSecretMigration.class);

    private final JdbcTemplate jdbc;
    private final SecretValueService secretValueService;

    public V80PlatformAccountSecretMigration(JdbcTemplate jdbc, SecretValueService secretValueService) {
        this.jdbc = jdbc;
        this.secretValueService = secretValueService;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        if (!tableExists("platform_account")) {
            return;
        }
        List<Map<String, Object>> rows = jdbc.queryForList("SELECT id, password FROM platform_account");
        int upgraded = 0;
        for (Map<String, Object> row : rows) {
            Object id = row.get("id");
            String password = row.get("password") == null ? "" : String.valueOf(row.get("password"));
            if (!password.isBlank() && !secretValueService.isEncrypted(password)) {
                jdbc.update(
                        "UPDATE platform_account SET password = ? WHERE id = ?",
                        secretValueService.encrypt(password),
                        id
                );
                upgraded += 1;
            }
        }
        if (upgraded > 0) {
            log.info("Encrypted {} legacy platform account secrets", upgraded);
        }
    }

    private boolean tableExists(String table) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(1) FROM sqlite_master WHERE type = 'table' AND name = ?",
                Integer.class,
                table
        );
        return count != null && count > 0;
    }
}
