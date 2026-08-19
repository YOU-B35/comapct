package com.crosshub.alibaba1688.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "alibaba1688_order")
public class Alibaba1688Order {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "order_no", nullable = false)
    private String orderNo = "";

    @Column(name = "status", nullable = false)
    private String status = "";

    @Column(name = "paid_amount", nullable = false)
    private String paidAmount = "0";

    @Column(name = "refunded_amount", nullable = false)
    private String refundedAmount = "0";

    @Column(name = "paid_at")
    private String paidAt = "";

    @Column(name = "refunded_at")
    private String refundedAt = "";

    @Column(name = "created_platform_at")
    private String createdPlatformAt = "";

    @Column(name = "updated_platform_at")
    private String updatedPlatformAt = "";

    @Column(name = "buyer_masked")
    private String buyerMasked = "";

    @Column(name = "raw_json")
    private String rawJson = "";

    @Column(name = "synced_at", nullable = false)
    private String syncedAt = "";

    @Column(name = "created_at", nullable = false)
    private String createdAt = "";

    @Column(name = "updated_at", nullable = false)
    private String updatedAt = "";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getStoreId() { return storeId; }
    public void setStoreId(String storeId) { this.storeId = storeId == null ? "" : storeId; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo == null ? "" : orderNo; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status == null ? "" : status; }
    public String getPaidAmount() { return paidAmount; }
    public void setPaidAmount(String paidAmount) { this.paidAmount = paidAmount == null ? "0" : paidAmount; }
    public String getRefundedAmount() { return refundedAmount; }
    public void setRefundedAmount(String refundedAmount) { this.refundedAmount = refundedAmount == null ? "0" : refundedAmount; }
    public String getPaidAt() { return paidAt; }
    public void setPaidAt(String paidAt) { this.paidAt = paidAt == null ? "" : paidAt; }
    public String getRefundedAt() { return refundedAt; }
    public void setRefundedAt(String refundedAt) { this.refundedAt = refundedAt == null ? "" : refundedAt; }
    public String getCreatedPlatformAt() { return createdPlatformAt; }
    public void setCreatedPlatformAt(String createdPlatformAt) { this.createdPlatformAt = createdPlatformAt == null ? "" : createdPlatformAt; }
    public String getUpdatedPlatformAt() { return updatedPlatformAt; }
    public void setUpdatedPlatformAt(String updatedPlatformAt) { this.updatedPlatformAt = updatedPlatformAt == null ? "" : updatedPlatformAt; }
    public String getBuyerMasked() { return buyerMasked; }
    public void setBuyerMasked(String buyerMasked) { this.buyerMasked = buyerMasked == null ? "" : buyerMasked; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
