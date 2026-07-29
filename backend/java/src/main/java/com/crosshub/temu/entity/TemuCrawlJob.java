package com.crosshub.temu.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "temu_crawl_job")
public class TemuCrawlJob {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "triggered_by", nullable = false)
    private Long triggeredBy;

    @Column(name = "status", nullable = false)
    private String status;

    @Column(name = "mode", nullable = false)
    private String mode;

    @Column(name = "report_time")
    private String reportTime;

    @Column(name = "shops_count")
    private Integer shopsCount;

    @Column(name = "rows_count")
    private Integer rowsCount;

    @Column(name = "error_message")
    private String errorMessage;

    @Column(name = "error_code")
    private String errorCode;

    @Column(name = "started_at")
    private String startedAt;

    @Column(name = "finished_at")
    private String finishedAt;

    @Column(name = "created_at", nullable = false)
    private String createdAt;

    @Column(name = "agent_task_id", nullable = false)
    private String agentTaskId = "";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public Long getTriggeredBy() { return triggeredBy; }
    public void setTriggeredBy(Long triggeredBy) { this.triggeredBy = triggeredBy; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getMode() { return mode; }
    public void setMode(String mode) { this.mode = mode; }
    public String getReportTime() { return reportTime; }
    public void setReportTime(String reportTime) { this.reportTime = reportTime; }
    public Integer getShopsCount() { return shopsCount; }
    public void setShopsCount(Integer shopsCount) { this.shopsCount = shopsCount; }
    public Integer getRowsCount() { return rowsCount; }
    public void setRowsCount(Integer rowsCount) { this.rowsCount = rowsCount; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String errorCode) { this.errorCode = errorCode; }
    public String getStartedAt() { return startedAt; }
    public void setStartedAt(String startedAt) { this.startedAt = startedAt; }
    public String getFinishedAt() { return finishedAt; }
    public void setFinishedAt(String finishedAt) { this.finishedAt = finishedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
    public String getAgentTaskId() { return agentTaskId; }
    public void setAgentTaskId(String agentTaskId) { this.agentTaskId = agentTaskId == null ? "" : agentTaskId; }
}
