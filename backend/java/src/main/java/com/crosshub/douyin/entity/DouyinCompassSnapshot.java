package com.crosshub.douyin.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "douyin_compass_snapshot")
public class DouyinCompassSnapshot {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    @Column(name = "report_day", nullable = false)
    private String reportDay = "";

    @Column(name = "date_type", nullable = false)
    private Integer dateType = 1;

    @Column(name = "shop_name")
    private String shopName = "";

    @Column(name = "pay_amt")
    private Double payAmt;

    @Column(name = "pay_cnt")
    private Double payCnt;

    @Column(name = "pay_ucnt")
    private Double payUcnt;

    @Column(name = "income_amt")
    private Double incomeAmt;

    @Column(name = "per_usr_pay_amt")
    private Double perUsrPayAmt;

    @Column(name = "product_show_ucnt")
    private Double productShowUcnt;

    @Column(name = "product_show_cnt")
    private Double productShowCnt;

    @Column(name = "product_click_ucnt")
    private Double productClickUcnt;

    @Column(name = "product_click_cnt")
    private Double productClickCnt;

    @Column(name = "show_click_rate")
    private Double showClickRate;

    @Column(name = "click_pay_rate")
    private Double clickPayRate;

    @Column(name = "settlement_amt")
    private Double settlementAmt;

    @Column(name = "refund_amt")
    private Double refundAmt;

    @Column(name = "refund_rate")
    private Double refundRate;

    @Column(name = "exp_score")
    private Double expScore;

    @Column(name = "exp_product")
    private Double expProduct;

    @Column(name = "exp_service")
    private Double expService;

    @Column(name = "exp_logistics")
    private Double expLogistics;

    @Column(name = "carrier_json")
    private String carrierJson = "[]";

    @Column(name = "metrics_json")
    private String metricsJson = "{}";

    @Column(name = "raw_json")
    private String rawJson = "{}";

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
    public String getReportDay() { return reportDay; }
    public void setReportDay(String reportDay) { this.reportDay = reportDay == null ? "" : reportDay; }
    public Integer getDateType() { return dateType; }
    public void setDateType(Integer dateType) { this.dateType = dateType == null ? 1 : dateType; }
    public String getShopName() { return shopName; }
    public void setShopName(String shopName) { this.shopName = shopName == null ? "" : shopName; }
    public Double getPayAmt() { return payAmt; }
    public void setPayAmt(Double payAmt) { this.payAmt = payAmt; }
    public Double getPayCnt() { return payCnt; }
    public void setPayCnt(Double payCnt) { this.payCnt = payCnt; }
    public Double getPayUcnt() { return payUcnt; }
    public void setPayUcnt(Double payUcnt) { this.payUcnt = payUcnt; }
    public Double getIncomeAmt() { return incomeAmt; }
    public void setIncomeAmt(Double incomeAmt) { this.incomeAmt = incomeAmt; }
    public Double getPerUsrPayAmt() { return perUsrPayAmt; }
    public void setPerUsrPayAmt(Double perUsrPayAmt) { this.perUsrPayAmt = perUsrPayAmt; }
    public Double getProductShowUcnt() { return productShowUcnt; }
    public void setProductShowUcnt(Double productShowUcnt) { this.productShowUcnt = productShowUcnt; }
    public Double getProductShowCnt() { return productShowCnt; }
    public void setProductShowCnt(Double productShowCnt) { this.productShowCnt = productShowCnt; }
    public Double getProductClickUcnt() { return productClickUcnt; }
    public void setProductClickUcnt(Double productClickUcnt) { this.productClickUcnt = productClickUcnt; }
    public Double getProductClickCnt() { return productClickCnt; }
    public void setProductClickCnt(Double productClickCnt) { this.productClickCnt = productClickCnt; }
    public Double getShowClickRate() { return showClickRate; }
    public void setShowClickRate(Double showClickRate) { this.showClickRate = showClickRate; }
    public Double getClickPayRate() { return clickPayRate; }
    public void setClickPayRate(Double clickPayRate) { this.clickPayRate = clickPayRate; }
    public Double getSettlementAmt() { return settlementAmt; }
    public void setSettlementAmt(Double settlementAmt) { this.settlementAmt = settlementAmt; }
    public Double getRefundAmt() { return refundAmt; }
    public void setRefundAmt(Double refundAmt) { this.refundAmt = refundAmt; }
    public Double getRefundRate() { return refundRate; }
    public void setRefundRate(Double refundRate) { this.refundRate = refundRate; }
    public Double getExpScore() { return expScore; }
    public void setExpScore(Double expScore) { this.expScore = expScore; }
    public Double getExpProduct() { return expProduct; }
    public void setExpProduct(Double expProduct) { this.expProduct = expProduct; }
    public Double getExpService() { return expService; }
    public void setExpService(Double expService) { this.expService = expService; }
    public Double getExpLogistics() { return expLogistics; }
    public void setExpLogistics(Double expLogistics) { this.expLogistics = expLogistics; }
    public String getCarrierJson() { return carrierJson; }
    public void setCarrierJson(String carrierJson) { this.carrierJson = carrierJson == null ? "[]" : carrierJson; }
    public String getMetricsJson() { return metricsJson; }
    public void setMetricsJson(String metricsJson) { this.metricsJson = metricsJson == null ? "{}" : metricsJson; }
    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson == null ? "{}" : rawJson; }
    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl == null ? "" : sourceUrl; }
    public String getSyncedAt() { return syncedAt; }
    public void setSyncedAt(String syncedAt) { this.syncedAt = syncedAt == null ? "" : syncedAt; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
