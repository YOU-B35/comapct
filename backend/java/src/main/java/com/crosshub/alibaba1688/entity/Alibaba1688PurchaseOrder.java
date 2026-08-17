package com.crosshub.alibaba1688.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "alibaba1688_purchase_order")
public class Alibaba1688PurchaseOrder {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId;

    @Column(name = "order_no", nullable = false)
    private String orderNo;

    @Column
    private String status;

    @Column(name = "pay_status")
    private String payStatus;

    @Column(name = "ship_status")
    private String shipStatus;

    @Column(name = "product_name")
    private String productName;

    @Column
    private String sku;

    @Column(name = "supplier_name")
    private String supplierName;

    @Column(name = "supplier_id")
    private String supplierId;

    @Column
    private Integer quantity;

    @Column(name = "unit_price")
    private Double unitPrice;

    @Column
    private Double amount;

    @Column
    private String currency = "CNY";

    @Column(name = "linked_platform")
    private String linkedPlatform;

    @Column(name = "expected_arrival_at")
    private String expectedArrivalAt;

    @Column(name = "expected_ship_at")
    private String expectedShipAt;

    @Column(name = "actual_ship_at")
    private String actualShipAt;

    @Column(name = "logistics_status")
    private String logisticsStatus;

    @Column(name = "logistics_no")
    private String logisticsNo;

    @Column(name = "is_delayed")
    private Integer isDelayed = 0;

    @Column(name = "is_stockout")
    private Integer isStockout = 0;

    @Column(name = "raw_json")
    private String rawJson;

    @Column(name = "synced_at")
    private String syncedAt;

    @Column(name = "created_at")
    private String createdAt;

    @Column(name = "updated_at")
    private String updatedAt;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getStoreId() { return storeId; }
    public void setStoreId(String storeId) { this.storeId = storeId; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getPayStatus() { return payStatus; }
    public void setPayStatus(String payStatus) { this.payStatus = payStatus; }
    public String getShipStatus() { return shipStatus; }
    public void setShipStatus(String shipStatus) { this.shipStatus = shipStatus; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName; }
    public String getSku() { return sku; }
    public void setSku(String sku) { this.sku = sku; }
    public String getSupplierName() { return supplierName; }
    public void setSupplierName(String supplierName) { this.supplierName = supplierName; }
    public String getSupplierId() { return supplierId; }
    public void setSupplierId(String supplierId) { this.supplierId = supplierId; }
    public Integer getQuantity() { return quantity; }
    public void setQuantity(Integer quantity) { this.quantity = quantity; }
    public Double getUnitPrice() { return unitPrice; }
    public void setUnitPrice(Double unitPrice) { this.unitPrice = unitPrice; }
    public Double getAmount() { return amount; }
    public void setAmount(Double amount) { this.amount = amount; }
    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency == null || currency.isBlank() ? "CNY" : currency; }
    public String getLinkedPlatform() { return linkedPlatform; }
    public void setLinkedPlatform(String linkedPlatform) { this.linkedPlatform = linkedPlatform; }
    public String getExpectedArrivalAt() { return expectedArrivalAt; }
    public void setExpectedArrivalAt(String expectedArrivalAt) { this.expectedArrivalAt = expectedArrivalAt; }
    public String getExpectedShipAt() { return expectedShipAt; }
    public void setExpectedShipAt(String expectedShipAt) { this.expectedShipAt = expectedShipAt; }
    public String getActualShipAt() { return actualShipAt; }
    public void setActualShipAt(String actualShipAt) { this.actualShipAt = actualShipAt; }
    public String getLogisticsStatus() { return logisticsStatus; }
    public void setLogisticsStatus(String logisticsStatus) { this.logisticsStatus = logisticsStatus; }
    public String getLogisticsNo() { return logisticsNo; }
    public void setLogisticsNo(String logisticsNo) { this.logisticsNo = logisticsNo; }
    public Integer getIsDelayed() { return isDelayed; }
    public void setIsDelayed(Integer isDelayed) { this.isDelayed = isDelayed == null ? 0 : isDelayed; }
    public Integer getIsStockout() { return isStockout; }
    public void setIsStockout(Integer isStockout) { this.isStockout = isStockout == null ? 0 : isStockout; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt; }
}
