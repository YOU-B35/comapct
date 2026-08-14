package com.crosshub.douyin.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "douyin_compass_product_rank")
public class DouyinCompassProductRank {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "board", nullable = false)
    private String board = "";

    @Column(name = "date_window", nullable = false)
    private String dateWindow = "";

    @Column(name = "report_day")
    private String reportDay = "";

    @Column(name = "rank_no", nullable = false)
    private Integer rankNo = 0;

    @Column(name = "product_id", nullable = false)
    private String productId = "";

    @Column(name = "product_name")
    private String productName = "";

    @Column(name = "main_image")
    private String mainImage = "";

    @Column(name = "category_path")
    private String categoryPath = "";

    @Column(name = "shop_name")
    private String shopName = "";

    @Column(name = "pay_amt")
    private Double payAmt;

    @Column(name = "click_cnt")
    private Double clickCnt;

    @Column(name = "pay_cnt")
    private Double payCnt;

    @Column(name = "click_pay_cvr")
    private Double clickPayCvr;

    @Column(name = "show_cnt")
    private Double showCnt;

    @Column(name = "order_cnt")
    private Double orderCnt;

    @Column(name = "deal_cnt")
    private Double dealCnt;

    @Column(name = "is_default_category", nullable = false)
    private Integer isDefaultCategory = 1;

    @Column(name = "category_id")
    private String categoryId = "";

    @Column(name = "category_name")
    private String categoryName = "";

    @Column(name = "source_url")
    private String sourceUrl = "";

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
    public String getBoard() { return board; }
    public void setBoard(String board) { this.board = board == null ? "" : board; }
    public String getDateWindow() { return dateWindow; }
    public void setDateWindow(String dateWindow) { this.dateWindow = dateWindow == null ? "" : dateWindow; }
    public String getReportDay() { return reportDay; }
    public void setReportDay(String reportDay) { this.reportDay = reportDay == null ? "" : reportDay; }
    public Integer getRankNo() { return rankNo; }
    public void setRankNo(Integer rankNo) { this.rankNo = rankNo == null ? 0 : rankNo; }
    public String getProductId() { return productId; }
    public void setProductId(String productId) { this.productId = productId == null ? "" : productId; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName == null ? "" : productName; }
    public String getMainImage() { return mainImage; }
    public void setMainImage(String mainImage) { this.mainImage = mainImage == null ? "" : mainImage; }
    public String getCategoryPath() { return categoryPath; }
    public void setCategoryPath(String categoryPath) { this.categoryPath = categoryPath == null ? "" : categoryPath; }
    public String getShopName() { return shopName; }
    public void setShopName(String shopName) { this.shopName = shopName == null ? "" : shopName; }
    public Double getPayAmt() { return payAmt; }
    public void setPayAmt(Double payAmt) { this.payAmt = payAmt; }
    public Double getClickCnt() { return clickCnt; }
    public void setClickCnt(Double clickCnt) { this.clickCnt = clickCnt; }
    public Double getPayCnt() { return payCnt; }
    public void setPayCnt(Double payCnt) { this.payCnt = payCnt; }
    public Double getClickPayCvr() { return clickPayCvr; }
    public void setClickPayCvr(Double clickPayCvr) { this.clickPayCvr = clickPayCvr; }
    public Double getShowCnt() { return showCnt; }
    public void setShowCnt(Double showCnt) { this.showCnt = showCnt; }
    public Double getOrderCnt() { return orderCnt; }
    public void setOrderCnt(Double orderCnt) { this.orderCnt = orderCnt; }
    public Double getDealCnt() { return dealCnt; }
    public void setDealCnt(Double dealCnt) { this.dealCnt = dealCnt; }
    public Integer getIsDefaultCategory() { return isDefaultCategory; }
    public void setIsDefaultCategory(Integer isDefaultCategory) {
        this.isDefaultCategory = isDefaultCategory == null ? 1 : isDefaultCategory;
    }
    public String getCategoryId() { return categoryId; }
    public void setCategoryId(String categoryId) { this.categoryId = categoryId == null ? "" : categoryId; }
    public String getCategoryName() { return categoryName; }
    public void setCategoryName(String categoryName) { this.categoryName = categoryName == null ? "" : categoryName; }
    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl == null ? "" : sourceUrl; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "" : rawJson; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
