package com.crosshub.platform.entity;

import jakarta.persistence.*;

@Entity
@Table(
        name = "platform_account",
        uniqueConstraints = @UniqueConstraint(columnNames = {"tenant_id", "platform", "store_name"})
)
public class PlatformAccount {
    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(nullable = false, length = 32)
    private String platform;

    @Column(name = "store_name", nullable = false)
    private String storeName;

    @Column(nullable = false)
    private String account;

    @Column(nullable = false, columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String password = "";

    @Column(name = "company_name", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String companyName = "";

    @Column(name = "bound_at", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String boundAt = "";

    @Column(name = "external_shop_id", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String externalShopId = "";

    @Column(name = "integration_mode", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String integrationMode = "";

    @Column(name = "ziniao_browser_oauth", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String ziniaoBrowserOauth = "";

    @Column(name = "ziniao_cli_store_id", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String ziniaoCliStoreId = "";

    @Column(name = "agent_node_id", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String agentNodeId = "";

    @Column(name = "amazon_merchant_id", columnDefinition = "TEXT NOT NULL DEFAULT ''")
    private String amazonMerchantId = "";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getPlatform() { return platform; }
    public void setPlatform(String platform) { this.platform = platform; }
    public String getStoreName() { return storeName; }
    public void setStoreName(String storeName) { this.storeName = storeName; }
    public String getAccount() { return account; }
    public void setAccount(String account) { this.account = account; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
    public String getCompanyName() { return companyName; }
    public void setCompanyName(String companyName) { this.companyName = companyName; }
    public String getBoundAt() { return boundAt; }
    public void setBoundAt(String boundAt) { this.boundAt = boundAt; }
    public String getExternalShopId() { return externalShopId; }
    public void setExternalShopId(String externalShopId) { this.externalShopId = externalShopId == null ? "" : externalShopId; }
    public String getIntegrationMode() { return integrationMode; }
    public void setIntegrationMode(String integrationMode) { this.integrationMode = integrationMode == null ? "" : integrationMode; }
    public String getZiniaoBrowserOauth() { return ziniaoBrowserOauth; }
    public void setZiniaoBrowserOauth(String ziniaoBrowserOauth) { this.ziniaoBrowserOauth = ziniaoBrowserOauth == null ? "" : ziniaoBrowserOauth; }
    public String getZiniaoCliStoreId() { return ziniaoCliStoreId; }
    public void setZiniaoCliStoreId(String ziniaoCliStoreId) { this.ziniaoCliStoreId = ziniaoCliStoreId == null ? "" : ziniaoCliStoreId; }
    public String getAgentNodeId() { return agentNodeId; }
    public void setAgentNodeId(String agentNodeId) { this.agentNodeId = agentNodeId == null ? "" : agentNodeId; }
    public String getAmazonMerchantId() { return amazonMerchantId; }
    public void setAmazonMerchantId(String amazonMerchantId) { this.amazonMerchantId = amazonMerchantId == null ? "" : amazonMerchantId; }
}
