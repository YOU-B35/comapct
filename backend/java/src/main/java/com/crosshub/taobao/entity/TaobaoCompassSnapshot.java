package com.crosshub.taobao.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 淘宝/天猫经营数据快照（生意参谋 sycm）。date_type/date_window 对齐抖音罗盘口径：
 * 实时=1, 近1天=20, 近7天=21, 近30天=23（probe 后可调整）。
 */
@Entity
@Table(name = "taobao_compass_snapshot")
public class TaobaoCompassSnapshot {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "date_type", nullable = false)
    private Integer dateType = 1;

    @Column(name = "date_window", nullable = false)
    private String dateWindow = "realtime";

    @Column(name = "payload_json", nullable = false)
    private String payloadJson = "{}";

    @Column(name = "raw_json")
    private String rawJson = "";

    @Column(name = "synced_at")
    private String syncedAt = "";

    @Column(name = "created_at")
    private String createdAt = "";

    @Column(name = "updated_at")
    private String updatedAt = "";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getStoreId() { return storeId; }
    public void setStoreId(String storeId) { this.storeId = storeId == null ? "" : storeId; }
    public Integer getDateType() { return dateType; }
    public void setDateType(Integer dateType) { this.dateType = dateType == null ? 1 : dateType; }
    public String getDateWindow() { return dateWindow; }
    public void setDateWindow(String dateWindow) { this.dateWindow = dateWindow == null ? "realtime" : dateWindow; }
    public String getPayloadJson() { return payloadJson; }
    public void setPayloadJson(String payloadJson) { this.payloadJson = payloadJson == null ? "{}" : payloadJson; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
