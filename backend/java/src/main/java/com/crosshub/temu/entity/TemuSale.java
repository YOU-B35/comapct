package com.crosshub.temu.entity;

import jakarta.persistence.*;

@Entity
@Table(name = "temu_sale")
public class TemuSale {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String platform;
    private String status;
    @Column(name = "report_time")
    private String reportTime;
    @Column(name = "shop_name")
    private String shopName;
    @Column(name = "shop_id")
    private String shopId;
    @Column(name = "tenant_id")
    private Long tenantId;
    @Column(name = "user_id")
    private Long userId;
    private Integer cost;
    @Column(name = "category_name")
    private String categoryName;
    @Column(name = "img_url")
    private String imgUrl;
    private String title;
    private String skc;
    private String spu;
    @Column(name = "ext_code")
    private String extCode;
    @Column(name = "son_sku")
    private String sonSku;
    @Column(name = "son_price")
    private Integer sonPrice;
    @Column(name = "son_today_sales")
    private Integer sonTodaySales;
    @Column(name = "son_sales_seven_days")
    private Integer sonSalesSevenDays;
    @Column(name = "son_sales_thirty_days")
    private Integer sonSalesThirtyDays;
    @Column(name = "join_site_time")
    private Integer joinSiteTime;
    @Column(name = "warehouse_available_stock")
    private Integer warehouseAvailableStock;
    private String nickname;
    private String username;
    private String enterprise;

    public Long getId() { return id; }
    public String getPlatform() { return platform; }
    public String getStatus() { return status; }
    public String getReportTime() { return reportTime; }
    public String getShopName() { return shopName; }
    public String getShopId() { return shopId; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public Long getUserId() { return userId; }
    public Integer getCost() { return cost; }
    public void setCost(Integer cost) { this.cost = cost; }
    public String getCategoryName() { return categoryName; }
    public String getImgUrl() { return imgUrl; }
    public String getTitle() { return title; }
    public String getSkc() { return skc; }
    public String getSpu() { return spu; }
    public String getExtCode() { return extCode; }
    public String getSonSku() { return sonSku; }
    public Integer getSonPrice() { return sonPrice; }
    public Integer getSonTodaySales() { return sonTodaySales; }
    public Integer getSonSalesSevenDays() { return sonSalesSevenDays; }
    public Integer getSonSalesThirtyDays() { return sonSalesThirtyDays; }
    public Integer getJoinSiteTime() { return joinSiteTime; }
    public Integer getWarehouseAvailableStock() { return warehouseAvailableStock; }
    public String getNickname() { return nickname; }
    public String getUsername() { return username; }
    public String getEnterprise() { return enterprise; }
}
