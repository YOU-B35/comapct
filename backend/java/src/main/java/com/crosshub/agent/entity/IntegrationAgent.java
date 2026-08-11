package com.crosshub.agent.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "integration_agent")
public class IntegrationAgent {
    @Id
    private String id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(nullable = false)
    private String name;

    @Column(name = "agent_token", nullable = false)
    private String agentToken;

    @Column(nullable = false)
    private String status = "active";

    @Column(name = "last_heartbeat_at", nullable = false)
    private String lastHeartbeatAt = "";

    @Column(name = "ziniao_online", nullable = false)
    private Integer ziniaoOnline = 0;

    @Column(name = "created_at", nullable = false)
    private String createdAt;

    @Column(name = "bound_user_id")
    private Long boundUserId;

    @Column(name = "machine_fingerprint", nullable = false)
    private String machineFingerprint = "";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getAgentToken() { return agentToken; }
    public void setAgentToken(String agentToken) { this.agentToken = agentToken; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getLastHeartbeatAt() { return lastHeartbeatAt; }
    public void setLastHeartbeatAt(String lastHeartbeatAt) { this.lastHeartbeatAt = lastHeartbeatAt; }
    public Integer getZiniaoOnline() { return ziniaoOnline; }
    public void setZiniaoOnline(Integer ziniaoOnline) { this.ziniaoOnline = ziniaoOnline; }
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
    public Long getBoundUserId() { return boundUserId; }
    public void setBoundUserId(Long boundUserId) { this.boundUserId = boundUserId; }
    public String getMachineFingerprint() { return machineFingerprint; }
    public void setMachineFingerprint(String machineFingerprint) { this.machineFingerprint = machineFingerprint; }
}
