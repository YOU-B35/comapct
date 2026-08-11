package com.crosshub.agent.repository;

import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class IntegrationAgentMachineBindRepoTest {

    @Test
    void repositoryDeclaresTenantFingerprintLookup() throws Exception {
        Method byTenantFp = IntegrationAgentRepository.class.getMethod(
                "findByTenantIdAndMachineFingerprint", Long.class, String.class);
        Method byTenantHb = IntegrationAgentRepository.class.getMethod(
                "findByTenantIdOrderByLastHeartbeatAtDesc", Long.class);

        assertEquals(Optional.class, byTenantFp.getReturnType());
        assertEquals(List.class, byTenantHb.getReturnType());
        assertNotNull(byTenantFp);
        assertNotNull(byTenantHb);
    }
}
