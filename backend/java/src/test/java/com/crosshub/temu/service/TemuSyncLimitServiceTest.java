package com.crosshub.temu.service;

import com.crosshub.config.CrawlerProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
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
                eq(42L)
        )).thenReturn(1L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(0L);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.checkCanEnqueue(5L, 42L)
        );

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, ex.getStatusCode());
        assertEquals("您已有进行中的 Temu 同步任务，请稍后再试", ex.getReason());
    }

    @Test
    void enqueueRateLimitThrows429WithChineseMsg() {
        when(jdbc.queryForObject(anyString(), eq(Long.class), eq(42L))).thenReturn(0L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(0L);

        service.checkCanEnqueue(5L, 42L);
        service.checkCanEnqueue(5L, 42L);
        service.checkCanEnqueue(5L, 42L);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.checkCanEnqueue(5L, 42L)
        );

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, ex.getStatusCode());
        assertEquals("操作过于频繁，每分钟最多提交 3 次，请稍后再试", ex.getReason());
    }

    @Test
    void globalRunningCapThrows429WithChineseMsg() {
        when(jdbc.queryForObject(anyString(), eq(Long.class), any())).thenReturn(0L);
        when(jdbc.queryForObject(anyString(), eq(Long.class))).thenReturn(8L);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.checkCanEnqueue(5L, 42L)
        );

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, ex.getStatusCode());
        assertEquals("系统同步任务繁忙，请稍后再试", ex.getReason());
    }
}
