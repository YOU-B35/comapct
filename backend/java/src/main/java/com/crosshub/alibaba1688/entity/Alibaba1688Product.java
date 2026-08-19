package com.crosshub.alibaba1688.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "alibaba1688_product")
public class Alibaba1688Product {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "offer_id", nullable = false)
    private String offerId = "";

    @Column(name = "product_name")
    private String productName = "";

    @Column(name = "goods_no")
    private String goodsNo = "";

    @Column(name = "quality_score")
    private Double qualityScore;

    private String price = "";

    private Integer stock;

    @Column(name = "search_expose_7d")
    private Integer searchExpose7d;

    @Column(name = "visitor_30d")
    private Integer visitor30d;

    @Column(name = "gmv_30d")
    private String gmv30d = "";

    @Column(name = "gmv_1d")
    private String gmv1d = "";

    @Column(name = "product_updated_at")
    private String productUpdatedAt = "";

    private String status = "";

    @Column(name = "tag_potential", nullable = false)
    private Integer tagPotential = 0;

    @Column(name = "tag_yanxuan", nullable = false)
    private Integer tagYanxuan = 0;

    @Column(name = "tag_underperform", nullable = false)
    private Integer tagUnderperform = 0;

    @Column(name = "index_score")
    private String indexScore = "";

    @Column(name = "image_url")
    private String imageUrl = "";

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
    public String getOfferId() { return offerId; }
    public void setOfferId(String offerId) { this.offerId = offerId == null ? "" : offerId; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName == null ? "" : productName; }
    public String getGoodsNo() { return goodsNo; }
    public void setGoodsNo(String goodsNo) { this.goodsNo = goodsNo == null ? "" : goodsNo; }
    public Double getQualityScore() { return qualityScore; }
    public void setQualityScore(Double qualityScore) { this.qualityScore = qualityScore; }
    public String getPrice() { return price; }
    public void setPrice(String price) { this.price = price == null ? "" : price; }
    public Integer getStock() { return stock; }
    public void setStock(Integer stock) { this.stock = stock; }
    public Integer getSearchExpose7d() { return searchExpose7d; }
    public void setSearchExpose7d(Integer searchExpose7d) { this.searchExpose7d = searchExpose7d; }
    public Integer getVisitor30d() { return visitor30d; }
    public void setVisitor30d(Integer visitor30d) { this.visitor30d = visitor30d; }
    public String getGmv30d() { return gmv30d; }
    public void setGmv30d(String gmv30d) { this.gmv30d = gmv30d == null ? "" : gmv30d; }
    public String getGmv1d() { return gmv1d; }
    public void setGmv1d(String gmv1d) { this.gmv1d = gmv1d == null ? "" : gmv1d; }
    public String getProductUpdatedAt() { return productUpdatedAt; }
    public void setProductUpdatedAt(String productUpdatedAt) { this.productUpdatedAt = productUpdatedAt == null ? "" : productUpdatedAt; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status == null ? "" : status; }
    public Integer getTagPotential() { return tagPotential; }
    public void setTagPotential(Integer tagPotential) { this.tagPotential = tagPotential == null ? 0 : tagPotential; }
    public Integer getTagYanxuan() { return tagYanxuan; }
    public void setTagYanxuan(Integer tagYanxuan) { this.tagYanxuan = tagYanxuan == null ? 0 : tagYanxuan; }
    public Integer getTagUnderperform() { return tagUnderperform; }
    public void setTagUnderperform(Integer tagUnderperform) { this.tagUnderperform = tagUnderperform == null ? 0 : tagUnderperform; }
    public String getIndexScore() { return indexScore; }
    public void setIndexScore(String indexScore) { this.indexScore = indexScore == null ? "" : indexScore; }
    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl == null ? "" : imageUrl; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
