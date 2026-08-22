package com.crosshub.pdd.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "pdd_product")
public class PddProduct {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "external_shop_id")
    private String externalShopId = "";

    @Column(name = "product_id", nullable = false)
    private String productId = "";

    @Column(name = "product_name")
    private String productName = "";

    private String status = "";

    @Column(name = "status_label")
    private String statusLabel = "";

    private Double price;
    private Double stock;
    private Double sales;

    @Column(name = "main_image")
    private String mainImage = "";

    private String category = "";

    @Column(name = "article_no")
    private String articleNo = "";

    @Column(name = "sku_count")
    private Integer skuCount = 0;

    @Column(name = "skus_json")
    private String skusJson = "";

    @Column(name = "raw_json")
    private String rawJson = "";

    @Column(name = "product_key", nullable = false)
    private String productKey = "";

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
    public String getExternalShopId() { return externalShopId; }
    public void setExternalShopId(String externalShopId) { this.externalShopId = externalShopId == null ? "" : externalShopId; }
    public String getProductId() { return productId; }
    public void setProductId(String productId) { this.productId = productId == null ? "" : productId; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName == null ? "" : productName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status == null ? "" : status; }
    public String getStatusLabel() { return statusLabel; }
    public void setStatusLabel(String statusLabel) { this.statusLabel = statusLabel == null ? "" : statusLabel; }
    public Double getPrice() { return price; }
    public void setPrice(Double price) { this.price = price; }
    public Double getStock() { return stock; }
    public void setStock(Double stock) { this.stock = stock; }
    public Double getSales() { return sales; }
    public void setSales(Double sales) { this.sales = sales; }
    public String getMainImage() { return mainImage; }
    public void setMainImage(String mainImage) { this.mainImage = mainImage == null ? "" : mainImage; }
    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category == null ? "" : category; }
    public String getArticleNo() { return articleNo; }
    public void setArticleNo(String articleNo) { this.articleNo = articleNo == null ? "" : articleNo; }
    public Integer getSkuCount() { return skuCount; }
    public void setSkuCount(Integer skuCount) { this.skuCount = skuCount == null ? 0 : skuCount; }
    public String getSkusJson() { return skusJson; }
    public void setSkusJson(String skusJson) { this.skusJson = skusJson == null ? "" : skusJson; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
    public String getProductKey() { return productKey; }
    public void setProductKey(String productKey) { this.productKey = productKey == null ? "" : productKey; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
