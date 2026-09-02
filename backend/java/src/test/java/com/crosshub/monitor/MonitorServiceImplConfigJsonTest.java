package com.crosshub.monitor;

import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.monitor.service.MonitorService;
import com.crosshub.monitor.service.impl.MonitorAgentTaskEnqueuer;
import com.crosshub.monitor.service.impl.MonitorServiceImpl;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class MonitorServiceImplConfigJsonTest {

    private JdbcTemplate jdbc;
    private MonitorService service;

    @BeforeEach
    void setUp() {
        SingleConnectionDataSource dataSource = new SingleConnectionDataSource("jdbc:sqlite::memory:", true);
        jdbc = new JdbcTemplate(dataSource);
        jdbc.execute("""
                CREATE TABLE monitor_target (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  platform TEXT NOT NULL,
                  target_type TEXT NOT NULL,
                  label TEXT NOT NULL,
                  target_url TEXT NOT NULL,
                  host TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'active',
                  crawl_strategy TEXT NOT NULL DEFAULT '',
                  freshness_minutes INTEGER NOT NULL DEFAULT 1440,
                  config_json TEXT NOT NULL DEFAULT '',
                  latest_snapshot_id TEXT,
                  latest_snapshot_at TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE monitor_schedule (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  target_id TEXT NOT NULL,
                  enabled INTEGER NOT NULL DEFAULT 1,
                  schedule_type TEXT NOT NULL DEFAULT 'interval',
                  cron_expr TEXT NOT NULL DEFAULT '',
                  interval_minutes INTEGER NOT NULL DEFAULT 1440,
                  next_run_at TEXT,
                  last_run_at TEXT,
                  max_products INTEGER NOT NULL DEFAULT 100,
                  retry_limit INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """);

        DataScopeService dataScopeService = mock(DataScopeService.class);
        when(dataScopeService.requireTenantId()).thenReturn(7L);
        service = new MonitorServiceImpl(
                jdbc,
                dataScopeService,
                mock(AuthContext.class),
                new CrawlerProperties(),
                mock(TenantCrawlCooldownService.class),
                mock(MonitorAgentTaskEnqueuer.class)
        );
    }

    @Test
    void createTarget_persistsConfigJsonForPddMonitorTarget() {
        String configJson = "{\"top_n\":5,\"pinned_offer_ids\":[\"123\",\"456\"],\"webhook_url\":\"https://example.com/hook\"}";

        Map<String, Object> created = service.createTarget(Map.of(
                "platform", "pdd",
                "target_type", "shop",
                "label", "竞对店铺",
                "target_url", "https://mobile.yangkeduo.com/mall_page.html?mall_id=10001",
                "crawl_strategy", "pdd_shop_topn",
                "config_json", configJson
        ));

        assertNotNull(created.get("id"));
        assertEquals(configJson, created.get("config_json"));
        String stored = jdbc.queryForObject(
                "SELECT config_json FROM monitor_target WHERE tenant_id = ? AND id = ?",
                String.class,
                7L,
                created.get("id")
        );
        assertEquals(configJson, stored);
    }

    @Test
    void updateTarget_updatesConfigJson() {
        String initial = "{\"top_n\":20,\"pinned_offer_ids\":[]}";
        Map<String, Object> created = service.createTarget(Map.of(
                "platform", "pdd",
                "target_type", "shop",
                "label", "竞对店铺",
                "target_url", "https://mobile.yangkeduo.com/mall_page.html?mall_id=10002",
                "crawl_strategy", "pdd_shop_topn",
                "config_json", initial
        ));
        String updated = "{\"top_n\":10,\"pinned_offer_ids\":[\"999\"],\"webhook_url\":\"https://example.com/hook\"}";

        Map<String, Object> result = service.updateTarget(String.valueOf(created.get("id")), Map.of(
                "config_json", updated
        ));

        assertEquals(updated, result.get("config_json"));
        String stored = jdbc.queryForObject(
                "SELECT config_json FROM monitor_target WHERE tenant_id = ? AND id = ?",
                String.class,
                7L,
                created.get("id")
        );
        assertEquals(updated, stored);
    }
}
