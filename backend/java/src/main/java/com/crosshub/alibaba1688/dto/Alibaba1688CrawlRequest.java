package com.crosshub.alibaba1688.dto;

public class Alibaba1688CrawlRequest {
    private String jobType;
    private String storeId;
    private Boolean force;
    private Boolean recordCooldown;

    public String getJobType() { return jobType; }
    public void setJobType(String jobType) { this.jobType = jobType; }
    public String getStoreId() { return storeId; }
    public void setStoreId(String storeId) { this.storeId = storeId; }
    public Boolean getForce() { return force; }
    public void setForce(Boolean force) { this.force = force; }
    public Boolean getRecordCooldown() { return recordCooldown; }
    public void setRecordCooldown(Boolean recordCooldown) { this.recordCooldown = recordCooldown; }

    public String resolvedJobType() {
        String t = jobType == null ? "" : jobType.trim().toLowerCase();
        if (t.isEmpty() || "crawl".equals(t)) return "sync";
        if ("login_probe".equals(t) || "sync".equals(t)) return t;
        return "sync";
    }

    public boolean resolvedForce() {
        return Boolean.TRUE.equals(force);
    }

    public boolean resolvedRecordCooldown() {
        return recordCooldown == null || Boolean.TRUE.equals(recordCooldown);
    }
}
