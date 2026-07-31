package com.crosshub.agent.service;

import com.crosshub.temu.service.TemuAgentTasks;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentTaskConcurrencyTest {

    private final AgentTaskConcurrency.Limits limits = AgentTaskConcurrency.Limits.defaults();

    @Test
    void temuLoginUsesSingleSellerLock() {
        AgentTaskConcurrency.Requirement req = AgentTaskConcurrency.analyze(
                TemuAgentTasks.LOGIN_OPEN,
                Map.of("session_key", "acct-a"),
                5L,
                limits
        );
        assertEquals(AgentTaskConcurrency.Family.TEMU, req.family());
        assertEquals(1, req.browserSlots());
        assertEquals(Set.of("temu:seller:5:acct-a"), req.lockKeys());
    }

    @Test
    void temuCrawlMultiSessionLocksAllAndCapsSlots() {
        AgentTaskConcurrency.Requirement req = AgentTaskConcurrency.analyze(
                TemuAgentTasks.CRAWL,
                Map.of(
                        "seller_sessions", List.of(
                                Map.of("session_key", "a"),
                                Map.of("session_key", "b"),
                                Map.of("session_key", "c"),
                                Map.of("session_key", "d")
                        )
                ),
                5L,
                limits
        );
        assertEquals(3, req.browserSlots());
        assertEquals(4, req.lockKeys().size());
        assertTrue(req.lockKeys().contains("temu:seller:5:a"));
        assertTrue(req.lockKeys().contains("temu:seller:5:d"));
    }

    @Test
    void sameSessionCannotOverlapButDifferentSessionsCanWithinCap() {
        AgentTaskConcurrency.State state = new AgentTaskConcurrency.State(limits);
        AgentTaskConcurrency.Requirement a = AgentTaskConcurrency.analyze(
                TemuAgentTasks.LOGIN_OPEN, Map.of("session_key", "a"), 1L, limits
        );
        AgentTaskConcurrency.Requirement a2 = AgentTaskConcurrency.analyze(
                TemuAgentTasks.SESSION_PROBE, Map.of("session_key", "a"), 1L, limits
        );
        AgentTaskConcurrency.Requirement b = AgentTaskConcurrency.analyze(
                TemuAgentTasks.LOGIN_OPEN, Map.of("session_key", "b"), 1L, limits
        );
        AgentTaskConcurrency.Requirement c = AgentTaskConcurrency.analyze(
                TemuAgentTasks.LOGIN_OPEN, Map.of("session_key", "c"), 1L, limits
        );
        AgentTaskConcurrency.Requirement d = AgentTaskConcurrency.analyze(
                TemuAgentTasks.LOGIN_OPEN, Map.of("session_key", "d"), 1L, limits
        );

        assertTrue(state.canAdmit(a));
        state.admit(a);
        assertFalse(state.canAdmit(a2));
        assertTrue(state.canAdmit(b));
        state.admit(b);
        assertTrue(state.canAdmit(c));
        state.admit(c);
        assertFalse(state.canAdmit(d)); // Temu cap 3
    }

    @Test
    void amazonAndTemuCanRunTogetherWithinGlobalCap() {
        AgentTaskConcurrency.State state = new AgentTaskConcurrency.State(limits);
        AgentTaskConcurrency.Requirement temu = AgentTaskConcurrency.analyze(
                TemuAgentTasks.CRAWL,
                Map.of("seller_sessions", List.of(
                        Map.of("session_key", "a"),
                        Map.of("session_key", "b"),
                        Map.of("session_key", "c")
                )),
                5L,
                limits
        );
        AgentTaskConcurrency.Requirement amazon = AgentTaskConcurrency.analyze(
                AgentService.TASK_TYPE,
                Map.of("browser_id", "bz1"),
                5L,
                limits
        );
        assertTrue(state.canAdmit(temu));
        state.admit(temu);
        assertEquals(3, temu.browserSlots());
        assertTrue(state.canAdmit(amazon));
        state.admit(amazon);
        AgentTaskConcurrency.Requirement amazon2 = AgentTaskConcurrency.analyze(
                AgentService.TASK_TYPE,
                Map.of("browser_id", "bz2"),
                5L,
                limits
        );
        assertFalse(state.canAdmit(amazon2)); // Amazon cap 1
    }

    @Test
    void buyerChromeTasksShareLock() {
        AgentTaskConcurrency.State state = new AgentTaskConcurrency.State(limits);
        AgentTaskConcurrency.Requirement login = AgentTaskConcurrency.analyze(
                TemuAgentTasks.FRONTEND_LOGIN_OPEN, Map.of(), 5L, limits
        );
        AgentTaskConcurrency.Requirement discover = AgentTaskConcurrency.analyze(
                TemuAgentTasks.COMPETITOR_DISCOVER, Map.of("keyword", "x"), 5L, limits
        );
        state.admit(login);
        assertFalse(state.canAdmit(discover));
    }
}
