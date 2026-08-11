package com.crosshub.agent.repository;

import com.crosshub.agent.entity.IntegrationAgent;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface IntegrationAgentRepository extends JpaRepository<IntegrationAgent, String> {
    List<IntegrationAgent> findByTenantIdOrderByCreatedAtDesc(Long tenantId);

    Optional<IntegrationAgent> findByAgentToken(String agentToken);

    Optional<IntegrationAgent> findByIdAndTenantId(String id, Long tenantId);

    List<IntegrationAgent> findByBoundUserIdOrderByLastHeartbeatAtDesc(Long userId);

    Optional<IntegrationAgent> findByBoundUserIdAndMachineFingerprint(Long userId, String fingerprint);

    Optional<IntegrationAgent> findFirstByTenantIdAndMachineFingerprintAndStatusIgnoreCase(
            Long tenantId, String fingerprint, String status);

    /**
     * Canonical machine agent for a tenant: active row only (retired siblings may share fingerprint).
     */
    default Optional<IntegrationAgent> findByTenantIdAndMachineFingerprint(Long tenantId, String fingerprint) {
        return findFirstByTenantIdAndMachineFingerprintAndStatusIgnoreCase(tenantId, fingerprint, "active");
    }

    List<IntegrationAgent> findByTenantIdOrderByLastHeartbeatAtDesc(Long tenantId);
}
