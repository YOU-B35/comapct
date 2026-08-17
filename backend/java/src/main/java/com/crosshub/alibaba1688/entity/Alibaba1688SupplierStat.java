package com.crosshub.alibaba1688.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "alibaba1688_supplier_stat")
public class Alibaba1688SupplierStat {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId;

    @Column(name = "supplier_key", nullable = false)
    private String supplierKey;

    @Column(name = "supplier_name")
    private String supplierName;

    @Column(name = "order_count")
    private Integer orderCount = 0;

    @Column(name = "total_amount")
    private Double totalAmount = 0d;

    @Column(name = "on_time_rate")
    private Double onTimeRate = 0d;

    @Column(name = "last_order_at")
    private String lastOrderAt;

    @Column(name = "window_days")
    private Integer windowDays = 90;

    @Column(name = "updated_at")
    private String updatedAt;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getStoreId() { return storeId; }
    public void setStoreId(String storeId) { this.storeId = storeId; }
    public String getSupplierKey() { return supplierKey; }
    public void setSupplierKey(String supplierKey) { this.supplierKey = supplierKey; }
    public String getSupplierName() { return supplierName; }
    public void setSupplierName(String supplierName) { this.supplierName = supplierName; }
    public Integer getOrderCount() { return orderCount; }
    public void setOrderCount(Integer orderCount) { this.orderCount = orderCount == null ? 0 : orderCount; }
    public Double getTotalAmount() { return totalAmount; }
    public void setTotalAmount(Double totalAmount) { this.totalAmount = totalAmount == null ? 0d : totalAmount; }
    public Double getOnTimeRate() { return onTimeRate; }
    public void setOnTimeRate(Double onTimeRate) { this.onTimeRate = onTimeRate == null ? 0d : onTimeRate; }
    public String getLastOrderAt() { return lastOrderAt; }
    public void setLastOrderAt(String lastOrderAt) { this.lastOrderAt = lastOrderAt; }
    public Integer getWindowDays() { return windowDays; }
    public void setWindowDays(Integer windowDays) { this.windowDays = windowDays == null ? 90 : windowDays; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt; }
}
