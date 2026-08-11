package com.crosshub.agent.service;

import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.repository.IntegrationAgentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AgentBindCodeServiceTest {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private MutableClock clock;
    private IntegrationAgentRepository agentRepo;
    private AgentBindCodeService svc;

    @BeforeEach
    void setUp() {
        clock = new MutableClock(Instant.parse("2026-08-11T03:00:00Z"));
        agentRepo = mock(IntegrationAgentRepository.class);
        when(agentRepo.save(any(IntegrationAgent.class))).thenAnswer(inv -> inv.getArgument(0));
        when(agentRepo.findByTenantIdAndMachineFingerprint(any(), any())).thenReturn(Optional.empty());
        svc = new AgentBindCodeService(clock, agentRepo);
    }

    @Test
    void createCodeReturnsCodeAndExpiry() {
        AgentBindCodeService.CreateCodeResult created = svc.createCode(1L, 5L);
        assertNotNull(created.code());
        assertFalse(created.code().isBlank());
        assertEquals(Instant.parse("2026-08-11T03:10:00Z"), created.expiresAt());
    }

    @Test
    void consumeCreatesBoundAgentAndReturnsToken() {
        String code = svc.createCode(1L, 5L).code();
        AgentBindCodeService.ConsumeResult result = svc.consume(code, "fp-abc", "办公电脑");

        assertNotNull(result.agentToken());
        assertFalse(result.agentToken().isBlank());
        assertEquals(5L, result.tenantId());
        assertEquals(1L, result.userId());
    }

    @Test
    void consumeFailsAfterExpiry() {
        String code = svc.createCode(1L, 5L).code();
        clock.advance(Duration.ofMinutes(11));
        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> svc.consume(code, "fp", "PC")
        );
        assertEquals("绑定码无效或已过期", ex.getReason());
    }

    @Test
    void consumeIsSingleUse() {
        String code = svc.createCode(1L, 5L).code();
        svc.consume(code, "fp", "PC");
        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> svc.consume(code, "fp", "PC")
        );
        assertEquals("绑定码无效或已过期", ex.getReason());
    }

    @Test
    void consumeUpsertsSameTenantAndFingerprint() {
        AtomicReference<IntegrationAgent> stored = new AtomicReference<>();
        when(agentRepo.save(any(IntegrationAgent.class))).thenAnswer(inv -> {
            IntegrationAgent agent = inv.getArgument(0);
            stored.set(agent);
            return agent;
        });
        when(agentRepo.findByTenantIdAndMachineFingerprint(eq(5L), eq("fp")))
                .thenAnswer(inv -> Optional.ofNullable(stored.get()));

        String code1 = svc.createCode(1L, 5L).code();
        AgentBindCodeService.ConsumeResult first = svc.consume(code1, "fp", "PC-A");
        String token1 = first.agentToken();
        String agentId = stored.get().getId();

        String code2 = svc.createCode(1L, 5L).code();
        AgentBindCodeService.ConsumeResult second = svc.consume(code2, "fp", "PC-B");

        assertEquals(agentId, stored.get().getId());
        assertNotEquals(token1, second.agentToken());
        assertEquals(5L, second.tenantId());
        assertEquals("PC-B", stored.get().getName());
        assertEquals(1L, stored.get().getBoundUserId());
        assertEquals("fp", stored.get().getMachineFingerprint());
    }

    @Test
    void consume_sameTenantSameFingerprint_reusesAgent_evenIfDifferentUser() {
        AtomicReference<IntegrationAgent> stored = new AtomicReference<>();
        when(agentRepo.save(any(IntegrationAgent.class))).thenAnswer(inv -> {
            IntegrationAgent agent = inv.getArgument(0);
            stored.set(agent);
            return agent;
        });
        when(agentRepo.findByTenantIdAndMachineFingerprint(eq(5L), eq("fp")))
                .thenAnswer(inv -> Optional.ofNullable(stored.get()));

        String code1 = svc.createCode(1L, 5L).code();
        svc.consume(code1, "fp", "PC");
        String agentId = stored.get().getId();

        String code2 = svc.createCode(2L, 5L).code();
        AgentBindCodeService.ConsumeResult second = svc.consume(code2, "fp", "PC");

        assertEquals(agentId, stored.get().getId());
        assertEquals(2L, stored.get().getBoundUserId());
        assertEquals(2L, second.userId());
        assertEquals(5L, second.tenantId());
    }

    @Test
    void statusForTenant_includesAgentsBoundByOtherUsers() {
        IntegrationAgent agent = new IntegrationAgent();
        agent.setId("a1");
        agent.setName("本机助手");
        agent.setMachineFingerprint("fp");
        agent.setBoundUserId(1L);
        agent.setTenantId(5L);
        agent.setStatus("active");
        agent.setLastHeartbeatAt(LocalDateTime.now(clock).format(TS));

        when(agentRepo.findByTenantIdOrderByLastHeartbeatAtDesc(5L)).thenReturn(List.of(agent));

        Map<String, Object> status = svc.statusForTenant(5L);
        assertEquals(true, status.get("online"));
        assertEquals("a1", status.get("recommended_agent_id"));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> agents = (List<Map<String, Object>>) status.get("agents");
        assertEquals(1, agents.size());
        assertEquals(true, agents.get(0).get("online"));
    }

    @Test
    void consumeUsesDefaultDisplayNameWhenBlank() {
        AtomicReference<IntegrationAgent> stored = new AtomicReference<>();
        when(agentRepo.save(any(IntegrationAgent.class))).thenAnswer(inv -> {
            IntegrationAgent agent = inv.getArgument(0);
            stored.set(agent);
            return agent;
        });

        String code = svc.createCode(1L, 5L).code();
        svc.consume(code, "fp", "  ");
        assertEquals("本机助手", stored.get().getName());
    }

    @Test
    void consumeRejectsUnknownCode() {
        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> svc.consume("no-such-code", "fp", "PC")
        );
        assertEquals("绑定码无效或已过期", ex.getReason());
    }

    /** Test clock with advance(); production uses java.time.Clock. */
    static final class MutableClock extends Clock {
        private Instant instant;
        private final ZoneOffset zone = ZoneOffset.UTC;

        MutableClock(Instant instant) {
            this.instant = instant;
        }

        void advance(Duration duration) {
            instant = instant.plus(duration);
        }

        @Override
        public ZoneOffset getZone() {
            return zone;
        }

        @Override
        public Clock withZone(java.time.ZoneId zone) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Instant instant() {
            return instant;
        }
    }
}
