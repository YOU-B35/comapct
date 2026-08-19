package com.crosshub.alibaba1688.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "alibaba1688_order_item")
public class Alibaba1688OrderItem {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "order_no", nullable = false)
    private String orderNo = "";

    @Column(name = "line_id", nullable = false)
    private String lineId = "";

    @Column(name = "offer_id")
    private String offerId = "";

    @Column(name = "sku_id")
    private String skuId = "";

    @Column(name = "sku_text")
    private String skuText = "";

    @Column(name = "product_name")
    private String productName = "";

    @Column(name = "quantity", nullable = false)
    private String quantity = "0";

    @Column(name = "paid_amount", nullable = false)
    private String paidAmount = "0";

    @Column(name = "actual_unit_price")
    private String actualUnitPrice = "";

    @Column(name = "refunded_amount", nullable = false)
    private String refundedAmount = "0";

    @Column(name = "image_url")
    private String imageUrl = "";

    @Column(name = "raw_json")
    private String rawJson = "";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getStoreId() { return storeId; }
    public void setStoreId(String storeId) { this.storeId = storeId == null ? "" : storeId; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo == null ? "" : orderNo; }
    public String getLineId() { return lineId; }
    public void setLineId(String lineId) { this.lineId = lineId == null ? "" : lineId; }
    public String getOfferId() { return offerId; }
    public void setOfferId(String offerId) { this.offerId = offerId == null ? "" : offerId; }
    public String getSkuId() { return skuId; }
    public void setSkuId(String skuId) { this.skuId = skuId == null ? "" : skuId; }
    public String getSkuText() { return skuText; }
    public void setSkuText(String skuText) { this.skuText = skuText == null ? "" : skuText; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName == null ? "" : productName; }
    public String getQuantity() { return quantity; }
    public void setQuantity(String quantity) { this.quantity = quantity == null ? "0" : quantity; }
    public String getPaidAmount() { return paidAmount; }
    public void setPaidAmount(String paidAmount) { this.paidAmount = paidAmount == null ? "0" : paidAmount; }
    public String getActualUnitPrice() { return actualUnitPrice; }
    public void setActualUnitPrice(String actualUnitPrice) { this.actualUnitPrice = actualUnitPrice == null ? "" : actualUnitPrice; }
    public String getRefundedAmount() { return refundedAmount; }
    public void setRefundedAmount(String refundedAmount) { this.refundedAmount = refundedAmount == null ? "0" : refundedAmount; }
    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl == null ? "" : imageUrl; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
}
