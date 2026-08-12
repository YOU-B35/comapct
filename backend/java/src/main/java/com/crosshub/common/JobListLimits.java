package com.crosshub.common;

/** Shared clamp for platform sync-history job list `limit` query params. */
public final class JobListLimits {
    public static final int DEFAULT = 20;
    public static final int MIN = 1;
    public static final int MAX = 60;

    private JobListLimits() {}

    public static int clamp(Integer limit) {
        if (limit == null || limit < MIN) {
            return DEFAULT;
        }
        return Math.min(limit, MAX);
    }
}
