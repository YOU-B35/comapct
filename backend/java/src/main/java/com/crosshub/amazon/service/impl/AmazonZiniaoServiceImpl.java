package com.crosshub.amazon.service.impl;

import com.crosshub.amazon.dto.ZiniaoBindRequest;
import com.crosshub.amazon.service.AmazonZiniaoService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.platform.dto.StorePayload;
import com.crosshub.platform.service.PlatformAccountService;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
public class AmazonZiniaoServiceImpl implements AmazonZiniaoService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final String TASK_TYPE = "ziniao_discover";

    private final DataScopeService dataScopeService;
    private final JdbcTemplate jdbc;
    private final PlatformAccountService platformAccountService;
    private final ObjectMapper objectMapper;

    public AmazonZiniaoServiceImpl(
            DataScopeService dataScopeService,
            JdbcTemplate jdbc,
            PlatformAccountService platformAccountService,
            ObjectMapper objectMapper
    ) {
        this.dataScopeService = dataScopeService;
        this.jdbc = jdbc;
        this.platformAccountService = platformAccountService;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> triggerDiscover() {
        Long tenantId = dataScopeService.requireTenantId();
        String jobId = "zn_discover_" + UUID.randomUUID();
        jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, agent_id, task_type, status, payload_json, result_json,
                  error_code, error_message, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                jobId, tenantId, "", TASK_TYPE, "pending", "{}", "{}", "", "", now(), "", ""
        );
        return Map.of("job_id", jobId, "status", "pending");
    }

    public Map<String, Object> getDiscoverJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        List<Map<String, Object>> rows = jdbc.query(
                """
                SELECT status, error_code, error_message, result_json
                FROM agent_task
                WHERE id = ? AND tenant_id = ?
                LIMIT 1
                """,
                (rs, rn) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("status", rs.getString("status"));
                    row.put("error_code", rs.getString("error_code") == null ? "" : rs.getString("error_code"));
                    row.put("error_message", rs.getString("error_message") == null ? "" : rs.getString("error_message"));
                    row.put("result_json", rs.getString("result_json") == null ? "{}" : rs.getString("result_json"));
                    return row;
                },
                jobId, tenantId
        );
        if (rows.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.AMAZON_SYNC_JOB_NOT_FOUND.getUserMessage());
        }
        Map<String, Object> row = rows.get(0);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("job_id", jobId);
        out.put("status", row.get("status"));
        out.put("error_code", row.get("error_code"));
        out.put("error_message", row.get("error_message"));
        out.put("stores", parseStores(row.get("result_json")));
        return out;
    }

    public List<Map<String, Object>> listCandidates() {
        Long tenantId = dataScopeService.requireTenantId();
        List<String> resultJsonRows = jdbc.query(
                """
                SELECT result_json
                FROM agent_task
                WHERE tenant_id = ?
                  AND task_type IN ('ziniao_discover', 'amazon_ziniao_discover')
                  AND status = 'success'
                ORDER BY finished_at DESC
                LIMIT 1
                """,
                (rs, rn) -> rs.getString("result_json"),
                tenantId
        );
        if (resultJsonRows.isEmpty()) {
            return List.of();
        }
        return parseStores(resultJsonRows.get(0));
    }

    public List<Map<String, Object>> bindStores(ZiniaoBindRequest request) {
        if (request == null || request.stores() == null || request.stores().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.ACCOUNT_BATCH_EMPTY.getUserMessage());
        }
        List<Map<String, Object>> out = new ArrayList<>();
        for (ZiniaoBindRequest.StoreCandidate x : request.stores()) {
            String browserId = x.browserId() == null ? "" : x.browserId().trim();
            String cliStoreId = x.ziniaoStoreId() == null ? "" : x.ziniaoStoreId().trim();
            if (browserId.isBlank() && cliStoreId.isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "紫鸟 browserId 或 storeId 不能为空");
            }
            String storeName = firstNonBlank(x.browserName(), x.storeUsername(), "Amazon店铺" + System.currentTimeMillis());
            String account = firstNonBlank(x.storeUsername(), browserId, cliStoreId, storeName);
            out.add(platformAccountService.upsert(new StorePayload(
                    null,
                    "amazon",
                    storeName,
                    account,
                    "",
                    "",
                    browserId,
                    cliStoreId.isBlank() ? "ziniao" : "ziniao_cli",
                    x.browserOauth() == null ? "" : x.browserOauth().trim(),
                    cliStoreId
            )));
        }
        return out;
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> parseStores(Object rawJson) {
        if (rawJson == null) {
            return List.of();
        }
        try {
            Map<String, Object> parsed = objectMapper.readValue(String.valueOf(rawJson), new TypeReference<>() {});
            Object stores = parsed.get("stores");
            if (!(stores instanceof List<?> list)) {
                return List.of();
            }
            List<Map<String, Object>> out = new ArrayList<>();
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (Map.Entry<?, ?> entry : map.entrySet()) {
                        row.put(String.valueOf(entry.getKey()), entry.getValue());
                    }
                    out.add(row);
                }
            }
            return out;
        } catch (Exception ex) {
            return List.of();
        }
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }

    private String firstNonBlank(String... values) {
        if (values == null) {
            return "";
        }
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value.trim();
            }
        }
        return "";
    }
}
