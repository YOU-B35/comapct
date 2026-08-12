package com.crosshub.tenant.team.impl;

import com.crosshub.security.AuthContext;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TeamScopeServiceImplTest {
    @Mock JdbcTemplate jdbc;
    @Mock AuthContext authContext;

    TeamScopeServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new TeamScopeServiceImpl(jdbc, authContext);
    }

    @Test
    void assertCanManageUser_bossPasses() {
        when(authContext.isBossPortal()).thenReturn(true);
        when(authContext.isAdmin()).thenReturn(true);
        assertDoesNotThrow(() -> service.assertCanManageUser(5L, 1L, 99L));
    }

    @Test
    void assertCanManageUser_leaderOnlyOwnMembers() {
        when(authContext.isBossPortal()).thenReturn(false);
        when(jdbc.query(anyString(), any(RowMapper.class), eq(5L), eq(10L)))
                .thenReturn(List.of(Map.of(
                        "id", 3L,
                        "tenantId", 5L,
                        "name", "一组",
                        "leaderUserId", 10L,
                        "status", "active"
                )));
        when(jdbc.queryForObject(anyString(), eq(Integer.class), eq(3L), eq(20L))).thenReturn(1);
        assertDoesNotThrow(() -> service.assertCanManageUser(5L, 10L, 20L));

        when(jdbc.queryForObject(anyString(), eq(Integer.class), eq(3L), eq(21L))).thenReturn(0);
        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.assertCanManageUser(5L, 10L, 21L)
        );
        assertTrue(ex.getReason().contains("管辖范围"));
    }
}
