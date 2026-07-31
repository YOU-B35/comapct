package com.crosshub.common;

public class CrawlCooldownException extends RuntimeException {
    private final long remainingMs;
    private final String scope;

    public CrawlCooldownException(long remainingMs) {
        this(remainingMs, TenantCrawlCooldownService.SCOPE_PLATFORM, AppErrorCode.CRAWL_COOLDOWN.getUserMessage());
    }

    public CrawlCooldownException(long remainingMs, String scope, String message) {
        super(message);
        this.remainingMs = remainingMs;
        this.scope = scope == null || scope.isBlank()
                ? TenantCrawlCooldownService.SCOPE_PLATFORM
                : scope;
    }

    public long getRemainingMs() {
        return remainingMs;
    }

    public String getScope() {
        return scope;
    }
}
