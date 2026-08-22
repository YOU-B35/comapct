package com.crosshub.monitor.service;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

public interface MonitorService {
    List<Map<String, Object>> listTargets(String platform);
    Map<String, Object> createTarget(Map<String, Object> payload);
    Map<String, Object> updateTarget(String id, Map<String, Object> payload);
    void deleteTarget(String id);
    Map<String, Object> updateSchedule(String targetId, Map<String, Object> payload);
    Map<String, Object> trigger(String targetId, Map<String, Object> payload);
    Map<String, Object> getJob(String jobId);
    List<Map<String, Object>> listRecentJobs(String targetId, int limit);
    Map<String, Object> getLatest(String targetId);
    Map<String, Object> getHistory(String targetId);
    List<Map<String, Object>> getTrend(String targetId, int days, String productId);
    List<Map<String, Object>> getSignals(String targetId, int limit);
    Path resolveReportXlsx(String targetId);
}
