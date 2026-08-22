package com.crosshub.taobao.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 淘宝/天猫工单预警实体。对齐抖音 {@code DouyinIssue}。
 */
@Entity
@Table(name = "taobao_issue")
public class TaobaoIssue {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "store_id", nullable = false)
    private String storeId = "";

    private String type = "";

    @Column(name = "type_label")
    private String typeLabel = "";

    private String sku = "";

    @Column(name = "product_name")
    private String productName = "";

    @Column(name = "product_image")
    private String productImage = "";

    private String detail = "";

    private String priority = "medium";

    private Integer resolved = 0;

    @Column(name = "reported_at")
    private String reportedAt = "";

    @Column(name = "resolved_at")
    private String resolvedAt = "";

    private String note = "";

    @Column(name = "external_id")
    private String externalId = "";

    private String source = "";

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
    public String getType() { return type; }
    public void setType(String type) { this.type = type == null ? "" : type; }
    public String getTypeLabel() { return typeLabel; }
    public void setTypeLabel(String typeLabel) { this.typeLabel = typeLabel == null ? "" : typeLabel; }
    public String getSku() { return sku; }
    public void setSku(String sku) { this.sku = sku == null ? "" : sku; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName == null ? "" : productName; }
    public String getProductImage() { return productImage; }
    public void setProductImage(String productImage) { this.productImage = productImage == null ? "" : productImage; }
    public String getDetail() { return detail; }
    public void setDetail(String detail) { this.detail = detail == null ? "" : detail; }
    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority == null || priority.isBlank() ? "medium" : priority; }
    public Integer getResolved() { return resolved; }
    public void setResolved(Integer resolved) { this.resolved = resolved == null ? 0 : resolved; }
    public String getReportedAt() { return reportedAt; }
    public void setReportedAt(String reportedAt) { this.reportedAt = reportedAt == null ? "" : reportedAt; }
    public String getResolvedAt() { return resolvedAt; }
    public void setResolvedAt(String resolvedAt) { this.resolvedAt = resolvedAt == null ? "" : resolvedAt; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note == null ? "" : note; }
    public String getExternalId() { return externalId; }
    public void setExternalId(String externalId) { this.externalId = externalId == null ? "" : externalId; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source == null ? "" : source; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt == null ? "" : createdAt; }
    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt == null ? "" : updatedAt; }
}
