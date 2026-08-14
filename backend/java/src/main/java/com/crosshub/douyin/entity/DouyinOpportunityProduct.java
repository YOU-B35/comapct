package com.crosshub.douyin.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "douyin_opportunity_product")
public class DouyinOpportunityProduct {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "category_key", nullable = false)
    private String categoryKey = "";

    @Column(name = "category_id")
    private String categoryId = "";

    @Column(name = "category_name")
    private String categoryName = "";

    @Column(name = "category_query")
    private String categoryQuery = "";

    @Column(name = "is_default_category", nullable = false)
    private Integer isDefaultCategory = 1;

    @Column(name = "rank_no", nullable = false)
    private Integer rankNo = 0;

    @Column(name = "clue_id", nullable = false)
    private String clueId = "";

    @Column(name = "product_name")
    private String productName = "";

    @Column(name = "main_image")
    private String mainImage = "";

    @Column(name = "category_path")
    private String categoryPath = "";

    @Column(name = "price_min")
    private Double priceMin;

    @Column(name = "price_max")
    private Double priceMax;

    @Column(name = "search_heat")
    private Double searchHeat;

    @Column(name = "search_pv_range")
    private String searchPvRange = "";

    @Column(name = "pay_growth_rate")
    private Double payGrowthRate;

    @Column(name = "pay_amt_range")
    private String payAmtRange = "";

    @Column(name = "labels_json")
    private String labelsJson = "[]";

    @Column(name = "overview_json")
    private String overviewJson = "";

    @Column(name = "raw_json")
    private String rawJson = "";

    @Column(name = "source_url")
    private String sourceUrl = "";

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
    public String getCategoryKey() { return categoryKey; }
    public void setCategoryKey(String categoryKey) { this.categoryKey = categoryKey == null ? "" : categoryKey; }
    public String getCategoryId() { return categoryId; }
    public void setCategoryId(String categoryId) { this.categoryId = categoryId == null ? "" : categoryId; }
    public String getCategoryName() { return categoryName; }
    public void setCategoryName(String categoryName) { this.categoryName = categoryName == null ? "" : categoryName; }
    public String getCategoryQuery() { return categoryQuery; }
    public void setCategoryQuery(String categoryQuery) { this.categoryQuery = categoryQuery == null ? "" : categoryQuery; }
    public Integer getIsDefaultCategory() { return isDefaultCategory; }
    public void setIsDefaultCategory(Integer isDefaultCategory) { this.isDefaultCategory = isDefaultCategory == null ? 1 : isDefaultCategory; }
    public Integer getRankNo() { return rankNo; }
    public void setRankNo(Integer rankNo) { this.rankNo = rankNo == null ? 0 : rankNo; }
    public String getClueId() { return clueId; }
    public void setClueId(String clueId) { this.clueId = clueId == null ? "" : clueId; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName == null ? "" : productName; }
    public String getMainImage() { return mainImage; }
    public void setMainImage(String mainImage) { this.mainImage = mainImage == null ? "" : mainImage; }
    public String getCategoryPath() { return categoryPath; }
    public void setCategoryPath(String categoryPath) { this.categoryPath = categoryPath == null ? "" : categoryPath; }
    public Double getPriceMin() { return priceMin; }
    public void setPriceMin(Double priceMin) { this.priceMin = priceMin; }
    public Double getPriceMax() { return priceMax; }
    public void setPriceMax(Double priceMax) { this.priceMax = priceMax; }
    public Double getSearchHeat() { return searchHeat; }
    public void setSearchHeat(Double searchHeat) { this.searchHeat = searchHeat; }
    public String getSearchPvRange() { return searchPvRange; }
    public void setSearchPvRange(String searchPvRange) { this.searchPvRange = searchPvRange == null ? "" : searchPvRange; }
    public Double getPayGrowthRate() { return payGrowthRate; }
    public void setPayGrowthRate(Double payGrowthRate) { this.payGrowthRate = payGrowthRate; }
    public String getPayAmtRange() { return payAmtRange; }
    public void setPayAmtRange(String payAmtRange) { this.payAmtRange = payAmtRange == null ? "" : payAmtRange; }
    public String getLabelsJson() { return labelsJson; }
    public void setLabelsJson(String labelsJson) { this.labelsJson = labelsJson == null ? "[]" : labelsJson; }
    public String getOverviewJson() { return overviewJson; }
    public void setOverviewJson(String overviewJson) { this.overviewJson = overviewJson == null ? "" : overviewJson; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl == null ? "" : sourceUrl; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
