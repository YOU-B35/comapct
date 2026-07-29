package com.crosshub.platform.service;

import com.crosshub.config.CrawlerProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 全平台日批调度：Temu + 速卖通 + Amazon，默认每天 09:30 Asia/Shanghai。
 */
@Component
public class PlatformDailySyncScheduler {
    private static final Logger log = LoggerFactory.getLogger(PlatformDailySyncScheduler.class);

    private final PlatformDailySyncService dailySyncService;
    private final CrawlerProperties crawlerProperties;

    public PlatformDailySyncScheduler(PlatformDailySyncService dailySyncService, CrawlerProperties crawlerProperties) {
        this.dailySyncService = dailySyncService;
        this.crawlerProperties = crawlerProperties;
    }

    @Scheduled(cron = "${crosshub.crawler.daily-sync.cron:0 30 9 * * *}", zone = "${crosshub.crawler.daily-sync.zone:Asia/Shanghai}")
    public void dailyPlatformSync() {
        if (!crawlerProperties.getDailySync().isEnabled()) {
            return;
        }
        log.info("Platform daily sync triggered (09:30 schedule, all platforms)");
        dailySyncService.runDailySyncForAllRegisteredTenants();
    }
}
