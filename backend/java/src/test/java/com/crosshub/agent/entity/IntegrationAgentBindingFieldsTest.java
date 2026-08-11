package com.crosshub.agent.entity;

import com.crosshub.agent.repository.IntegrationAgentRepository;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class IntegrationAgentBindingFieldsTest {

    @Test
    void entityExposesBoundUserIdAndFingerprint() {
        IntegrationAgent a = new IntegrationAgent();
        a.setBoundUserId(42L);
        a.setMachineFingerprint("fp-abc");
        assertEquals(42L, a.getBoundUserId());
        assertEquals("fp-abc", a.getMachineFingerprint());
    }

    @Test
    void repositoryExposesBoundUserQueryMethods() throws Exception {
        Method byUser = IntegrationAgentRepository.class.getMethod(
                "findByBoundUserIdOrderByLastHeartbeatAtDesc", Long.class);
        Method byUserAndFp = IntegrationAgentRepository.class.getMethod(
                "findByBoundUserIdAndMachineFingerprint", Long.class, String.class);

        assertEquals(List.class, byUser.getReturnType());
        assertEquals(Optional.class, byUserAndFp.getReturnType());
        assertNotNull(byUser);
        assertNotNull(byUserAndFp);
    }
}
