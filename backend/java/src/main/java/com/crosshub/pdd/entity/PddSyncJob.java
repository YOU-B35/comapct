package com.crosshub.pdd.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "pdd_sync_job")
public class PddSyncJob {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(nullable = false)
    private String scope = "orders";

    @Column(nullable = false)
    private String status = "pending";

    @Column(name = "store_id")
    private String storeId = "";

    @Column(name = "agent_task_id")
    private String agentTaskId = "";

    @Column(name = "orders_count")
    private Integer ordersCount = 0;

    @Column(name = "products_count")
    private Integer productsCount = 0;

    @Column(name = "compass_count")
    private Integer compassCount = 0;

    @Column(name = "error_code")
    private String errorCode = "";

    @Column(name = "error_message")
    private String errorMessage = "";

    private String message = "";

    @Column(name = "created_at")
    private String createdAt = "";

    @Column(name = "updated_at")
    private String updatedAt = "";

    @Column(name = "finished_at")
    private String finishedAt = "";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getScope() { return scope; }
    public void setScope(String scope) { this.scope = scope == null ? "orders" : scope; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status == null ? "pending" : status; }
    public String getStoreId() { return storeId; }
    public void setStoreId(String storeId) { this.storeId = storeId == null ? "" : storeId; }
    public String getAgentTaskId() { return agentTaskId; }
    public void setAgentTaskId(String agentTaskId) { this.agentTaskId = agentTaskId == null ? "" : agentTaskId; }
    public Integer getOrdersCount() { return ordersCount; }
    public void setOrdersCount(Integer ordersCount) { this.ordersCount = ordersCount == null ? 0 : ordersCount; }
    public Integer getProductsCount() { return productsCount; }
    public void setProductsCount(Integer productsCount) { this.productsCount = productsCount == null ? 0 : productsCount; }
    public Integer getCompassCount() { return compassCount; }
    public void setCompassCount(Integer compassCount) { this.compassCount = compassCount == null ? 0 : compassCount; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String errorCode) { this.errorCode = errorCode == null ? "" : errorCode; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage == null ? "" : errorMessage; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message == null ? "" : message; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
    public String getFinishedAt() { return finishedAt; }
    public void setFinishedAt(String finishedAt) { this.finishedAt = finishedAt == null ? "" : finishedAt; }
}
