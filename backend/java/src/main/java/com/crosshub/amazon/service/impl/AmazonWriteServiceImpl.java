package com.crosshub.amazon.service.impl;

import com.crosshub.amazon.entity.AmazonOperationalItem;
import com.crosshub.amazon.entity.AmazonWriteJob;
import com.crosshub.amazon.repository.AmazonOperationalItemRepository;
import com.crosshub.amazon.repository.AmazonWriteJobRepository;
import com.crosshub.amazon.service.AmazonWriteService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
public class AmazonWriteServiceImpl implements AmazonWriteService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> ACTIVE_JOB = Set.of("pending", "running");

    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final AmazonOperationalItemRepository operationalItemRepository;
    private final AmazonWriteJobRepository writeJobRepository;
    private final PlatformAccountRepository platformAccountRepository;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public AmazonWriteServiceImpl(
            DataScopeService dataScopeService,
            AuthContext authContext,
            AmazonOperationalItemRepository operationalItemRepository,
            AmazonWriteJobRepository writeJobRepository,
            PlatformAccountRepository platformAccountRepository,
            JdbcTemplate jdbc,
            ObjectMapper objectMapper
    ) {
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.operationalItemRepository = operationalItemRepository;
        this.writeJobRepository = writeJobRepository;
        this.platformAccountRepository = platformAccountRepository;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    @Override
    @Transactional
    public Map<String, Object> replyMessage(String id, String templateId, String note) {
        Map<String, Object> request = new LinkedHashMap<>();
        request.put("template_id", templateId == null ? "" : templateId);
        request.put("note", note == null ? "" : note);
        return enqueueWrite(id, "buyer_message", "buyer_message_reply", request, "replied");
    }

    @Override
    @Transactional
    public Map<String, Object> handleReview(String id, String note) {
        Map<String, Object> request = new LinkedHashMap<>();
        request.put("note", note == null ? "" : note);
        return enqueueWrite(id, "review", "review_handle", request, "handled");
    }

    @Override
    @Transactional
    public Map<String, Object> acknowledgeCase(String id, String note) {
        Map<String, Object> request = new LinkedHashMap<>();
        request.put("note", note == null ? "" : note);
        return enqueueWrite(id, "case", "case_ack", request, "read");
    }

    @Override
    @Transactional
    public Map<String, Object> shipOutbound(String id, String trackingNo) {
        if (trackingNo == null || trackingNo.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "运单号不能为空");
        }
        Long tenantId = dataScopeService.requireTenantId();
        AmazonOperationalItem item = requireItem(id, "outbound_order", tenantId);
        Map<String, Object> payload = payload(item);
        String fulfillmentType = text(payload.get("fulfillment_type"));
        if (fulfillmentType.isBlank()) {
            fulfillmentType = text(payload.get("fulfillmentType"));
        }
        if ("fba".equalsIgnoreCase(fulfillmentType) || "amazon".equalsIgnoreCase(fulfillmentType)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "FBA 订单由亚马逊履约，无需确认发货"
            );
        }
        Map<String, Object> request = new LinkedHashMap<>();
        request.put("tracking_no", trackingNo.trim());
        return enqueueWrite(id, "outbound_order", "outbound_ship", request, "shipped");
    }

    @Override
    public Map<String, Object> getWriteJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        AmazonWriteJob job = writeJobRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        AppErrorCode.AMAZON_WRITE_JOB_NOT_FOUND.getUserMessage()
                ));
        return toJobDto(job);
    }

    @Override
    public List<Map<String, Object>> listWriteAudit(String itemId, int limit) {
        Long tenantId = dataScopeService.requireTenantId();
        int safeLimit = Math.min(Math.max(limit, 1), 100);
        if (isBlank(itemId)) {
            return jdbc.query(
                    """
                    SELECT id, write_job_id, platform_account_id, item_id, action, status,
                           initiated_by_user_id, initiated_by_name, error_code, error_message, created_at
                    FROM amazon_write_audit
                    WHERE tenant_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (rs, rowNum) -> auditRow(rs),
                    tenantId,
                    safeLimit
            );
        }
        return jdbc.query(
                """
                SELECT id, write_job_id, platform_account_id, item_id, action, status,
                       initiated_by_user_id, initiated_by_name, error_code, error_message, created_at
                FROM amazon_write_audit
                WHERE tenant_id = ? AND item_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (rs, rowNum) -> auditRow(rs),
                tenantId,
                itemId,
                safeLimit
        );
    }

    @Override
    @Transactional
    public void onAgentTaskStarted(String agentTaskId) {
        writeJobRepository.findFirstByAgentTaskId(agentTaskId).ifPresent(job -> {
            if ("pending".equals(job.getStatus())) {
                job.setStatus("running");
                writeJobRepository.save(job);
            }
        });
    }

    @Override
    @Transactional
    public void onAgentTaskCompleted(
            String agentTaskId,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        AmazonWriteJob job = writeJobRepository.findFirstByAgentTaskId(agentTaskId).orElse(null);
        if (job == null) {
            return;
        }
        String normalized = status == null ? "failed" : status.trim().toLowerCase(Locale.ROOT);
        job.setFinishedAt(now());
        job.setResultJson(json(result == null ? Map.of() : result));
        if ("success".equals(normalized)) {
            job.setStatus("success");
            job.setErrorCode("");
            job.setErrorMessage("");
            applySuccess(job);
        } else {
            job.setStatus("failed");
            job.setErrorCode(errorCode == null ? AppErrorCode.AMAZON_WRITE_FAILED.getCode() : errorCode);
            job.setErrorMessage(errorMessage == null ? AppErrorCode.AMAZON_WRITE_FAILED.getUserMessage() : errorMessage);
            revertPending(job);
        }
        writeJobRepository.save(job);
        insertWriteAudit(job);
    }

    private Map<String, Object> enqueueWrite(
            String itemId,
            String itemType,
            String action,
            Map<String, Object> request,
            String successStatus
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        AmazonOperationalItem item = requireItem(itemId, itemType, tenantId);
        assertNoActiveBrowserTask(tenantId, item.getPlatformAccountId());

        PlatformAccount account = platformAccountRepository.findByIdAndTenantId(item.getPlatformAccountId(), tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.ACCOUNT_NOT_FOUND.getUserMessage()));

        String writeJobId = "amz_write_" + UUID.randomUUID();
        String agentTaskId = "agt_" + UUID.randomUUID();

        Map<String, Object> payload = payload(item);
        payload.put("status", "pending_write");
        payload.put("write_job_id", writeJobId);
        payload.put("write_action", action);
        payload.put("target_status", successStatus);
        item.setPayloadJson(json(payload));
        item.setSyncedAt(now());
        operationalItemRepository.save(item);

        AmazonWriteJob job = new AmazonWriteJob();
        job.setId(writeJobId);
        job.setTenantId(tenantId);
        job.setPlatformAccountId(item.getPlatformAccountId());
        job.setAgentTaskId(agentTaskId);
        job.setItemId(itemId);
        job.setAction(action);
        job.setStatus("pending");
        job.setRequestJson(json(request));
        job.setResultJson("{}");
        job.setErrorCode("");
        job.setErrorMessage("");
        job.setCreatedAt(now());
        job.setFinishedAt("");
        Long userId = authContext.userId();
        job.setInitiatedByUserId(userId);
        job.setInitiatedByName(resolveInitiatorName(userId));
        writeJobRepository.save(job);

        Map<String, Object> agentPayload = buildAgentPayload(item, account, action, request, writeJobId);
        jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, agent_id, task_type, status, payload_json, result_json,
                  error_code, error_message, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                agentTaskId,
                tenantId,
                "",
                WRITE_TASK_TYPE,
                "pending",
                json(agentPayload),
                "{}",
                "",
                "",
                now(),
                "",
                ""
        );

        Map<String, Object> response = new LinkedHashMap<>(payload);
        response.put("write_job_id", writeJobId);
        response.put("write_status", "pending");
        return response;
    }

    private Map<String, Object> buildAgentPayload(
            AmazonOperationalItem item,
            PlatformAccount account,
            String action,
            Map<String, Object> request,
            String writeJobId
    ) {
        Map<String, Object> payload = new LinkedHashMap<>(payload(item));
        payload.put("action", action);
        payload.put("write_job_id", writeJobId);
        payload.put("item_id", item.getId());
        payload.put("item_type", item.getItemType());
        payload.put("platform_account_id", item.getPlatformAccountId());
        payload.put("external_shop_id", text(account.getExternalShopId()));
        payload.put("browser_id", text(account.getExternalShopId()));
        payload.put("browser_oauth", text(account.getZiniaoBrowserOauth()));
        payload.put("store_name", text(account.getStoreName()));
        payload.put("request", request);
        return payload;
    }

    private void applySuccess(AmazonWriteJob job) {
        AmazonOperationalItem item = operationalItemRepository.findById(job.getItemId()).orElse(null);
        if (item == null) {
            return;
        }
        Map<String, Object> payload = payload(item);
        String targetStatus = text(payload.get("target_status"));
        if (targetStatus.isBlank()) {
            targetStatus = defaultSuccessStatus(job.getAction());
        }
        payload.put("status", targetStatus);
        payload.put("platform_confirmed", true);
        payload.put("platform_confirmed_at", now());
        payload.remove("write_action");
        payload.remove("target_status");

        Map<String, Object> request = readMap(job.getRequestJson());
        if ("buyer_message_reply".equals(job.getAction())) {
            payload.put("template_used", text(request.get("template_id")));
            payload.put("reply_note", text(request.get("note")));
            payload.put("replied_at", now());
        } else if ("review_handle".equals(job.getAction())) {
            payload.put("note", text(request.get("note")));
            payload.put("handled_at", now());
        } else if ("case_ack".equals(job.getAction())) {
            payload.put("note", text(request.get("note")));
            payload.put("read_at", now());
        } else if ("outbound_ship".equals(job.getAction())) {
            payload.put("tracking_no", text(request.get("tracking_no")));
            payload.put("shipped_at", now());
        }
        item.setPayloadJson(json(payload));
        item.setSyncedAt(now());
        operationalItemRepository.save(item);
    }

    private void revertPending(AmazonWriteJob job) {
        AmazonOperationalItem item = operationalItemRepository.findById(job.getItemId()).orElse(null);
        if (item == null) {
            return;
        }
        Map<String, Object> payload = payload(item);
        payload.put("status", revertStatus(job.getAction()));
        payload.put("write_error_code", job.getErrorCode());
        payload.put("write_error_message", job.getErrorMessage());
        payload.remove("write_action");
        payload.remove("target_status");
        item.setPayloadJson(json(payload));
        operationalItemRepository.save(item);
    }

    private String defaultSuccessStatus(String action) {
        return switch (action) {
            case "buyer_message_reply" -> "replied";
            case "review_handle" -> "handled";
            case "case_ack" -> "read";
            case "outbound_ship" -> "shipped";
            default -> "done";
        };
    }

    private String revertStatus(String action) {
        return switch (action) {
            case "buyer_message_reply" -> "pending";
            case "review_handle" -> "pending";
            case "case_ack" -> "pending";
            case "outbound_ship" -> "pending";
            default -> "pending";
        };
    }

    private void assertNoActiveBrowserTask(Long tenantId, String platformAccountId) {
        Integer syncJobs = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM amazon_sync_job
                WHERE tenant_id = ? AND platform_account_id = ? AND status IN ('pending', 'running')
                """,
                Integer.class,
                tenantId,
                platformAccountId
        );
        if (syncJobs != null && syncJobs > 0) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    AppErrorCode.AMAZON_SYNC_IN_PROGRESS.getUserMessage()
            );
        }
        List<AmazonWriteJob> activeWrites = writeJobRepository.findByTenantIdAndPlatformAccountIdAndStatusIn(
                tenantId,
                platformAccountId,
                List.copyOf(ACTIVE_JOB)
        );
        if (!activeWrites.isEmpty()) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    AppErrorCode.AMAZON_WRITE_IN_PROGRESS.getUserMessage()
            );
        }
        Integer activeAgentTasks = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM agent_task
                WHERE tenant_id = ? AND task_type IN ('amazon_sync', 'amazon_write') AND status IN ('pending', 'running')
                """,
                Integer.class,
                tenantId
        );
        if (activeAgentTasks != null && activeAgentTasks > 0) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    AppErrorCode.AMAZON_WRITE_IN_PROGRESS.getUserMessage()
            );
        }
    }

    private AmazonOperationalItem requireItem(String id, String type, Long tenantId) {
        return operationalItemRepository.findById(id)
                .filter(item -> tenantId.equals(item.getTenantId()) && type.equals(item.getItemType()))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "资源不存在"));
    }

    private Map<String, Object> toJobDto(AmazonWriteJob job) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("write_job_id", job.getId());
        row.put("job_id", job.getId());
        row.put("item_id", job.getItemId());
        row.put("action", job.getAction());
        row.put("status", job.getStatus());
        row.put("error_code", job.getErrorCode());
        row.put("error_message", job.getErrorMessage());
        row.put("created_at", job.getCreatedAt());
        row.put("finished_at", job.getFinishedAt());
        row.put("initiated_by_user_id", job.getInitiatedByUserId());
        row.put("initiated_by_name", job.getInitiatedByName());
        try {
            row.put("result", objectMapper.readValue(job.getResultJson(), new TypeReference<Map<String, Object>>() {}));
        } catch (Exception ex) {
            row.put("result", Map.of());
        }
        return row;
    }

    private Map<String, Object> payload(AmazonOperationalItem item) {
        try {
            return objectMapper.readValue(item.getPayloadJson(), new TypeReference<Map<String, Object>>() {});
        } catch (Exception ex) {
            return new LinkedHashMap<>();
        }
    }

    private Map<String, Object> readMap(String jsonText) {
        try {
            return objectMapper.readValue(jsonText == null || jsonText.isBlank() ? "{}" : jsonText, new TypeReference<>() {});
        } catch (Exception ex) {
            return new LinkedHashMap<>();
        }
    }

    private String json(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            return "{}";
        }
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }

    private Map<String, Object> auditRow(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", rs.getString("id"));
        row.put("write_job_id", rs.getString("write_job_id"));
        row.put("platform_account_id", rs.getString("platform_account_id"));
        row.put("item_id", rs.getString("item_id"));
        row.put("action", rs.getString("action"));
        row.put("status", rs.getString("status"));
        row.put("initiated_by_user_id", rs.getObject("initiated_by_user_id"));
        row.put("initiated_by_name", rs.getString("initiated_by_name"));
        row.put("error_code", rs.getString("error_code"));
        row.put("error_message", rs.getString("error_message"));
        row.put("created_at", rs.getString("created_at"));
        return row;
    }

    private void insertWriteAudit(AmazonWriteJob job) {
        jdbc.update(
                """
                INSERT INTO amazon_write_audit (
                  id, tenant_id, write_job_id, platform_account_id, item_id, action, status,
                  initiated_by_user_id, initiated_by_name, request_json, result_json,
                  error_code, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                "amz_audit_" + UUID.randomUUID(),
                job.getTenantId(),
                job.getId(),
                job.getPlatformAccountId(),
                job.getItemId(),
                job.getAction(),
                job.getStatus(),
                job.getInitiatedByUserId(),
                text(job.getInitiatedByName()),
                job.getRequestJson(),
                job.getResultJson(),
                text(job.getErrorCode()),
                text(job.getErrorMessage()),
                text(job.getFinishedAt()).isBlank() ? now() : job.getFinishedAt()
        );
    }

    private String resolveInitiatorName(Long userId) {
        if (userId == null) {
            return "系统";
        }
        return jdbc.query(
                "SELECT nickname FROM app_user WHERE id = ? LIMIT 1",
                rs -> rs.next() ? text(rs.getString(1)) : "用户",
                userId
        );
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
