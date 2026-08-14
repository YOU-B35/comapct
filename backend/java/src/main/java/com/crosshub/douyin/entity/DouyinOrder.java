package com.crosshub.douyin.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "douyin_order")
public class DouyinOrder {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "external_shop_id")
    private String externalShopId = "";

    @Column(name = "report_day", nullable = false)
    private String reportDay = "";

    @Column(name = "order_no", nullable = false)
    private String orderNo = "";

    @Column(name = "product_name")
    private String productName = "";

    private String channel = "";
    private String sku = "";
    private Integer quantity = 1;
    private Double amount = 0d;
    private String currency = "CNY";
    private String status = "";

    @Column(name = "ship_deadline")
    private String shipDeadline = "";

    @Column(name = "ordered_at")
    private String orderedAt = "";

    @Column(name = "order_key", nullable = false)
    private String orderKey = "";

    @Column(name = "raw_json")
    private String rawJson = "";

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
    public String getExternalShopId() { return externalShopId; }
    public void setExternalShopId(String externalShopId) { this.externalShopId = externalShopId == null ? "" : externalShopId; }
    public String getReportDay() { return reportDay; }
    public void setReportDay(String reportDay) { this.reportDay = reportDay == null ? "" : reportDay; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo == null ? "" : orderNo; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName == null ? "" : productName; }
    public String getChannel() { return channel; }
    public void setChannel(String channel) { this.channel = channel == null ? "" : channel; }
    public String getSku() { return sku; }
    public void setSku(String sku) { this.sku = sku == null ? "" : sku; }
    public Integer getQuantity() { return quantity; }
    public void setQuantity(Integer quantity) { this.quantity = quantity == null ? 1 : quantity; }
    public Double getAmount() { return amount; }
    public void setAmount(Double amount) { this.amount = amount == null ? 0d : amount; }
    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency == null || currency.isBlank() ? "CNY" : currency; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status == null ? "" : status; }
    public String getShipDeadline() { return shipDeadline; }
    public void setShipDeadline(String shipDeadline) { this.shipDeadline = shipDeadline == null ? "" : shipDeadline; }
    public String getOrderedAt() { return orderedAt; }
    public void setOrderedAt(String orderedAt) { this.orderedAt = orderedAt == null ? "" : orderedAt; }
    public String getOrderKey() { return orderKey; }
    public void setOrderKey(String orderKey) { this.orderKey = orderKey == null ? "" : orderKey; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
