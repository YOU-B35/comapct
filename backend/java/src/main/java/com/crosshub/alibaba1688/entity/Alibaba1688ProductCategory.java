package com.crosshub.alibaba1688.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "alibaba1688_product_category")
public class Alibaba1688ProductCategory {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "offer_id", nullable = false)
    private String offerId = "";

    @Column(name = "category_code", nullable = false)
    private String categoryCode = "";

    @Column(name = "source_sync_id")
    private String sourceSyncId = "";

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
    public String getOfferId() { return offerId; }
    public void setOfferId(String offerId) { this.offerId = offerId == null ? "" : offerId; }
    public String getCategoryCode() { return categoryCode; }
    public void setCategoryCode(String categoryCode) { this.categoryCode = categoryCode == null ? "" : categoryCode; }
    public String getSourceSyncId() { return sourceSyncId; }
    public void setSourceSyncId(String sourceSyncId) { this.sourceSyncId = sourceSyncId == null ? "" : sourceSyncId; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
