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
@Order(44)
public class V44Alibaba1688PeerBestsellerStoreMigration {
    private static final Logger log = LoggerFactory.getLogger(V44Alibaba1688PeerBestsellerStoreMigration.class);

    private final JdbcTemplate jdbc;

    public V44Alibaba1688PeerBestsellerStoreMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(alibaba1688_peer_bestseller)");
        boolean hasStoreId = columns.stream()
                .anyMatch(col -> "store_id".equals(String.valueOf(col.get("name"))));
        // 旧表（V42）建表 SQL 带 UNIQUE(tenant_id, offer_id)；SQLite 会为 TEXT PRIMARY KEY
        // 也生成自动索引，因此不能按索引名判断，只能看建表 SQL 是否含旧唯一约束。
        String createSql = jdbc.queryForObject(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'alibaba1688_peer_bestseller'",
                String.class
        );
        boolean hasLegacyUnique = createSql != null && createSql.contains("UNIQUE (tenant_id, offer_id)");
        if (!hasStoreId || hasLegacyUnique) {
            // 旧表（V42）带有 UNIQUE(tenant_id, offer_id) 自动索引，SQLite 不允许直接删除；
            // 这里重建表：加入 store_id 并换成 (tenant_id, store_id, offer_id) 复合唯一索引。
            jdbc.execute("""
                    CREATE TABLE IF NOT EXISTS alibaba1688_peer_bestseller_v44 (
                      id TEXT PRIMARY KEY,
                      tenant_id INTEGER NOT NULL,
                      store_id TEXT DEFAULT '',
                      offer_id TEXT NOT NULL,
                      shop_name TEXT DEFAULT '',
                      title TEXT DEFAULT '',
                      price TEXT DEFAULT '',
                      sales INTEGER NOT NULL DEFAULT 0,
                      sale_text TEXT DEFAULT '',
                      offer_url TEXT DEFAULT '',
                      image_url TEXT DEFAULT '',
                      quality_score TEXT DEFAULT '',
                      suggestion TEXT DEFAULT '',
                      synced_at TEXT NOT NULL,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    )
                    """);
            jdbc.execute("""
                    INSERT INTO alibaba1688_peer_bestseller_v44 (
                      id, tenant_id, store_id, offer_id, shop_name, title, price, sales, sale_text,
                      offer_url, image_url, quality_score, suggestion, synced_at, created_at, updated_at
                    )
                    SELECT
                      id, tenant_id, 'default',
                      offer_id, shop_name, title, price, sales, sale_text,
                      offer_url, image_url, quality_score, suggestion, synced_at, created_at, updated_at
                    FROM alibaba1688_peer_bestseller
                    """);
            jdbc.execute("""
                    UPDATE alibaba1688_peer_bestseller_v44
                    SET store_id = 'default'
                    WHERE store_id = '' OR store_id IS NULL
                    """);
            jdbc.execute("""
                    UPDATE alibaba1688_peer_bestseller_v44
                    SET store_id = 'default'
                    WHERE store_id = '' OR store_id IS NULL
                    """);
            jdbc.execute("DROP TABLE alibaba1688_peer_bestseller");
            jdbc.execute("ALTER TABLE alibaba1688_peer_bestseller_v44 RENAME TO alibaba1688_peer_bestseller");
            log.info("V44 alibaba1688_peer_bestseller rebuilt with store_id");
        } else {
            log.info("V44 alibaba1688_peer_bestseller.store_id already present");
        }
        // 幂等兜底：空 store_id 的行归属到该租户绑定的店铺（无则 default）
        Integer productTable = jdbc.queryForObject(
                "SELECT COUNT(1) FROM sqlite_master WHERE type = 'table' AND name = 'alibaba1688_product'",
                Integer.class
        );
        if (productTable != null && productTable > 0) {
            jdbc.execute("""
                    UPDATE alibaba1688_peer_bestseller
                    SET store_id = (
                      SELECT COALESCE(p.store_id, 'default')
                      FROM alibaba1688_product p
                      WHERE p.tenant_id = alibaba1688_peer_bestseller.tenant_id
                      LIMIT 1
                    )
                    WHERE store_id = '' OR store_id IS NULL
                    """);
        }
        jdbc.execute("""
                UPDATE alibaba1688_peer_bestseller
                SET store_id = 'default'
                WHERE store_id = '' OR store_id IS NULL
                """);
        jdbc.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uk_a1688_peer_bestseller_offer
                ON alibaba1688_peer_bestseller(tenant_id, store_id, offer_id)
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_a1688_peer_bestseller_store_sales
                ON alibaba1688_peer_bestseller(tenant_id, store_id, sales)
                """);
    }
}
