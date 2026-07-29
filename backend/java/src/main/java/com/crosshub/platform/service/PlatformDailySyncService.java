package com.crosshub.platform.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.aliexpress.service.AliExpressCrawlService;
import com.crosshub.amazon.service.AmazonSyncService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import com.crosshub.temu.service.TemuDailySyncService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * 全平台日批：每天 09:30（Asia/Shanghai）同步 Temu / 速卖通 / Amazon。
 * 前期由本机 Agent（有头）+ Java 侧 AE 爬虫执行；打开应用只读库展示状态/错误。
 */
@Service
public class PlatformDailySyncService {
    private static final Logger log = LoggerFactory.getLogger(PlatformDailySyncService.class);
    private static final List<String> PLATFORMS = List.of("temu", "aliexpress", "amazon");

    private final CrawlerProperties crawlerProperties;
    private final AgentPresenceService agentPresenceService;
    private final PlatformAccountRepository platformAccountRepository;
    private final TemuDailySyncService temuDailySyncService;
    private final AliExpressCrawlService aliExpressCrawlService;
    private final AmazonSyncService amazonSyncService;

    public PlatformDailySyncService(
            CrawlerProperties crawlerProperties,
            AgentPresenceService agentPresenceService,
            PlatformAccountRepository platformAccountRepository,
            TemuDailySyncService temuDailySyncService,
            AliExpressCrawlService aliExpressCrawlService,
            AmazonSyncService amazonSyncService
    ) {
        this.crawlerProperties = crawlerProperties;
        this.agentPresenceService = agentPresenceService;
        this.platformAccountRepository = platformAccountRepository;
        this.temuDailySyncService = temuDailySyncService;
        this.aliExpressCrawlService = aliExpressCrawlService;
        this.amazonSyncService = amazonSyncService;
    }

    public void runDailySyncForAllRegisteredTenants() {
        runDailySyncNow(false);
    }

    /** 手动/调度共用：对所有已注册助手租户入队日批。 */
    public Map<String, Object> runDailySyncNow(boolean force) {
        Map<String, Object> summary = new LinkedHashMap<>();
        if (!crawlerProperties.getDailySync().isEnabled()) {
            log.info("Platform daily sync skipped: disabled");
            summary.put("action", "skipped_disabled");
            summary.put("tenants", List.of());
            return summary;
        }
        List<Long> tenants = agentPresenceService.listRegisteredTenantIds();
        if (tenants.isEmpty()) {
            log.info("Platform daily sync: no registered agents");
            summary.put("action", "skipped_no_agents");
            summary.put("tenants", List.of());
            return summary;
        }
        log.info("Platform daily sync start for {} tenant(s): {} force={}", tenants.size(), PLATFORMS, force);
        List<Map<String, Object>> results = new ArrayList<>();
        for (Long tenantId : tenants) {
            try {
                Map<String, Object> result = enqueueDailySyncForTenant(tenantId, force);
                results.add(result);
                log.info("Platform daily sync tenant {}: {}", tenantId, result.get("actions"));
            } catch (Exception ex) {
                log.warn("Platform daily sync failed for tenant {}: {}", tenantId, ex.getMessage());
                Map<String, Object> failed = new LinkedHashMap<>();
                failed.put("tenant_id", tenantId);
                failed.put("error", ex.getMessage());
                results.add(failed);
            }
        }
        summary.put("action", "ran");
        summary.put("force", force);
        summary.put("tenants", results);
        return summary;
    }

    public Map<String, Object> enqueueDailySyncForTenant(Long tenantId) {
        return enqueueDailySyncForTenant(tenantId, false);
    }

    public Map<String, Object> enqueueDailySyncForTenant(Long tenantId, boolean force) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("tenant_id", tenantId);
        out.put("force", force);
        List<String> actions = new ArrayList<>();
        Map<String, Object> platforms = new LinkedHashMap<>();

        Map<String, Object> temu;
        try {
            temu = temuDailySyncService.enqueueDailyCrawl(tenantId, force);
        } catch (Exception ex) {
            log.warn("Daily Temu enqueue failed tenant {}: {}", tenantId, ex.getMessage());
            temu = Map.of("action", "failed_exception", "platform", "temu", "error", String.valueOf(ex.getMessage()));
        }
        platforms.put("temu", temu);
        actions.add("temu:" + String.valueOf(temu.get("action")));

        if (hasPlatformAccount(tenantId, "aliexpress")) {
            Map<String, Object> ae;
            try {
                ae = aliExpressCrawlService.enqueueDailyCrawl(tenantId, force);
            } catch (Exception ex) {
                log.warn("Daily AE enqueue failed tenant {}: {}", tenantId, ex.getMessage());
                ae = Map.of("action", "failed_exception", "platform", "aliexpress", "error", String.valueOf(ex.getMessage()));
            }
            platforms.put("aliexpress", ae);
            actions.add("aliexpress:" + String.valueOf(ae.get("action")));
        } else {
            platforms.put("aliexpress", Map.of("action", "skipped_no_accounts", "platform", "aliexpress"));
            actions.add("aliexpress:skipped_no_accounts");
        }

        if (hasPlatformAccount(tenantId, "amazon")) {
            Map<String, Object> amz;
            try {
                amz = amazonSyncService.enqueueDailySync(tenantId, force);
            } catch (Exception ex) {
                log.warn("Daily Amazon enqueue failed tenant {}: {}", tenantId, ex.getMessage());
                amz = Map.of("action", "failed_exception", "platform", "amazon", "error", String.valueOf(ex.getMessage()));
            }
            platforms.put("amazon", amz);
            actions.add("amazon:" + String.valueOf(amz.get("action")));
        } else {
            platforms.put("amazon", Map.of("action", "skipped_no_accounts", "platform", "amazon"));
            actions.add("amazon:skipped_no_accounts");
        }

        out.put("platforms", platforms);
        out.put("actions", actions);
        return out;
    }

    public Map<String, Object> buildSyncStatus(Long tenantId) {
        Map<String, Object> out = new LinkedHashMap<>();
        CrawlerProperties.DailySync cfg = crawlerProperties.getDailySync();
        Map<String, Object> schedule = new LinkedHashMap<>();
        schedule.put("enabled", cfg.isEnabled());
        schedule.put("cron", cfg.getCron());
        schedule.put("zone", cfg.getZone());
        schedule.put("time_label", "每天 09:30");
        schedule.put("scope_label", "全平台");
        schedule.put("platforms", PLATFORMS);
        schedule.put("next_run_hint", nextRunHint());
        out.put("schedule", schedule);

        boolean agentOnline = agentPresenceService.isAgentOnline(tenantId);
        out.put("agent_online", agentOnline);
        out.putAll(agentPresenceService.integrationStatus(tenantId));

        Map<String, Object> platforms = new LinkedHashMap<>();
        Map<String, Object> temu = temuDailySyncService.buildSyncStatus(tenantId);
        // Temu 状态里已含 schedule；聚合时只保留平台切片相关字段
        platforms.put("temu", temuSlice(temu));
        platforms.put("aliexpress", aliExpressCrawlService.buildSyncStatus(tenantId));
        platforms.put("amazon", amazonSyncService.buildSyncStatus(tenantId));
        out.put("platforms", platforms);

        boolean hasError = false;
        List<String> errorMessages = new ArrayList<>();
        String errorCode = "";
        for (String key : PLATFORMS) {
            Object raw = platforms.get(key);
            if (!(raw instanceof Map<?, ?> map)) {
                continue;
            }
            if (Boolean.TRUE.equals(map.get("has_error"))) {
                hasError = true;
                String msg = stringValue(map.get("error_message"));
                String code = stringValue(map.get("error_code"));
                if (!msg.isBlank()) {
                    errorMessages.add(platformLabel(key) + "：" + msg);
                }
                if (errorCode.isBlank() && !code.isBlank()) {
                    errorCode = code;
                }
            }
        }
        out.put("has_error", hasError);
        out.put("error_code", errorCode);
        out.put("error_message", String.join("；", errorMessages));
        out.put("data_report_time", stringValue(temu.get("data_report_time")));
        return out;
    }

    private Map<String, Object> temuSlice(Map<String, Object> temuFull) {
        Map<String, Object> slice = new LinkedHashMap<>();
        slice.put("platform", "temu");
        slice.put("last_job", temuFull.get("last_job"));
        slice.put("has_error", temuFull.get("has_error"));
        slice.put("error_code", temuFull.get("error_code"));
        slice.put("error_message", temuFull.get("error_message"));
        slice.put("data_report_time", temuFull.get("data_report_time"));
        slice.put("agent_online", temuFull.get("agent_online"));
        return slice;
    }

    private boolean hasPlatformAccount(Long tenantId, String platform) {
        List<PlatformAccount> list = platformAccountRepository.findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, platform);
        return list != null && !list.isEmpty();
    }

    private String nextRunHint() {
        ZoneId zone;
        try {
            zone = ZoneId.of(crawlerProperties.getDailySync().getZone());
        } catch (Exception ex) {
            zone = ZoneId.of("Asia/Shanghai");
        }
        ZonedDateTime now = ZonedDateTime.now(zone);
        ZonedDateTime next = now.withHour(9).withMinute(30).withSecond(0).withNano(0);
        if (!next.isAfter(now)) {
            next = next.plusDays(1);
        }
        return next.format(DateTimeFormatter.ofPattern("MM-dd HH:mm"));
    }

    private static String platformLabel(String platform) {
        return switch (String.valueOf(platform).toLowerCase(Locale.ROOT)) {
            case "temu" -> "Temu";
            case "aliexpress" -> "速卖通";
            case "amazon" -> "Amazon";
            default -> platform;
        };
    }

    private static String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }
}
