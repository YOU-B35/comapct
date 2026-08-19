package com.crosshub.config.migration;

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
@Order(43)
public class V43Alibaba1688PeerBestsellerQualityMigration {
    private static final Logger log = LoggerFactory.getLogger(V43Alibaba1688PeerBestsellerQualityMigration.class);

    private final JdbcTemplate jdbc;

    public V43Alibaba1688PeerBestsellerQualityMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(alibaba1688_peer_bestseller)");
        boolean exists = columns.stream()
                .anyMatch(col -> "quality_score".equals(String.valueOf(col.get("name"))));
        if (!exists) {
            jdbc.execute("""
                    ALTER TABLE alibaba1688_peer_bestseller
                    ADD COLUMN quality_score TEXT DEFAULT ''
                    """);
            log.info("V43 alibaba1688_peer_bestseller.quality_score migration applied");
        } else {
            log.info("V43 alibaba1688_peer_bestseller.quality_score already present");
        }
    }
}
