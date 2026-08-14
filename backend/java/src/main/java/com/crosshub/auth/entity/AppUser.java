package com.crosshub.auth.entity;

import com.crosshub.auth.PortalPer;
import jakarta.persistence.*;

@Entity
@Table(
        name = "app_user",
        uniqueConstraints = @UniqueConstraint(columnNames = {"tenant_id", "username"})
)
public class AppUser {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id")
    private Long tenantId;

    private String username;
    private String password;
    private String nickname;
    private String enterprise;

    @Column(name = "job_title")
    private String jobTitle;

    private String role;

    private String phone;

    @Column(name = "other_role")
    private String otherRole = "";

    @Column(name = "status")
    private String status;

    @Column(name = "created_at")
    private String createdAt;

    public Long getId() { return id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
    public String getNickname() { return nickname; }
    public void setNickname(String nickname) { this.nickname = nickname; }
    public String getEnterprise() { return enterprise; }
    public void setEnterprise(String enterprise) { this.enterprise = enterprise; }
    public String getJobTitle() { return jobTitle; }
    public void setJobTitle(String jobTitle) { this.jobTitle = jobTitle; }
    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
    public String getPhone() { return phone; }
    public void setPhone(String phone) { this.phone = phone; }
    public String getOtherRole() { return otherRole; }
    public void setOtherRole(String otherRole) { this.otherRole = otherRole; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
    public boolean isAdmin() { return "admin".equalsIgnoreCase(role); }
    public boolean isWarehouse() { return "warehouse".equalsIgnoreCase(role); }

    /** 端口权限码：0=boss，1=员工，2=仓库（由 role 推导，与登录页选项卡对齐）。 */
    public String getPer() {
        return PortalPer.fromRole(role);
    }

    public boolean isActive() {
        return status == null || status.isBlank() || "active".equalsIgnoreCase(status);
    }
}
