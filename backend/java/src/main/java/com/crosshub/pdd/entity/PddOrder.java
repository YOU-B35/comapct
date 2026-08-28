package com.crosshub.pdd.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "pdd_order")
public class PddOrder {
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

    /** 时间窗口：today / d1 / d7 / d30 / d90，对齐用户「订单按时间段分」需求 */
    @Column(name = "date_window", nullable = false)
    private String dateWindow = "today";

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

    /** 订单实付金额（对齐 alibaba1688_order.paid_amount；agent 携带 cookie 抓取后回写） */
    @Column(name = "paid_amount", nullable = false)
    private String paidAmount = "0";

    /** 退款金额 */
    @Column(name = "refunded_amount", nullable = false)
    private String refundedAmount = "0";

    /** 支付时间（yyyy-MM-dd HH:mm:ss 或平台原始时间串），用于经营汇总/趋势按日聚合 */
    @Column(name = "paid_at")
    private String paidAt = "";

    /** 退款时间 */
    @Column(name = "refunded_at")
    private String refundedAt = "";

    /** 买家昵称（脱敏） */
    @Column(name = "buyer_masked")
    private String buyerMasked = "";

    /** 数据同步时间 */
    @Column(name = "synced_at")
    private String syncedAt = "";

    /** 单价（商品行），与 quantity/item_amount 对齐 alibaba1688_order_item */
    @Column(name = "unit_price", nullable = false)
    private String unitPrice = "0";

    /** 行金额 = 单价 × 数量 */
    @Column(name = "item_amount", nullable = false)
    private String itemAmount = "0";

    /** 商品主图 URL */
    @Column(name = "image_url")
    private String imageUrl = "";

    /** SKU 描述文本（规格串） */
    @Column(name = "sku_text")
    private String skuText = "";

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
    public String getDateWindow() { return dateWindow; }
    public void setDateWindow(String dateWindow) { this.dateWindow = dateWindow == null ? "today" : dateWindow; }
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
    public String getPaidAmount() { return paidAmount; }
    public void setPaidAmount(String paidAmount) { this.paidAmount = paidAmount == null ? "0" : paidAmount; }
    public String getRefundedAmount() { return refundedAmount; }
    public void setRefundedAmount(String refundedAmount) { this.refundedAmount = refundedAmount == null ? "0" : refundedAmount; }
    public String getPaidAt() { return paidAt; }
    public void setPaidAt(String paidAt) { this.paidAt = paidAt == null ? "" : paidAt; }
    public String getRefundedAt() { return refundedAt; }
    public void setRefundedAt(String refundedAt) { this.refundedAt = refundedAt == null ? "" : refundedAt; }
    public String getBuyerMasked() { return buyerMasked; }
    public void setBuyerMasked(String buyerMasked) { this.buyerMasked = buyerMasked == null ? "" : buyerMasked; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getUnitPrice() { return unitPrice; }
    public void setUnitPrice(String unitPrice) { this.unitPrice = unitPrice == null ? "0" : unitPrice; }
    public String getItemAmount() { return itemAmount; }
    public void setItemAmount(String itemAmount) { this.itemAmount = itemAmount == null ? "0" : itemAmount; }
    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl == null ? "" : imageUrl; }
    public String getSkuText() { return skuText; }
    public void setSkuText(String skuText) { this.skuText = skuText == null ? "" : skuText; }
}
