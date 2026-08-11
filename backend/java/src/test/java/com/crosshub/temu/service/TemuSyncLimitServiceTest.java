package com.crosshub.temu.service;

import com.crosshub.config.CrawlerProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TemuSyncLimitServiceTest {

    private JdbcTemplate jdbc;
    private TemuSyncLimitService service;

    @BeforeEach
    void setUp() {
        jdbc = mock(JdbcTemplate.class);
        CrawlerProperties props = new CrawlerProperties();
        props.getSyncLimit().setMaxGlobalRunning(8);
        props.getSyncLimit().setMaxEnqueuePerMinute(3);
        service = new TemuSyncLimitService(jdbc, props);
    }

    @Test
    void perUserInFlightThrows429WithChineseMsg() {
        when(jdbc.queryForObject(
                anyString(),
                eq(Long.class),
                eq(5L),
                eq(42L)
        )).thenReturn(1L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(0L);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.checkCanEnqueue(5L, 42L)
        );

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, ex.getStatusCode());
        assertEquals("您已有进行中的 Temu 同步任务，请稍后再试", ex.getReason());

        ArgumentCaptor<String> sqlCaptor = ArgumentCaptor.forClass(String.class);
        verify(jdbc).queryForObject(sqlCaptor.capture(), eq(Long.class), eq(5L), eq(42L));
        String sql = sqlCaptor.getValue().toLowerCase();
        assertTrue(sql.contains("tenant_id"), "in-flight SQL must filter by tenant_id");
        assertTrue(sql.contains("triggered_by"), "in-flight SQL must filter by triggered_by");
    }

    @Test
    void enqueueRateLimitThrows429WithChineseMsg() {
        when(jdbc.queryForObject(anyString(), eq(Long.class), eq(5L), eq(42L))).thenReturn(0L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(0L);

        service.checkCanEnqueue(5L, 42L);
        service.recordEnqueue(42L);
        service.checkCanEnqueue(5L, 42L);
        service.recordEnqueue(42L);
        service.checkCanEnqueue(5L, 42L);
        service.recordEnqueue(42L);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.checkCanEnqueue(5L, 42L)
        );

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, ex.getStatusCode());
        assertEquals("操作过于频繁，每分钟最多提交 3 次，请稍后再试", ex.getReason());
    }

    @Test
    void failedEnqueueDoesNotConsumeRateQuota() {
        when(jdbc.queryForObject(anyString(), eq(Long.class), eq(5L), eq(42L))).thenReturn(0L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(0L);

        for (int i = 0; i < 5; i++) {
            assertThrows(IllegalStateException.class, () ->
                    service.runWithEnqueueGate(5L, 42L, () -> {
                        throw new IllegalStateException("helper offline");
                    })
            );
        }

        // Still within 3/min because failures must not burn slots
        String ok = service.runWithEnqueueGate(5L, 42L, () -> "queued");
        assertEquals("queued", ok);
    }

    @Test
    void globalRunningCapThrows429WithChineseMsg() {
        when(jdbc.queryForObject(anyString(), eq(Long.class), any(), any())).thenReturn(0L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(8L);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.checkCanEnqueue(5L, 42L)
        );

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, ex.getStatusCode());
        assertEquals("系统同步任务繁忙，请稍后再试", ex.getReason());
    }

    @Test
    void runWithEnqueueGateRecordsOnlyAfterSuccess() {
        when(jdbc.queryForObject(anyString(), eq(Long.class), eq(5L), eq(42L))).thenReturn(0L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(0L);

        service.runWithEnqueueGate(5L, 42L, () -> "a");
        service.runWithEnqueueGate(5L, 42L, () -> "b");
        service.runWithEnqueueGate(5L, 42L, () -> "c");

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.runWithEnqueueGate(5L, 42L, () -> "d")
        );
        assertEquals(HttpStatus.TOO_MANY_REQUESTS, ex.getStatusCode());
        assertEquals(TemuSyncLimitService.MSG_ENQUEUE_RATE, ex.getReason());
    }
}
