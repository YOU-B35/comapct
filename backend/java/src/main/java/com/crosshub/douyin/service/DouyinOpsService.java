package com.crosshub.douyin.service;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.douyin.entity.DouyinCompassProductRank;
import com.crosshub.douyin.entity.DouyinCompassSnapshot;
import com.crosshub.douyin.entity.DouyinIssue;
import com.crosshub.douyin.entity.DouyinOpportunityProduct;
import com.crosshub.douyin.entity.DouyinOrder;
import com.crosshub.douyin.entity.DouyinProduct;
import com.crosshub.douyin.entity.DouyinSyncJob;
import com.crosshub.douyin.repository.DouyinCompassProductRankRepository;
import com.crosshub.douyin.repository.DouyinCompassSnapshotRepository;
import com.crosshub.douyin.repository.DouyinIssueRepository;
import com.crosshub.douyin.repository.DouyinOpportunityProductRepository;
import com.crosshub.douyin.repository.DouyinOrderRepository;
import com.crosshub.douyin.repository.DouyinProductRepository;
import com.crosshub.douyin.repository.DouyinSyncJobRepository;
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

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class DouyinOpsService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");

    private final DouyinOrderRepository orderRepository;
    private final DouyinProductRepository productRepository;
    private final DouyinIssueRepository issueRepository;
    private final DouyinCompassSnapshotRepository compassSnapshotRepository;
    private final DouyinCompassProductRankRepository compassProductRankRepository;
    private final DouyinOpportunityProductRepository opportunityProductRepository;
    private final DouyinSyncJobRepository syncJobRepository;
    private final PlatformAccountRepository platformAccountRepository;
    private final AgentPresenceService agentPresenceService;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public DouyinOpsService(
            DouyinOrderRepository orderRepository,
            DouyinProductRepository productRepository,
            DouyinIssueRepository issueRepository,
            DouyinCompassSnapshotRepository compassSnapshotRepository,
            DouyinCompassProductRankRepository compassProductRankRepository,
            DouyinOpportunityProductRepository opportunityProductRepository,
            DouyinSyncJobRepository syncJobRepository,
            PlatformAccountRepository platformAccountRepository,
            AgentPresenceService agentPresenceService,
            DataScopeService dataScopeService,
            AuthContext authContext,
            JdbcTemplate jdbc,
            ObjectMapper objectMapper
    ) {
        this.orderRepository = orderRepository;
        this.productRepository = productRepository;
        this.issueRepository = issueRepository;
        this.compassSnapshotRepository = compassSnapshotRepository;
        this.compassProductRankRepository = compassProductRankRepository;
        this.opportunityProductRepository = opportunityProductRepository;
        this.syncJobRepository = syncJobRepository;
        this.platformAccountRepository = platformAccountRepository;
        this.agentPresenceService = agentPresenceService;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> session() {
        Long tenantId = dataScopeService.requireTenantId();
        boolean agentOnline = agentPresenceService.isAgentOnline(tenantId);
        boolean profileBusy = hasRunningBusy(tenantId);
        Map<String, Object> snapshot = readSessionSnapshot(tenantId);
        boolean loggedIn = Boolean.TRUE.equals(snapshot.get("logged_in")) || Boolean.TRUE.equals(snapshot.get("ready"));
        Map<String, Object> out = new LinkedHashMap<>(snapshot);
        out.put("tenant_id", tenantId);
        out.put("agent_online", agentOnline);
        out.put("profile_busy", profileBusy || Boolean.TRUE.equals(snapshot.get("profile_busy")));
        out.put("logged_in", loggedIn);
        out.put("ready", loggedIn && agentOnline && !profileBusy);
        out.putIfAbsent("requires_auth", !loggedIn);
        if (!agentOnline) {
            out.put("message", AppErrorCode.DY_AGENT_OFFLINE.getUserMessage());
            out.put("requires_auth", true);
            out.put("ready", false);
        } else if (profileBusy) {
            out.putIfAbsent("message", "抖音浏览器任务进行中，请稍候");
        } else if (!loggedIn) {
            out.putIfAbsent("message", "请打开登录窗口完成抖店商家后台登录");
        }
        List<PlatformAccount> shops = platformAccountRepository.findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "douyin");
        out.put("shop_count", shops.size());
        List<Map<String, Object>> shopRows = new ArrayList<>();
        for (PlatformAccount shop : shops) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", shop.getId());
            row.put("store_name", shop.getStoreName());
            row.put("external_shop_id", shop.getExternalShopId() == null ? "" : shop.getExternalShopId());
            shopRows.add(row);
        }
        out.put("shops", shopRows);
        return out;
    }

    @Transactional
    public Map<String, Object> enqueueLoginOpen() {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        reclaimStaleBusyTasks(tenantId, agent.getId());
        if (hasRunningBusy(tenantId)) {
            return Map.of(
                    "already_open", true,
                    "queued", false,
                    "message", "抖音浏览器任务进行中；若本机没有弹出登录窗口，请重启 Sync Helper 后再点「打开登录」"
            );
        }
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        insertAgentTask(tenantId, taskId, DouyinAgentTasks.LOGIN_OPEN, payload, agent.getId());
        writeSessionSnapshot(tenantId, Map.of(
                "tenant_id", tenantId,
                "ready", false,
                "logged_in", false,
                "requires_auth", true,
                "profile_busy", true,
                "message", "登录窗口已打开，请在弹出的浏览器中完成抖店登录"
        ));
        return Map.of(
                "queued", true,
                "task_id", taskId,
                "message", "已通知本机助手打开抖店登录窗口"
        );
    }

    @Transactional
    public Map<String, Object> enqueueSessionProbe() {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        reclaimStaleBusyTasks(tenantId, agent.getId());
        if (hasRunningBusy(tenantId)) {
            return Map.of(
                    "queued", false,
                    "message", "抖音浏览器任务进行中，请稍候再刷新登录状态"
            );
        }
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        insertAgentTask(tenantId, taskId, DouyinAgentTasks.SESSION_PROBE, payload, agent.getId());
        writeSessionSnapshot(tenantId, Map.of(
                "tenant_id", tenantId,
                "ready", false,
                "logged_in", false,
                "requires_auth", true,
                "profile_busy", true,
                "message", "正在检测抖店登录状态…"
        ));
        return Map.of(
                "queued", true,
                "task_id", taskId,
                "message", "已通知本机助手检测抖店登录状态"
        );
    }

    @Transactional
    public Map<String, Object> enqueueSync(String scope, boolean force, String storeId) {
        return enqueueSync(scope, force, storeId, null, null, null, null);
    }

    @Transactional
    public Map<String, Object> enqueueSync(
            String scope,
            boolean force,
            String storeId,
            String categoryQuery,
            String categoryId
    ) {
        return enqueueSync(scope, force, storeId, categoryQuery, categoryId, null, null);
    }

    @Transactional
    public Map<String, Object> enqueueSync(
            String scope,
            boolean force,
            String storeId,
            String categoryQuery,
            String categoryId,
            String pool,
            String sortField
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        String normalizedScope = normalizeScope(scope);
        if (!"orders".equals(normalizedScope)
                && !"products".equals(normalizedScope)
                && !"compass".equals(normalizedScope)
                && !"compass_product_rank".equals(normalizedScope)
                && !"opportunity".equals(normalizedScope)
                && !"all".equals(normalizedScope)
                && !"issues".equals(normalizedScope)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }
        List<DouyinSyncJob> running = syncJobRepository.findByTenantIdAndStatusInOrderByCreatedAtDesc(
                tenantId,
                List.of("pending", "running")
        );
        if (!force && !running.isEmpty()) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    AppErrorCode.DY_SYNC_IN_PROGRESS.getUserMessage()
            );
        }
        if (hasRunningBusy(tenantId) && !force) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    AppErrorCode.DY_SYNC_IN_PROGRESS.getUserMessage()
            );
        }
        validateStoreMapping(tenantId, storeId);

        String jobId = UUID.randomUUID().toString();
        String taskId = "agt_" + UUID.randomUUID();
        String now = now();
        DouyinSyncJob job = new DouyinSyncJob();
        job.setId(jobId);
        job.setTenantId(tenantId);
        job.setScope(normalizedScope);
        job.setStatus("pending");
        job.setStoreId(storeId == null ? "" : storeId.trim());
        job.setAgentTaskId(taskId);
        job.setCreatedAt(now);
        job.setUpdatedAt(now);
        syncJobRepository.save(job);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        payload.put("job_id", jobId);
        payload.put("scope", normalizedScope);
        payload.put("force", force);
        if (storeId != null && !storeId.isBlank()) {
            payload.put("store_id", storeId.trim());
        }
        if (categoryQuery != null && !categoryQuery.isBlank()) {
            payload.put("category_query", categoryQuery.trim());
        }
        if (categoryId != null && !categoryId.isBlank()) {
            payload.put("category_id", categoryId.trim());
        }
        if (pool != null && !pool.isBlank()) {
            payload.put("pool", pool.trim());
        }
        if (sortField != null && !sortField.isBlank()) {
            payload.put("sort_field", sortField.trim());
        }
        String taskType = "products".equals(normalizedScope)
                ? DouyinAgentTasks.PRODUCTS_SYNC
                : DouyinAgentTasks.SYNC;
        insertAgentTask(tenantId, taskId, taskType, payload, agent.getId());
        job.setStatus("running");
        job.setUpdatedAt(now());
        syncJobRepository.save(job);

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", jobId);
        data.put("status", job.getStatus());
        data.put("scope", job.getScope());
        data.put("agent_task_id", taskId);
        data.put("created_at", job.getCreatedAt());
        return data;
    }

    public Map<String, Object> getSyncJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        DouyinSyncJob job = syncJobRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        AppErrorCode.NOT_FOUND.getUserMessage()
                ));
        return toJobDto(job);
    }

    public Map<String, Object> todayOrders(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDateTime end = LocalDateTime.now(SHANGHAI).withNano(0);
        LocalDateTime start = end.minusDays(1);
        String windowStart = TS.format(start);
        String windowEnd = TS.format(end);
        List<String> reportDays = new ArrayList<>();
        LocalDate day = start.toLocalDate();
        LocalDate endDay = end.toLocalDate();
        while (!day.isAfter(endDay)) {
            reportDays.add(day.toString());
            day = day.plusDays(1);
        }
        List<DouyinOrder> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = orderRepository.findByTenantIdAndStoreIdAndReportDayInOrderByOrderedAtDesc(
                    tenantId, storeId.trim(), reportDays
            );
        } else {
            rows = orderRepository.findByTenantIdAndReportDayInOrderByOrderedAtDesc(tenantId, reportDays);
        }
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        List<Map<String, Object>> items = new ArrayList<>();
        String syncedAt = "";
        for (DouyinOrder row : rows) {
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            String orderedAt = row.getOrderedAt() == null ? "" : row.getOrderedAt().trim();
            // Lexicographic compare works for yyyy-MM-dd HH:mm:ss
            if (!orderedAt.isBlank() && (orderedAt.compareTo(windowStart) < 0 || orderedAt.compareTo(windowEnd) > 0)) {
                continue;
            }
            items.add(toOrderDto(row));
            if (syncedAt.isBlank() && row.getUpdatedAt() != null) {
                syncedAt = row.getUpdatedAt();
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("report_day", end.toLocalDate().toString());
        out.put("report_days", reportDays);
        out.put("window_start", windowStart);
        out.put("window_end", windowEnd);
        out.put("days", 1);
        out.put("synced_at", syncedAt);
        out.put("count", items.size());
        return out;
    }

    @Transactional
    public Map<String, Object> ingestOrders(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }

        List<Map<String, Object>> dayBatches = new ArrayList<>();
        Object rawDays = body.get("days");
        if (rawDays instanceof List<?> list && !list.isEmpty()) {
            for (Object item : list) {
                if (!(item instanceof Map<?, ?> map)) {
                    continue;
                }
                Map<String, Object> day = new LinkedHashMap<>();
                for (Map.Entry<?, ?> e : map.entrySet()) {
                    day.put(String.valueOf(e.getKey()), e.getValue());
                }
                dayBatches.add(day);
            }
        } else {
            String replaceDay = text(body.get("replace_day"));
            if (replaceDay.isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
            }
            Map<String, Object> single = new LinkedHashMap<>();
            single.put("replace_day", replaceDay);
            single.put("orders", body.get("orders"));
            dayBatches.add(single);
        }

        String now = now();
        int ingested = 0;
        List<String> replacedDays = new ArrayList<>();
        for (Map<String, Object> dayBody : dayBatches) {
            String replaceDay = firstNonBlank(text(dayBody.get("replace_day")), text(dayBody.get("replaceDay")));
            if (replaceDay.isBlank()) {
                continue;
            }
            Object rawOrders = dayBody.get("orders");
            List<Map<String, Object>> orders = new ArrayList<>();
            if (rawOrders instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map<?, ?> map) {
                        Map<String, Object> row = new LinkedHashMap<>();
                        for (Map.Entry<?, ?> e : map.entrySet()) {
                            row.put(String.valueOf(e.getKey()), e.getValue());
                        }
                        orders.add(row);
                    }
                }
            }
            orderRepository.deleteByTenantIdAndStoreIdAndReportDay(tenantId, storeId, replaceDay);
            List<DouyinOrder> saved = new ArrayList<>();
            for (Map<String, Object> src : orders) {
                saved.add(mapOrder(tenantId, storeId, replaceDay, src, now));
            }
            if (!saved.isEmpty()) {
                orderRepository.saveAll(saved);
            }
            ingested += saved.size();
            replacedDays.add(replaceDay);
        }

        String jobId = text(body.get("job_id"));
        if (!jobId.isBlank()) {
            int finalIngested = ingested;
            syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
                job.setOrdersCount(finalIngested);
                job.setUpdatedAt(now);
                syncJobRepository.save(job);
            });
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", ingested);
        out.put("store_id", storeId);
        out.put("replace_days", replacedDays);
        if (replacedDays.size() == 1) {
            out.put("replace_day", replacedDays.get(0));
        }
        return out;
    }

    public Map<String, Object> listProducts(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        List<DouyinProduct> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = productRepository.findByTenantIdAndStoreIdOrderByUpdatedAtDesc(tenantId, storeId.trim());
        } else {
            rows = productRepository.findByTenantIdOrderByUpdatedAtDesc(tenantId);
        }
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        List<Map<String, Object>> items = new ArrayList<>();
        String syncedAt = "";
        for (DouyinProduct row : rows) {
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            items.add(toProductDto(row));
            if (syncedAt.isBlank() && row.getSyncedAt() != null && !row.getSyncedAt().isBlank()) {
                syncedAt = row.getSyncedAt();
            } else if (syncedAt.isBlank() && row.getUpdatedAt() != null) {
                syncedAt = row.getUpdatedAt();
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("synced_at", syncedAt);
        out.put("count", items.size());
        return out;
    }

    @Transactional
    public Map<String, Object> ingestProducts(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            storeId = "default";
        }
        Object rawProducts = body.get("products");
        List<Map<String, Object>> products = new ArrayList<>();
        if (rawProducts instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (Map.Entry<?, ?> e : map.entrySet()) {
                        row.put(String.valueOf(e.getKey()), e.getValue());
                    }
                    products.add(row);
                }
            }
        }
        productRepository.deleteByTenantIdAndStoreId(tenantId, storeId);
        String now = now();
        List<DouyinProduct> saved = new ArrayList<>();
        for (Map<String, Object> src : products) {
            DouyinProduct product = mapProduct(tenantId, storeId, src, now);
            if (product.getProductId().isBlank() && product.getProductName().isBlank()) {
                continue;
            }
            saved.add(product);
        }
        productRepository.saveAll(saved);

        String jobId = text(body.get("job_id"));
        if (!jobId.isBlank()) {
            String finalStoreId = storeId;
            syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
                job.setProductsCount(saved.size());
                job.setStoreId(finalStoreId);
                job.setUpdatedAt(now);
                syncJobRepository.save(job);
            });
        }
        return Map.of("ingested", saved.size(), "store_id", storeId);
    }

    public Map<String, Object> listIssues(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        List<DouyinIssue> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = issueRepository.findByTenantIdAndStoreIdOrderByReportedAtDesc(tenantId, storeId.trim());
        } else {
            rows = issueRepository.findByTenantIdOrderByReportedAtDesc(tenantId);
        }
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        List<Map<String, Object>> items = new ArrayList<>();
        String syncedAt = "";
        for (DouyinIssue row : rows) {
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            items.add(toIssueDto(row));
            String cand = firstNonBlank(row.getUpdatedAt(), row.getReportedAt());
            if (!cand.isBlank() && (syncedAt.isBlank() || cand.compareTo(syncedAt) > 0)) {
                syncedAt = cand;
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("synced_at", syncedAt);
        out.put("total", items.size());
        out.put("count", items.size());
        return out;
    }

    @Transactional
    public Map<String, Object> ingestIssues(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            storeId = "default";
        }
        Object rawIssues = body.get("issues");
        List<Map<String, Object>> issues = new ArrayList<>();
        if (rawIssues instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (Map.Entry<?, ?> e : map.entrySet()) {
                        row.put(String.valueOf(e.getKey()), e.getValue());
                    }
                    issues.add(row);
                }
            }
        }
        String now = now();
        int upserted = 0;
        for (Map<String, Object> src : issues) {
            String externalId = firstNonBlank(text(src.get("external_id")), text(src.get("externalId")));
            if (externalId.isBlank()) {
                continue;
            }
            Optional<DouyinIssue> existing = issueRepository.findByTenantIdAndStoreIdAndExternalId(
                    tenantId, storeId, externalId
            );
            DouyinIssue row;
            boolean isNew;
            if (existing.isPresent()) {
                row = existing.get();
                isNew = false;
            } else {
                row = new DouyinIssue();
                row.setId(UUID.randomUUID().toString());
                row.setTenantId(tenantId);
                row.setStoreId(storeId);
                row.setExternalId(externalId);
                isNew = true;
            }
            DouyinIssueUpsert.applyIncoming(row, src, now, isNew);
            issueRepository.save(row);
            upserted++;
        }

        boolean partial = Boolean.TRUE.equals(body.get("partial"));
        String message = firstNonBlank(text(body.get("message")), text(body.get("partial_reason")));
        String jobId = text(body.get("job_id"));
        if (!jobId.isBlank()) {
            String finalStoreId = storeId;
            int finalUpserted = upserted;
            syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
                job.setIssuesCount(finalUpserted);
                job.setStoreId(finalStoreId);
                if (!message.isBlank()) {
                    job.setMessage(message);
                }
                if (partial) {
                    // Status finalized on agent task complete; stash hint in message.
                    String existingMsg = text(job.getMessage());
                    if (existingMsg.isBlank()) {
                        job.setMessage(firstNonBlank(message, AppErrorCode.DY_ISSUES_SOURCE_UNCONFIGURED.getUserMessage()));
                    }
                }
                job.setUpdatedAt(now);
                syncJobRepository.save(job);
            });
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", upserted);
        out.put("store_id", storeId);
        out.put("partial", partial);
        return out;
    }

    @Transactional
    public Map<String, Object> resolveIssue(String id, Map<String, Object> body) {
        Long tenantId = dataScopeService.requireTenantId();
        DouyinIssue row = issueRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        AppErrorCode.NOT_FOUND.getUserMessage()
                ));
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, AppErrorCode.FORBIDDEN.getUserMessage());
        }
        String now = now();
        boolean resolved = body == null || !Boolean.FALSE.equals(body.get("resolved"));
        row.setResolved(resolved ? 1 : 0);
        if (resolved) {
            row.setResolvedAt(now);
            if (body != null) {
                String note = firstNonBlank(text(body.get("note")), text(body.get("resolveNote")));
                if (!note.isBlank()) {
                    row.setNote(note);
                }
            }
        } else {
            row.setResolvedAt("");
        }
        row.setUpdatedAt(now);
        issueRepository.save(row);
        return toIssueDto(row);
    }

    public Map<String, Object> getCompass(String storeId, Integer dateType) {
        Long tenantId = dataScopeService.requireTenantId();
        int dt = dateType == null || dateType <= 0 ? 1 : dateType;
        Optional<DouyinCompassSnapshot> opt;
        if (storeId != null && !storeId.isBlank()) {
            opt = compassSnapshotRepository.findFirstByTenantIdAndStoreIdAndDateTypeOrderBySyncedAtDesc(
                    tenantId, storeId.trim(), dt
            );
        } else {
            opt = compassSnapshotRepository.findFirstByTenantIdAndDateTypeOrderBySyncedAtDesc(tenantId, dt);
        }
        if (opt.isEmpty()) {
            Map<String, Object> empty = new LinkedHashMap<>();
            empty.put("snapshot", null);
            empty.put("date_type", dt);
            empty.put("synced_at", "");
            return empty;
        }
        DouyinCompassSnapshot row = opt.get();
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
            Map<String, Object> empty = new LinkedHashMap<>();
            empty.put("snapshot", null);
            empty.put("date_type", dt);
            empty.put("synced_at", "");
            return empty;
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("snapshot", toCompassDto(row));
        out.put("date_type", dt);
        out.put("synced_at", row.getSyncedAt());
        return out;
    }

    public Map<String, Object> listCompass(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        int[] types = new int[]{1, 20, 21, 23};
        Map<Integer, String> labels = Map.of(
                1, "实时",
                20, "近1天",
                21, "近7天",
                23, "近30天"
        );
        List<Map<String, Object>> snapshots = new ArrayList<>();
        String syncedAt = "";
        for (int dt : types) {
            Optional<DouyinCompassSnapshot> opt;
            if (storeId != null && !storeId.isBlank()) {
                opt = compassSnapshotRepository.findFirstByTenantIdAndStoreIdAndDateTypeOrderBySyncedAtDesc(
                        tenantId, storeId.trim(), dt
                );
            } else {
                opt = compassSnapshotRepository.findFirstByTenantIdAndDateTypeOrderBySyncedAtDesc(tenantId, dt);
            }
            if (opt.isEmpty()) {
                continue;
            }
            DouyinCompassSnapshot row = opt.get();
            List<String> scope = authContext.shopScope();
            boolean boss = authContext.isBossPortal() || authContext.isAdmin();
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            Map<String, Object> dto = toCompassDto(row);
            dto.put("dateLabel", labels.getOrDefault(dt, String.valueOf(dt)));
            snapshots.add(dto);
            if (syncedAt.isBlank() || (row.getSyncedAt() != null && row.getSyncedAt().compareTo(syncedAt) > 0)) {
                syncedAt = row.getSyncedAt() == null ? "" : row.getSyncedAt();
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("snapshots", snapshots);
        out.put("synced_at", syncedAt);
        out.put("count", snapshots.size());
        return out;
    }

    @Transactional
    public Map<String, Object> ingestCompass(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            storeId = "default";
        }
        String reportDay = firstNonBlank(text(body.get("report_day")), text(body.get("reportDay")));
        if (reportDay.isBlank()) {
            reportDay = LocalDate.now(SHANGHAI).toString();
        }
        int dateType = intVal(body.get("date_type"), 1);
        if (dateType <= 0) {
            dateType = 1;
        }
        Object snapObj = body.get("snapshot");
        Map<String, Object> src = new LinkedHashMap<>();
        if (snapObj instanceof Map<?, ?> map) {
            for (Map.Entry<?, ?> e : map.entrySet()) {
                src.put(String.valueOf(e.getKey()), e.getValue());
            }
        } else {
            src.putAll(body);
        }
        Object rawObj = body.get("raw");
        String rawJson = "";
        if (rawObj != null) {
            try {
                rawJson = objectMapper.writeValueAsString(rawObj);
            } catch (Exception ex) {
                rawJson = text(body.get("raw_json"));
            }
        } else {
            rawJson = firstNonBlank(text(src.get("raw_json")), text(body.get("raw_json")));
        }

        compassSnapshotRepository.deleteByTenantIdAndStoreIdAndReportDayAndDateType(
                tenantId, storeId, reportDay, dateType
        );
        String now = now();
        String key = tenantId + "|" + storeId + "|" + reportDay + "|" + dateType;
        DouyinCompassSnapshot row = new DouyinCompassSnapshot();
        row.setId(UUID.nameUUIDFromBytes(key.getBytes()).toString());
        row.setTenantId(tenantId);
        row.setStoreId(storeId);
        row.setReportDay(reportDay);
        row.setDateType(dateType);
        row.setShopName(firstNonBlank(text(src.get("shop_name")), text(src.get("shopName"))));
        row.setPayAmt(doubleVal(src.get("pay_amt")));
        if (row.getPayAmt() == null) row.setPayAmt(doubleVal(src.get("payAmt")));
        row.setPayCnt(doubleVal(src.get("pay_cnt")));
        if (row.getPayCnt() == null) row.setPayCnt(doubleVal(src.get("payCnt")));
        row.setPayUcnt(doubleVal(src.get("pay_ucnt")));
        if (row.getPayUcnt() == null) row.setPayUcnt(doubleVal(src.get("payUcnt")));
        row.setIncomeAmt(doubleVal(src.get("income_amt")));
        if (row.getIncomeAmt() == null) row.setIncomeAmt(doubleVal(src.get("incomeAmt")));
        row.setPerUsrPayAmt(doubleVal(src.get("per_usr_pay_amt")));
        if (row.getPerUsrPayAmt() == null) row.setPerUsrPayAmt(doubleVal(src.get("perUsrPayAmt")));
        row.setProductShowUcnt(doubleVal(src.get("product_show_ucnt")));
        if (row.getProductShowUcnt() == null) row.setProductShowUcnt(doubleVal(src.get("productShowUcnt")));
        row.setProductShowCnt(doubleVal(src.get("product_show_cnt")));
        if (row.getProductShowCnt() == null) row.setProductShowCnt(doubleVal(src.get("productShowCnt")));
        row.setProductClickUcnt(doubleVal(src.get("product_click_ucnt")));
        if (row.getProductClickUcnt() == null) row.setProductClickUcnt(doubleVal(src.get("productClickUcnt")));
        row.setProductClickCnt(doubleVal(src.get("product_click_cnt")));
        if (row.getProductClickCnt() == null) row.setProductClickCnt(doubleVal(src.get("productClickCnt")));
        row.setShowClickRate(doubleVal(src.get("show_click_rate")));
        if (row.getShowClickRate() == null) row.setShowClickRate(doubleVal(src.get("showClickRate")));
        row.setClickPayRate(doubleVal(src.get("click_pay_rate")));
        if (row.getClickPayRate() == null) row.setClickPayRate(doubleVal(src.get("clickPayRate")));
        row.setSettlementAmt(doubleVal(src.get("settlement_amt")));
        if (row.getSettlementAmt() == null) row.setSettlementAmt(doubleVal(src.get("settlementAmt")));
        row.setRefundAmt(doubleVal(src.get("refund_amt")));
        if (row.getRefundAmt() == null) row.setRefundAmt(doubleVal(src.get("refundAmt")));
        row.setRefundRate(doubleVal(src.get("refund_rate")));
        if (row.getRefundRate() == null) row.setRefundRate(doubleVal(src.get("refundRate")));
        row.setExpScore(doubleVal(src.get("exp_score")));
        if (row.getExpScore() == null) row.setExpScore(doubleVal(src.get("expScore")));
        row.setExpProduct(doubleVal(src.get("exp_product")));
        if (row.getExpProduct() == null) row.setExpProduct(doubleVal(src.get("expProduct")));
        row.setExpService(doubleVal(src.get("exp_service")));
        if (row.getExpService() == null) row.setExpService(doubleVal(src.get("expService")));
        row.setExpLogistics(doubleVal(src.get("exp_logistics")));
        if (row.getExpLogistics() == null) row.setExpLogistics(doubleVal(src.get("expLogistics")));
        Object carriers = src.get("carriers");
        if (carriers == null) {
            carriers = src.get("carrier_json");
        }
        try {
            if (carriers instanceof String s && !s.isBlank()) {
                row.setCarrierJson(s);
            } else if (carriers != null) {
                row.setCarrierJson(objectMapper.writeValueAsString(carriers));
            } else {
                row.setCarrierJson("[]");
            }
        } catch (Exception ex) {
            row.setCarrierJson("[]");
        }
        Object metrics = src.get("metrics");
        if (metrics == null) {
            metrics = src.get("metrics_json");
        }
        try {
            if (metrics instanceof String s && !s.isBlank()) {
                row.setMetricsJson(s);
            } else if (metrics != null) {
                row.setMetricsJson(objectMapper.writeValueAsString(metrics));
            } else {
                row.setMetricsJson("{}");
            }
        } catch (Exception ex) {
            row.setMetricsJson("{}");
        }
        row.setRawJson(rawJson.isBlank() ? "{}" : rawJson);
        row.setSourceUrl(firstNonBlank(text(body.get("source_url")), text(src.get("source_url"))));
        row.setSyncedAt(now);
        row.setCreatedAt(now);
        row.setUpdatedAt(now);
        compassSnapshotRepository.save(row);

        String jobId = text(body.get("job_id"));
        if (!jobId.isBlank()) {
            syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
                job.setMessage(firstNonBlank(text(body.get("message")), "已同步抖店罗盘"));
                job.setUpdatedAt(now);
                syncJobRepository.save(job);
            });
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", 1);
        out.put("store_id", storeId);
        out.put("report_day", reportDay);
        out.put("date_type", dateType);
        return out;
    }

    public Map<String, Object> listOpportunityProducts(String storeId, String categoryKey, String q) {
        return listOpportunityProducts(storeId, categoryKey, q, null, null);
    }

    public Map<String, Object> listOpportunityProducts(
            String storeId,
            String categoryKey,
            String q,
            String pool,
            String sortField
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        List<DouyinOpportunityProduct> rows;
        String store = storeId == null ? "" : storeId.trim();
        String catKey = categoryKey == null ? "" : categoryKey.trim();
        String poolKey = pool == null ? "" : pool.trim().toLowerCase(Locale.ROOT);
        String sortKey = sortField == null ? "" : sortField.trim().toUpperCase(Locale.ROOT);
        if (!store.isBlank() && !catKey.isBlank()) {
            rows = opportunityProductRepository.findByTenantIdAndStoreIdAndCategoryKeyOrderByRankNoAsc(
                    tenantId, store, catKey
            );
        } else if (!store.isBlank()) {
            rows = opportunityProductRepository.findByTenantIdAndStoreIdOrderBySyncedAtDescRankNoAsc(tenantId, store);
        } else if (!catKey.isBlank()) {
            rows = opportunityProductRepository.findByTenantIdAndCategoryKeyOrderByRankNoAsc(tenantId, catKey);
        } else {
            rows = opportunityProductRepository.findByTenantIdOrderBySyncedAtDescRankNoAsc(tenantId);
        }
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        String needle = q == null ? "" : q.trim().toLowerCase(Locale.ROOT);
        String wantPrefix = "";
        if (!poolKey.isBlank()) {
            wantPrefix = "pool:" + poolKey + "|";
            if (!sortKey.isBlank()) {
                wantPrefix = wantPrefix + "sort:" + sortKey + "|";
            }
        }
        List<Map<String, Object>> items = new ArrayList<>();
        String syncedAt = "";
        String usedCategoryKey = "";
        String usedCategoryName = "";
        for (DouyinOpportunityProduct row : rows) {
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            String rowKey = row.getCategoryKey() == null ? "" : row.getCategoryKey();
            if (!wantPrefix.isBlank()) {
                boolean match = rowKey.startsWith(wantPrefix);
                // backward compat: old default recommended key maps to potential+MATCH_DEGREE
                if (!match
                        && "potential".equals(poolKey)
                        && (sortKey.isBlank() || "MATCH_DEGREE".equals(sortKey))
                        && ("default:recommended".equals(rowKey) || rowKey.startsWith("leaf:") || rowKey.startsWith("q:"))) {
                    match = true;
                }
                if (!match) {
                    continue;
                }
            }
            if (!needle.isBlank()) {
                String hay = (row.getProductName() + " " + row.getCategoryPath() + " " + row.getCategoryName())
                        .toLowerCase(Locale.ROOT);
                if (!hay.contains(needle)) {
                    continue;
                }
            }
            // Keep only the newest category_key batch when store filter omitted category_key
            if (catKey.isBlank()) {
                if (usedCategoryKey.isBlank()) {
                    usedCategoryKey = rowKey;
                    usedCategoryName = row.getCategoryName() == null ? "" : row.getCategoryName();
                } else if (!usedCategoryKey.equals(rowKey)) {
                    continue;
                }
            } else if (usedCategoryName.isBlank()) {
                usedCategoryName = row.getCategoryName() == null ? "" : row.getCategoryName();
                usedCategoryKey = rowKey;
            }
            items.add(toOpportunityDto(row));
            if (syncedAt.isBlank() && row.getSyncedAt() != null) {
                syncedAt = row.getSyncedAt();
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("count", items.size());
        out.put("synced_at", syncedAt);
        out.put("category_key", usedCategoryKey);
        out.put("category_name", usedCategoryName);
        out.put("pool", poolKey);
        out.put("sort_field", sortKey);
        return out;
    }

    public Map<String, Object> getOpportunityOverview(String id) {
        Long tenantId = dataScopeService.requireTenantId();
        DouyinOpportunityProduct row = opportunityProductRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        AppErrorCode.NOT_FOUND.getUserMessage()
                ));
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, AppErrorCode.FORBIDDEN.getUserMessage());
        }
        Map<String, Object> out = toOpportunityDto(row);
        out.put("overview", parseJson(row.getOverviewJson()));
        out.put("raw", parseJson(row.getRawJson()));
        return out;
    }

    @Transactional
    public Map<String, Object> ingestOpportunity(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            storeId = "default";
        }
        String categoryKey = firstNonBlank(text(body.get("category_key")), text(body.get("categoryKey")));
        if (categoryKey.isBlank()) {
            categoryKey = "default:recommended";
        }
        String categoryId = firstNonBlank(text(body.get("category_id")), text(body.get("categoryId")));
        String categoryName = firstNonBlank(text(body.get("category_name")), text(body.get("categoryName")));
        String categoryQuery = firstNonBlank(text(body.get("category_query")), text(body.get("categoryQuery")));
        boolean isDefault = Boolean.TRUE.equals(body.get("is_default_category"))
                || Boolean.TRUE.equals(body.get("isDefaultCategory"))
                || categoryKey.startsWith("default:");
        String sourceUrl = text(body.get("source_url"));
        Object productsObj = body.get("products");
        if (productsObj == null) {
            productsObj = body.get("items");
        }
        if (!(productsObj instanceof List<?> list) || list.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }

        opportunityProductRepository.deleteByTenantIdAndStoreIdAndCategoryKey(tenantId, storeId, categoryKey);
        String now = now();
        List<DouyinOpportunityProduct> saved = new ArrayList<>();
        int rank = 0;
        for (Object rawItem : list) {
            if (!(rawItem instanceof Map<?, ?> map)) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                item.put(String.valueOf(e.getKey()), e.getValue());
            }
            String clueId = firstNonBlank(text(item.get("clue_id")), text(item.get("clueId")), text(item.get("product_id")));
            if (clueId.isBlank()) {
                continue;
            }
            rank += 1;
            String key = tenantId + "|" + storeId + "|" + categoryKey + "|" + clueId;
            DouyinOpportunityProduct row = new DouyinOpportunityProduct();
            row.setId(UUID.nameUUIDFromBytes(key.getBytes()).toString());
            row.setTenantId(tenantId);
            row.setStoreId(storeId);
            row.setCategoryKey(categoryKey);
            row.setCategoryId(firstNonBlank(categoryId, text(item.get("category_id"))));
            row.setCategoryName(firstNonBlank(categoryName, text(item.get("category_name"))));
            row.setCategoryQuery(categoryQuery);
            row.setIsDefaultCategory(isDefault ? 1 : 0);
            row.setRankNo(intVal(item.get("rank_no"), rank));
            row.setClueId(clueId);
            row.setProductName(firstNonBlank(text(item.get("product_name")), text(item.get("name"))));
            row.setMainImage(firstNonBlank(text(item.get("main_image")), text(item.get("product_pic_url"))));
            row.setCategoryPath(firstNonBlank(text(item.get("category_path")), text(item.get("categoryPath"))));
            row.setPriceMin(doubleVal(item.get("price_min")));
            row.setPriceMax(doubleVal(item.get("price_max")));
            row.setSearchHeat(doubleVal(item.get("search_heat")));
            row.setSearchPvRange(firstNonBlank(text(item.get("search_pv_range")), text(item.get("search_pv_cnt_range"))));
            row.setPayGrowthRate(doubleVal(item.get("pay_growth_rate")));
            if (row.getPayGrowthRate() == null) {
                row.setPayGrowthRate(doubleVal(item.get("pay_amount_ind_30d_rate")));
            }
            row.setPayAmtRange(firstNonBlank(text(item.get("pay_amt_range")), text(item.get("pay_amount_ind_range"))));
            row.setLabelsJson(writeJson(item.get("labels"), "[]"));
            row.setOverviewJson(writeJson(item.get("overview"), "{}"));
            row.setRawJson(writeJson(item.get("raw") != null ? item.get("raw") : item, "{}"));
            row.setSourceUrl(sourceUrl);
            row.setSyncedAt(now);
            row.setCreatedAt(now);
            row.setUpdatedAt(now);
            saved.add(row);
        }
        opportunityProductRepository.saveAll(saved);

        String jobId = text(body.get("job_id"));
        if (!jobId.isBlank()) {
            String message = firstNonBlank(text(body.get("message")), "已同步商机中心为你推荐 Top" + saved.size());
            syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
                job.setMessage(message);
                job.setUpdatedAt(now);
                syncJobRepository.save(job);
            });
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", saved.size());
        out.put("store_id", storeId);
        out.put("category_key", categoryKey);
        out.put("category_name", categoryName);
        return out;
    }

    public Map<String, Object> listCompassProductRanks(String storeId, String board, String dateWindow) {
        Long tenantId = dataScopeService.requireTenantId();
        String normalizedBoard = normalizeCompassRankBoard(board);
        String normalizedWindow = normalizeCompassRankDateWindow(dateWindow);
        String store = storeId == null || storeId.isBlank() || "all".equalsIgnoreCase(storeId.trim())
                || "default".equalsIgnoreCase(storeId.trim())
                ? ""
                : storeId.trim();

        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        if (!store.isBlank() && !boss && scope != null && !scope.isEmpty() && !scope.contains(store)) {
            return emptyCompassProductRankList(normalizedBoard, normalizedWindow);
        }

        List<DouyinCompassProductRank> rows;
        String preferredStore = "";
        if (!store.isBlank()) {
            rows = compassProductRankRepository.findByTenantIdAndStoreIdAndBoardAndDateWindowOrderByRankNoAsc(
                    tenantId, store, normalizedBoard, normalizedWindow
            );
            preferredStore = store;
        } else {
            rows = compassProductRankRepository.findByTenantIdAndBoardAndDateWindowOrderBySyncedAtDescRankNoAsc(
                    tenantId, normalizedBoard, normalizedWindow
            );
            // Prefer the most recently synced store slice when "全部店铺"
            for (DouyinCompassProductRank row : rows) {
                if (row.getStoreId() != null && !row.getStoreId().isBlank()) {
                    preferredStore = row.getStoreId();
                    break;
                }
            }
            if (!preferredStore.isBlank()) {
                String keep = preferredStore;
                rows = rows.stream().filter(r -> keep.equals(r.getStoreId())).toList();
            }
        }
        List<Map<String, Object>> items = new ArrayList<>();
        String syncedAt = "";
        String reportDay = "";
        String categoryName = "";
        for (DouyinCompassProductRank row : rows) {
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            items.add(toCompassProductRankDto(row));
            if (syncedAt.isBlank() && row.getSyncedAt() != null) {
                syncedAt = row.getSyncedAt();
            }
            if (reportDay.isBlank() && row.getReportDay() != null && !row.getReportDay().isBlank()) {
                reportDay = row.getReportDay();
            }
            if (categoryName.isBlank() && row.getCategoryName() != null && !row.getCategoryName().isBlank()) {
                categoryName = row.getCategoryName();
            }
        }

        String peerWindow = CompassRankTrackAnalyzer.peerWindow(normalizedWindow);
        List<DouyinCompassProductRank> peerRows;
        if (!store.isBlank()) {
            peerRows = compassProductRankRepository
                    .findByTenantIdAndStoreIdAndBoardAndDateWindowOrderByRankNoAsc(
                            tenantId, store, normalizedBoard, peerWindow);
        } else if (!preferredStore.isBlank()) {
            peerRows = compassProductRankRepository
                    .findByTenantIdAndStoreIdAndBoardAndDateWindowOrderByRankNoAsc(
                            tenantId, preferredStore, normalizedBoard, peerWindow);
        } else {
            peerRows = compassProductRankRepository
                    .findByTenantIdAndBoardAndDateWindowOrderBySyncedAtDescRankNoAsc(
                            tenantId, normalizedBoard, peerWindow);
            String keep = "";
            for (DouyinCompassProductRank row : peerRows) {
                if (row.getStoreId() != null && !row.getStoreId().isBlank()) {
                    keep = row.getStoreId();
                    break;
                }
            }
            if (!keep.isBlank()) {
                String k = keep;
                peerRows = peerRows.stream().filter(r -> k.equals(r.getStoreId())).toList();
            }
        }
        List<Map<String, Object>> peerItems = new ArrayList<>();
        for (DouyinCompassProductRank row : peerRows) {
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            peerItems.add(toCompassProductRankDto(row));
        }
        boolean peerAvailable = !peerItems.isEmpty();
        CompassRankTrackAnalyzer.enrich(items, peerItems, peerAvailable);

        boolean hasShowCnt = false;
        boolean hasOrderCnt = false;
        for (Map<String, Object> it : items) {
            if (it.get("showCnt") != null) {
                hasShowCnt = true;
            }
            if (it.get("orderCnt") != null) {
                hasOrderCnt = true;
            }
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("synced_at", syncedAt);
        out.put("board", normalizedBoard);
        out.put("date_window", normalizedWindow);
        out.put("report_day", reportDay);
        out.put("category_name", categoryName);
        out.put("total", items.size());
        out.put("peer_date_window", peerWindow);
        out.put("peer_available", peerAvailable);
        out.put("analysis_version", "v1");
        out.put("has_show_cnt", hasShowCnt);
        out.put("has_order_cnt", hasOrderCnt);
        return out;
    }

    @Transactional
    public Map<String, Object> ingestCompassProductRank(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            storeId = "default";
        }
        String board = normalizeCompassRankBoard(
                firstNonBlank(text(body.get("board")), text(body.get("board_type")))
        );
        if (!isValidCompassRankBoard(board)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }
        String dateWindow = normalizeCompassRankDateWindow(
                firstNonBlank(text(body.get("date_window")), text(body.get("dateWindow")))
        );
        if (!isValidCompassRankDateWindow(dateWindow)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }
        String reportDay = firstNonBlank(text(body.get("report_day")), text(body.get("reportDay")));
        String categoryId = firstNonBlank(text(body.get("category_id")), text(body.get("categoryId")));
        String categoryName = firstNonBlank(text(body.get("category_name")), text(body.get("categoryName")));
        boolean isDefault = Boolean.TRUE.equals(body.get("is_default_category"))
                || Boolean.TRUE.equals(body.get("isDefaultCategory"))
                || categoryId.isBlank();
        String sourceUrl = text(body.get("source_url"));

        Object productsObj = body.get("products");
        if (productsObj == null) {
            productsObj = body.get("items");
        }
        if (!(productsObj instanceof List<?> list)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }

        compassProductRankRepository.deleteByTenantIdAndStoreIdAndBoardAndDateWindow(
                tenantId, storeId, board, dateWindow
        );
        String now = now();
        List<DouyinCompassProductRank> saved = new ArrayList<>();
        int rank = 0;
        for (Object rawItem : list) {
            if (!(rawItem instanceof Map<?, ?> map)) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                item.put(String.valueOf(e.getKey()), e.getValue());
            }
            String productId = firstNonBlank(
                    text(item.get("product_id")),
                    text(item.get("productId")),
                    text(item.get("id"))
            );
            if (productId.isBlank()) {
                continue;
            }
            rank += 1;
            String key = tenantId + "|" + storeId + "|" + board + "|" + dateWindow + "|" + productId;
            DouyinCompassProductRank row = new DouyinCompassProductRank();
            row.setId(UUID.nameUUIDFromBytes(key.getBytes()).toString());
            row.setTenantId(tenantId);
            row.setStoreId(storeId);
            row.setBoard(board);
            row.setDateWindow(dateWindow);
            row.setReportDay(firstNonBlank(reportDay, text(item.get("report_day")), text(item.get("reportDay"))));
            row.setRankNo(intVal(firstNonBlankObj(item.get("rank_no"), item.get("rankNo"), item.get("rank")), rank));
            row.setProductId(productId);
            row.setProductName(firstNonBlank(text(item.get("product_name")), text(item.get("productName")), text(item.get("name"))));
            row.setMainImage(firstNonBlank(
                    text(item.get("main_image")),
                    text(item.get("mainImage")),
                    text(item.get("product_pic_url")),
                    text(item.get("image"))
            ));
            row.setCategoryPath(firstNonBlank(text(item.get("category_path")), text(item.get("categoryPath"))));
            row.setShopName(firstNonBlank(text(item.get("shop_name")), text(item.get("shopName"))));
            row.setPayAmt(doubleVal(firstNonBlankObj(item.get("pay_amt"), item.get("payAmt"))));
            row.setClickCnt(doubleVal(firstNonBlankObj(item.get("click_cnt"), item.get("clickCnt"))));
            row.setPayCnt(doubleVal(firstNonBlankObj(item.get("pay_cnt"), item.get("payCnt"))));
            row.setClickPayCvr(doubleVal(firstNonBlankObj(item.get("click_pay_cvr"), item.get("clickPayCvr"))));
            row.setShowCnt(doubleVal(firstNonBlankObj(item.get("show_cnt"), item.get("showCnt"))));
            row.setOrderCnt(doubleVal(firstNonBlankObj(item.get("order_cnt"), item.get("orderCnt"))));
            row.setDealCnt(doubleVal(firstNonBlankObj(item.get("deal_cnt"), item.get("dealCnt"))));
            row.setIsDefaultCategory(isDefault ? 1 : 0);
            row.setCategoryId(firstNonBlank(categoryId, text(item.get("category_id")), text(item.get("categoryId"))));
            row.setCategoryName(firstNonBlank(categoryName, text(item.get("category_name")), text(item.get("categoryName"))));
            row.setSourceUrl(sourceUrl);
            row.setRawJson(writeJson(item.get("raw") != null ? item.get("raw") : item, "{}"));
            row.setSyncedAt(now);
            row.setCreatedAt(now);
            row.setUpdatedAt(now);
            saved.add(row);
        }
        if (!saved.isEmpty()) {
            compassProductRankRepository.saveAll(saved);
        }

        String jobId = text(body.get("job_id"));
        if (!jobId.isBlank()) {
            String message = firstNonBlank(
                    text(body.get("message")),
                    "已同步罗盘商品榜 " + board + "/" + dateWindow + " Top" + saved.size()
            );
            syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
                job.setMessage(message);
                job.setUpdatedAt(now);
                syncJobRepository.save(job);
            });
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("saved", saved.size());
        out.put("board", board);
        out.put("date_window", dateWindow);
        out.put("report_day", reportDay);
        return out;
    }

    private Map<String, Object> emptyCompassProductRankList(String board, String dateWindow) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", List.of());
        out.put("synced_at", "");
        out.put("board", board);
        out.put("date_window", dateWindow);
        out.put("report_day", "");
        out.put("category_name", "");
        out.put("total", 0);
        out.put("peer_date_window", CompassRankTrackAnalyzer.peerWindow(dateWindow));
        out.put("peer_available", false);
        out.put("analysis_version", "v1");
        out.put("has_show_cnt", false);
        out.put("has_order_cnt", false);
        return out;
    }

    private Map<String, Object> toCompassProductRankDto(DouyinCompassProductRank row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("rankNo", row.getRankNo());
        item.put("productId", row.getProductId());
        item.put("productName", row.getProductName());
        item.put("mainImage", row.getMainImage());
        item.put("categoryPath", row.getCategoryPath());
        item.put("shopName", row.getShopName());
        item.put("payAmt", row.getPayAmt());
        item.put("clickCnt", row.getClickCnt());
        item.put("payCnt", row.getPayCnt());
        item.put("clickPayCvr", row.getClickPayCvr());
        item.put("showCnt", row.getShowCnt());
        // Compass 昨日商品卡榜常不返回 pay_cnt（成交订单数）；用成交件数兜底，避免列表整列空白
        Double orderCnt = row.getOrderCnt();
        if (orderCnt == null) {
            orderCnt = row.getDealCnt() != null ? row.getDealCnt() : row.getPayCnt();
        }
        item.put("orderCnt", orderCnt);
        item.put("dealCnt", row.getDealCnt());
        item.put("board", row.getBoard());
        item.put("dateWindow", row.getDateWindow());
        item.put("reportDay", row.getReportDay());
        item.put("syncedAt", row.getSyncedAt());
        return item;
    }

    private static String normalizeCompassRankBoard(String board) {
        String value = board == null ? "" : board.trim().toLowerCase(Locale.ROOT);
        return value.isBlank() ? "total" : value;
    }

    private static String normalizeCompassRankDateWindow(String dateWindow) {
        String value = dateWindow == null ? "" : dateWindow.trim().toLowerCase(Locale.ROOT);
        return value.isBlank() ? "today" : value;
    }

    private static boolean isValidCompassRankBoard(String board) {
        return "search".equals(board) || "product_card".equals(board) || "total".equals(board);
    }

    private static boolean isValidCompassRankDateWindow(String dateWindow) {
        return "today".equals(dateWindow) || "yesterday".equals(dateWindow);
    }

    private static Object firstNonBlankObj(Object... values) {
        if (values == null) {
            return null;
        }
        for (Object value : values) {
            if (value == null) {
                continue;
            }
            String text = String.valueOf(value).trim();
            if (!text.isEmpty() && !"null".equalsIgnoreCase(text)) {
                return value;
            }
        }
        return null;
    }

    private String writeJson(Object value, String fallback) {
        try {
            if (value instanceof String s) {
                return s.isBlank() ? fallback : s;
            }
            if (value == null) {
                return fallback;
            }
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            return fallback;
        }
    }

    private Map<String, Object> toOpportunityDto(DouyinOpportunityProduct row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("storeId", row.getStoreId());
        item.put("categoryKey", row.getCategoryKey());
        item.put("categoryId", row.getCategoryId());
        item.put("categoryName", row.getCategoryName());
        item.put("categoryQuery", row.getCategoryQuery());
        item.put("isDefaultCategory", row.getIsDefaultCategory() != null && row.getIsDefaultCategory() == 1);
        item.put("rankNo", row.getRankNo());
        item.put("clueId", row.getClueId());
        item.put("productName", row.getProductName());
        item.put("mainImage", row.getMainImage());
        item.put("categoryPath", row.getCategoryPath());
        item.put("priceMin", row.getPriceMin());
        item.put("priceMax", row.getPriceMax());
        item.put("searchHeat", row.getSearchHeat());
        item.put("searchPvRange", row.getSearchPvRange());
        item.put("payGrowthRate", row.getPayGrowthRate());
        item.put("payAmtRange", row.getPayAmtRange());
        item.put("labels", parseJsonArray(row.getLabelsJson()));
        item.put("hasOverview", row.getOverviewJson() != null && !row.getOverviewJson().isBlank()
                && !"{}".equals(row.getOverviewJson().trim()));
        item.put("syncedAt", row.getSyncedAt());
        item.put("sourceUrl", row.getSourceUrl());
        enrichOpportunityPeriodFields(item, row);
        return item;
    }

    @SuppressWarnings("unchecked")
    private void enrichOpportunityPeriodFields(Map<String, Object> item, DouyinOpportunityProduct row) {
        Map<String, Object> overview = parseJsonObject(row.getOverviewJson());
        Map<String, Object> period = null;
        Object pm = overview.get("period_metrics");
        if (pm instanceof Map<?, ?> m) {
            period = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : m.entrySet()) {
                period.put(String.valueOf(e.getKey()), e.getValue());
            }
        }
        Map<String, Object> indicator = null;
        Object fromList = overview.get("from_list");
        if (fromList instanceof Map<?, ?> fl) {
            Object ind = fl.get("clue_indicator");
            if (ind instanceof Map<?, ?> im) {
                indicator = new LinkedHashMap<>();
                for (Map.Entry<?, ?> e : im.entrySet()) {
                    indicator.put(String.valueOf(e.getKey()), e.getValue());
                }
            }
        }
        if (indicator == null) {
            Map<String, Object> raw = parseJsonObject(row.getRawJson());
            Object listItem = raw.get("list_item");
            if (listItem instanceof Map<?, ?> li) {
                Object ind = li.get("clue_indicator");
                if (ind instanceof Map<?, ?> im) {
                    indicator = new LinkedHashMap<>();
                    for (Map.Entry<?, ?> e : im.entrySet()) {
                        indicator.put(String.valueOf(e.getKey()), e.getValue());
                    }
                }
                Object card = li.get("query_clue_card_info");
                if (card instanceof Map<?, ?> cm && period == null) {
                    Map<String, Object> day = new LinkedHashMap<>();
                    day.put("search_popularity", cm.get("search_popularity"));
                    Map<String, Object> built = new LinkedHashMap<>();
                    built.put("day", day);
                    if (indicator != null) {
                        Map<String, Object> d7 = new LinkedHashMap<>();
                        d7.put("seven_day_sales", indicator.get("seven_day_sales"));
                        built.put("d7", d7);
                        Map<String, Object> d30 = new LinkedHashMap<>();
                        d30.put("search_pv_cnt_range", indicator.get("search_pv_cnt_range"));
                        d30.put("search_pv_cnt_30d_rate", indicator.get("search_pv_cnt_30d_rate"));
                        d30.put("pay_amount_ind_range", indicator.get("pay_amount_ind_range"));
                        d30.put("pay_amount_ind_30d_rate", indicator.get("pay_amount_ind_30d_rate"));
                        built.put("d30", d30);
                    }
                    period = built;
                }
            }
        }
        if (period != null) {
            item.put("periodMetrics", period);
        }
        if (indicator != null) {
            if (item.get("searchPvCnt") == null) item.put("searchPvCnt", indicator.get("search_pv_cnt"));
            if (item.get("searchPv30dRate") == null) item.put("searchPv30dRate", indicator.get("search_pv_cnt_30d_rate"));
            if (item.get("sevenDaySales") == null) item.put("sevenDaySales", indicator.get("seven_day_sales"));
            if (item.get("payAmt") == null) item.put("payAmt", indicator.get("pay_amount_ind"));
            if (item.get("demandSupplyRate") == null) item.put("demandSupplyRate", indicator.get("demand_supply_rate"));
            if (item.get("payOrderCnt") == null) item.put("payOrderCnt", indicator.get("pay_order_cnt"));
            if (item.get("payOrderCntRange") == null) {
                item.put("payOrderCntRange", indicator.get("pay_order_cnt_range"));
            }
        }
        Object day = period == null ? null : period.get("day");
        if (day instanceof Map<?, ?> dm && item.get("searchPopularity") == null) {
            item.put("searchPopularity", dm.get("search_popularity"));
        }
    }

    private Map<String, Object> parseJsonObject(String json) {
        try {
            Object value = objectMapper.readValue(
                    json == null || json.isBlank() ? "{}" : json,
                    new TypeReference<Object>() {}
            );
            if (value instanceof Map<?, ?> map) {
                Map<String, Object> out = new LinkedHashMap<>();
                for (Map.Entry<?, ?> e : map.entrySet()) {
                    out.put(String.valueOf(e.getKey()), e.getValue());
                }
                return out;
            }
        } catch (Exception ignored) {
            // fall through
        }
        return new LinkedHashMap<>();
    }

    private List<Object> parseJsonArray(String json) {
        try {
            Object value = objectMapper.readValue(
                    json == null || json.isBlank() ? "[]" : json,
                    new TypeReference<Object>() {}
            );
            if (value instanceof List<?> list) {
                return new ArrayList<>(list);
            }
        } catch (Exception ignored) {
            // fall through
        }
        return new ArrayList<>();
    }

    private Map<String, Object> toCompassDto(DouyinCompassSnapshot row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("storeId", row.getStoreId());
        item.put("reportDay", row.getReportDay());
        item.put("dateType", row.getDateType());
        item.put("shopName", row.getShopName());
        item.put("payAmt", row.getPayAmt());
        item.put("payCnt", row.getPayCnt());
        item.put("payUcnt", row.getPayUcnt());
        item.put("incomeAmt", row.getIncomeAmt());
        item.put("perUsrPayAmt", row.getPerUsrPayAmt());
        item.put("productShowUcnt", row.getProductShowUcnt());
        item.put("productShowCnt", row.getProductShowCnt());
        item.put("productClickUcnt", row.getProductClickUcnt());
        item.put("productClickCnt", row.getProductClickCnt());
        item.put("showClickRate", row.getShowClickRate());
        item.put("clickPayRate", row.getClickPayRate());
        item.put("settlementAmt", row.getSettlementAmt());
        item.put("refundAmt", row.getRefundAmt());
        item.put("refundRate", row.getRefundRate());
        item.put("expScore", row.getExpScore());
        item.put("expProduct", row.getExpProduct());
        item.put("expService", row.getExpService());
        item.put("expLogistics", row.getExpLogistics());
        item.put("syncedAt", row.getSyncedAt());
        item.put("sourceUrl", row.getSourceUrl());
        try {
            item.put("carriers", objectMapper.readValue(
                    row.getCarrierJson() == null || row.getCarrierJson().isBlank() ? "[]" : row.getCarrierJson(),
                    new TypeReference<List<Map<String, Object>>>() {}
            ));
        } catch (Exception ex) {
            item.put("carriers", List.of());
        }
        try {
            item.put("metrics", objectMapper.readValue(
                    row.getMetricsJson() == null || row.getMetricsJson().isBlank() ? "{}" : row.getMetricsJson(),
                    new TypeReference<Map<String, Object>>() {}
            ));
        } catch (Exception ex) {
            item.put("metrics", Map.of());
        }
        return item;
    }

    @Transactional
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !DouyinAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        Long tenantId = task.getTenantId();
        Map<String, Object> payload = parseJson(task.getPayloadJson());
        if (DouyinAgentTasks.LOGIN_OPEN.equals(task.getTaskType())
                || DouyinAgentTasks.SESSION_PROBE.equals(task.getTaskType())) {
            Map<String, Object> session = result == null ? Map.of() : result;
            Object nested = session.get("session");
            if (nested instanceof Map<?, ?> map) {
                Map<String, Object> copy = new LinkedHashMap<>();
                for (Map.Entry<?, ?> e : map.entrySet()) {
                    copy.put(String.valueOf(e.getKey()), e.getValue());
                }
                session = copy;
            }
            Map<String, Object> snap = new LinkedHashMap<>(session);
            snap.put("tenant_id", tenantId);
            if ("success".equalsIgnoreCase(status)) {
                boolean loggedIn = Boolean.TRUE.equals(snap.get("logged_in")) || Boolean.TRUE.equals(snap.get("ready"));
                snap.put("logged_in", loggedIn);
                snap.put("ready", loggedIn);
                snap.put("requires_auth", !loggedIn);
                snap.put("profile_busy", false);
                snap.putIfAbsent("message", loggedIn ? "抖店已登录" : "登录未完成，请重试打开登录");
            } else {
                snap.put("logged_in", false);
                snap.put("ready", false);
                snap.put("requires_auth", true);
                snap.put("profile_busy", false);
                snap.put("message", errorMessage == null || errorMessage.isBlank()
                        ? AppErrorCode.DY_SYNC_FAILED.getUserMessage()
                        : errorMessage);
            }
            writeSessionSnapshot(tenantId, snap);
            return;
        }

        if (!DouyinAgentTasks.SYNC.equals(task.getTaskType())
                && !DouyinAgentTasks.PRODUCTS_SYNC.equals(task.getTaskType())) {
            return;
        }
        String jobId = text(payload.get("job_id"));
        DouyinSyncJob job = jobId.isBlank()
                ? syncJobRepository.findFirstByTenantIdAndAgentTaskId(tenantId, task.getId()).orElse(null)
                : syncJobRepository.findByIdAndTenantId(jobId, tenantId).orElse(null);
        if (job == null) {
            return;
        }
        String now = now();
        job.setUpdatedAt(now);
        job.setFinishedAt(now);
        if ("success".equalsIgnoreCase(status)) {
            boolean partial = result != null && Boolean.TRUE.equals(result.get("partial"));
            job.setStatus(partial ? "partial" : "success");
            if (result != null) {
                if (result.get("orders_count") instanceof Number n) {
                    job.setOrdersCount(n.intValue());
                }
                if (result.get("issues_count") instanceof Number n) {
                    job.setIssuesCount(n.intValue());
                }
                if (result.get("products_count") instanceof Number n) {
                    job.setProductsCount(n.intValue());
                }
                job.setMessage(text(result.get("message")));
            }
            job.setErrorCode("");
            job.setErrorMessage("");
        } else {
            job.setStatus("failed");
            job.setErrorCode(errorCode == null || errorCode.isBlank()
                    ? AppErrorCode.DY_SYNC_FAILED.getCode()
                    : errorCode);
            job.setErrorMessage(errorMessage == null ? "" : errorMessage);
        }
        syncJobRepository.save(job);
    }

    @Transactional
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null) {
            return;
        }
        if (!DouyinAgentTasks.SYNC.equals(task.getTaskType())
                && !DouyinAgentTasks.PRODUCTS_SYNC.equals(task.getTaskType())) {
            return;
        }
        Map<String, Object> payload = parseJson(task.getPayloadJson());
        String jobId = text(payload.get("job_id"));
        if (jobId.isBlank()) {
            return;
        }
        syncJobRepository.findByIdAndTenantId(jobId, task.getTenantId()).ifPresent(job -> {
            job.setStatus("running");
            job.setUpdatedAt(now());
            syncJobRepository.save(job);
        });
    }

    private void validateStoreMapping(Long tenantId, String storeId) {
        List<PlatformAccount> shops = platformAccountRepository.findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "douyin");
        if (shops.isEmpty()) {
            return;
        }
        if (storeId != null && !storeId.isBlank()) {
            PlatformAccount match = shops.stream()
                    .filter(s -> storeId.trim().equals(s.getId()))
                    .findFirst()
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.ACCOUNT_NOT_FOUND.getUserMessage()));
            return;
        }
        if (shops.size() > 1) {
            boolean missing = shops.stream().anyMatch(s ->
                    s.getExternalShopId() == null || s.getExternalShopId().isBlank());
            if (missing) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST,
                        AppErrorCode.DY_SHOP_MAPPING_REQUIRED.getUserMessage()
                );
            }
        }
    }

    private DouyinOrder mapOrder(
            Long tenantId,
            String storeId,
            String reportDay,
            Map<String, Object> src,
            String now
    ) {
        String orderNo = firstNonBlank(text(src.get("order_no")), text(src.get("orderNo")));
        String sku = firstNonBlank(text(src.get("sku")), "");
        String orderKey = tenantId + "|" + storeId + "|" + orderNo + "|" + sku;
        DouyinOrder order = new DouyinOrder();
        order.setId(UUID.nameUUIDFromBytes(orderKey.getBytes()).toString());
        order.setTenantId(tenantId);
        order.setStoreId(storeId);
        order.setExternalShopId(text(src.get("external_shop_id")));
        order.setReportDay(reportDay);
        order.setOrderNo(orderNo);
        order.setProductName(firstNonBlank(text(src.get("product_name")), text(src.get("productName"))));
        order.setChannel(text(src.get("channel")));
        order.setSku(sku);
        order.setQuantity(intVal(src.get("quantity"), 1));
        order.setAmount(doubleVal(src.get("amount"), 0d));
        order.setCurrency(firstNonBlank(text(src.get("currency")), "CNY"));
        order.setStatus(normalizeStatus(firstNonBlank(text(src.get("status")), "待处理")));
        order.setShipDeadline(firstNonBlank(text(src.get("ship_deadline")), text(src.get("shipDeadline"))));
        order.setOrderedAt(firstNonBlank(text(src.get("ordered_at")), text(src.get("orderedAt"))));
        order.setOrderKey(orderKey);
        String rawJson = firstNonBlank(text(src.get("raw_json")), text(src.get("rawJson")));
        if (!rawJson.isBlank()) {
            order.setRawJson(rawJson);
        } else {
            try {
                order.setRawJson(objectMapper.writeValueAsString(src));
            } catch (Exception ex) {
                order.setRawJson("{}");
            }
        }
        order.setCreatedAt(now);
        order.setUpdatedAt(now);
        return order;
    }

    private String normalizeStatus(String raw) {
        String s = raw == null ? "" : raw.trim();
        if (s.isEmpty()) {
            return "待处理";
        }
        if (s.contains("取消")) {
            return "已取消";
        }
        if (s.contains("发货") && (s.contains("已") || s.toLowerCase(Locale.ROOT).contains("ship"))) {
            return "已发货";
        }
        if (s.contains("待发") || s.contains("备货")) {
            return "待发货";
        }
        if (List.of("待处理", "待发货", "已发货", "已取消").contains(s)) {
            return s;
        }
        return s.length() > 32 ? s.substring(0, 32) : s;
    }

    private Map<String, Object> toOrderDto(DouyinOrder row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("orderNo", row.getOrderNo());
        item.put("storeId", row.getStoreId());
        item.put("sku", row.getSku());
        item.put("productName", row.getProductName());
        String productId = extractOrderProductId(row);
        if (!productId.isBlank()) {
            item.put("productId", productId);
        }
        item.put("quantity", row.getQuantity());
        item.put("amount", row.getAmount());
        item.put("currency", row.getCurrency());
        item.put("channel", row.getChannel());
        item.put("status", row.getStatus());
        item.put("orderedAt", row.getOrderedAt());
        item.put("shipDeadline", row.getShipDeadline());
        return item;
    }

    /** 从订单 raw_json.product_item[].product_id 解析抖店商品 ID（标题可能与商品库不一致） */
    private String extractOrderProductId(DouyinOrder row) {
        String raw = row == null ? "" : firstNonBlank(row.getRawJson(), "");
        if (raw.isBlank()) {
            return "";
        }
        try {
            var root = objectMapper.readTree(raw);
            var items = root.get("product_item");
            if (items != null && items.isArray()) {
                for (var node : items) {
                    if (node == null || node.isNull()) continue;
                    String id = firstNonBlank(
                            node.path("product_id").asText(""),
                            node.path("productId").asText("")
                    );
                    if (!id.isBlank()) {
                        return id;
                    }
                }
            }
            return firstNonBlank(
                    root.path("product_id").asText(""),
                    root.path("productId").asText("")
            );
        } catch (Exception ignored) {
            return "";
        }
    }

    private Map<String, Object> toProductDto(DouyinProduct row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("storeId", row.getStoreId());
        item.put("productId", row.getProductId());
        item.put("productName", row.getProductName());
        item.put("status", row.getStatus());
        item.put("statusLabel", row.getStatusLabel());
        item.put("price", row.getPrice());
        item.put("stock", row.getStock());
        item.put("sales", row.getSales());
        item.put("mainImage", row.getMainImage());
        item.put("category", row.getCategory());
        item.put("articleNo", row.getArticleNo());
        item.put("qualityScore", row.getQualityScore());
        item.put("publishedAt", row.getPublishedAt());
        item.put("goodRate", row.getGoodRate());
        item.put("skuCount", row.getSkuCount());
        item.put("syncedAt", row.getSyncedAt());
        item.put("updatedAt", row.getUpdatedAt());
        return item;
    }

    private Map<String, Object> toIssueDto(DouyinIssue row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("storeId", row.getStoreId());
        item.put("type", row.getType());
        item.put("typeLabel", firstNonBlank(row.getTypeLabel(), DouyinIssueUpsert.defaultLabel(row.getType())));
        item.put("sku", row.getSku());
        item.put("productName", row.getProductName());
        item.put("productImage", row.getProductImage() == null ? "" : row.getProductImage());
        item.put("mainImage", row.getProductImage() == null ? "" : row.getProductImage());
        item.put("detail", row.getDetail());
        String severity = firstNonBlank(row.getPriority(), "medium");
        item.put("severity", severity);
        item.put("priority", severity);
        item.put("resolved", row.getResolved() != null && row.getResolved() == 1);
        item.put("reportedAt", row.getReportedAt());
        item.put("resolvedAt", row.getResolvedAt());
        item.put("note", row.getNote());
        item.put("externalId", row.getExternalId());
        item.put("source", row.getSource());
        item.put("updatedAt", row.getUpdatedAt());
        return item;
    }

    private DouyinProduct mapProduct(Long tenantId, String storeId, Map<String, Object> src, String now) {
        String productId = firstNonBlank(text(src.get("product_id")), text(src.get("productId")));
        String productName = firstNonBlank(text(src.get("product_name")), text(src.get("productName")));
        String productKey = tenantId + "|" + storeId + "|" + (productId.isBlank() ? productName : productId);
        DouyinProduct product = new DouyinProduct();
        product.setId(UUID.nameUUIDFromBytes(productKey.getBytes()).toString());
        product.setTenantId(tenantId);
        product.setStoreId(storeId);
        product.setExternalShopId(text(src.get("external_shop_id")));
        product.setProductId(productId);
        product.setProductName(productName);
        product.setStatus(firstNonBlank(text(src.get("status")), ""));
        product.setStatusLabel(firstNonBlank(text(src.get("status_label")), text(src.get("statusLabel")), product.getStatus()));
        product.setPrice(doubleVal(src.get("price")));
        product.setStock(doubleVal(src.get("stock")));
        product.setSales(doubleVal(src.get("sales")));
        product.setMainImage(firstNonBlank(text(src.get("main_image")), text(src.get("mainImage"))));
        product.setCategory(text(src.get("category")));
        product.setArticleNo(firstNonBlank(text(src.get("article_no")), text(src.get("articleNo"))));
        Double qualityScore = doubleVal(src.get("quality_score"));
        if (qualityScore == null) {
            qualityScore = doubleVal(src.get("qualityScore"));
        }
        product.setQualityScore(qualityScore);
        product.setPublishedAt(firstNonBlank(text(src.get("published_at")), text(src.get("publishedAt"))));
        Double goodRate = doubleVal(src.get("good_rate"));
        if (goodRate == null) {
            goodRate = doubleVal(src.get("goodRate"));
        }
        product.setGoodRate(goodRate);
        product.setSkuCount(intVal(src.get("sku_count"), intVal(src.get("skuCount"), 0)));
        product.setSkusJson(firstNonBlank(text(src.get("skus_json")), text(src.get("skusJson"))));
        product.setRawJson(firstNonBlank(text(src.get("raw_json")), text(src.get("rawJson"))));
        product.setProductKey(productKey);
        product.setSyncedAt(now);
        product.setCreatedAt(now);
        product.setUpdatedAt(now);
        return product;
    }

    private Map<String, Object> toJobDto(DouyinSyncJob job) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", job.getId());
        data.put("status", job.getStatus());
        data.put("scope", job.getScope());
        data.put("store_id", job.getStoreId());
        data.put("agent_task_id", job.getAgentTaskId());
        data.put("orders_count", job.getOrdersCount());
        data.put("issues_count", job.getIssuesCount());
        data.put("products_count", job.getProductsCount());
        data.put("error_code", job.getErrorCode());
        data.put("error_message", job.getErrorMessage());
        data.put("message", job.getMessage());
        data.put("created_at", job.getCreatedAt());
        data.put("updated_at", job.getUpdatedAt());
        data.put("finished_at", job.getFinishedAt());
        return data;
    }

    private IntegrationAgent requireOnlineAgent(Long tenantId) {
        IntegrationAgent agent = agentPresenceService.findLatestOnlineAgentForTenant(tenantId);
        if (agent == null || agent.getId() == null || agent.getId().isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    AppErrorCode.DY_AGENT_OFFLINE.getUserMessage()
            );
        }
        return agent;
    }

    /**
     * Drop zombie Douyin browser tasks so a dead/restarted Helper cannot block「打开登录」forever.
     * Orphans: claimed by another agent id. Stale: pending &gt;2m, probe running &gt;3m, login/sync running &gt;12m.
     */
    private void reclaimStaleBusyTasks(Long tenantId, String onlineAgentId) {
        String nowTs = now();
        LocalDateTime nowDt = LocalDateTime.now();
        String pendingCutoff = nowDt.minusMinutes(2).format(TS);
        String probeCutoff = nowDt.minusMinutes(3).format(TS);
        String loginCutoff = nowDt.minusMinutes(12).format(TS);
        String agentId = onlineAgentId == null ? "" : onlineAgentId;

        int orphaned = jdbc.update(
                """
                UPDATE agent_task
                SET status = 'failed',
                    error_code = 'DY_SYNC_FAILED',
                    error_message = '助手已重启，旧登录任务已取消，请重新打开登录',
                    finished_at = ?
                WHERE tenant_id = ?
                  AND status IN ('pending', 'running')
                  AND task_type IN (
                    'douyin_session_probe',
                    'douyin_login_open',
                    'douyin_sync',
                    'douyin_products_sync'
                  )
                  AND (agent_id IS NULL OR agent_id = '' OR agent_id <> ?)
                """,
                nowTs,
                tenantId,
                agentId
        );
        int stale = jdbc.update(
                """
                UPDATE agent_task
                SET status = 'failed',
                    error_code = 'DY_SYNC_FAILED',
                    error_message = '登录任务已过期，请重新打开登录',
                    finished_at = ?
                WHERE tenant_id = ?
                  AND status IN ('pending', 'running')
                  AND task_type IN (
                    'douyin_session_probe',
                    'douyin_login_open',
                    'douyin_sync',
                    'douyin_products_sync'
                  )
                  AND (
                    (status = 'pending' AND created_at <> '' AND created_at < ?)
                    OR (
                      task_type = 'douyin_session_probe'
                      AND status = 'running'
                      AND CASE WHEN started_at IS NULL OR started_at = '' THEN created_at ELSE started_at END < ?
                    )
                    OR (
                      task_type IN ('douyin_login_open', 'douyin_sync', 'douyin_products_sync')
                      AND status = 'running'
                      AND CASE WHEN started_at IS NULL OR started_at = '' THEN created_at ELSE started_at END < ?
                    )
                  )
                """,
                nowTs,
                tenantId,
                pendingCutoff,
                probeCutoff,
                loginCutoff
        );
        if (orphaned + stale > 0) {
            Map<String, Object> snap = readSessionSnapshot(tenantId);
            snap.put("profile_busy", false);
            snap.put("ready", false);
            snap.putIfAbsent("logged_in", false);
            snap.put("requires_auth", true);
            snap.put("message", "请重新打开登录窗口完成抖店登录");
            snap.remove("error_code");
            writeSessionSnapshot(tenantId, snap);
        }
    }

    private boolean hasRunningBusy(Long tenantId) {
        Integer count = jdbc.queryForObject(
                """
                SELECT COUNT(1) FROM agent_task
                WHERE tenant_id = ?
                  AND status IN ('pending', 'running')
                  AND task_type IN (
                    'douyin_session_probe',
                    'douyin_login_open',
                    'douyin_sync',
                    'douyin_products_sync'
                  )
                """,
                Integer.class,
                tenantId
        );
        return count != null && count > 0;
    }

    private Map<String, Object> readSessionSnapshot(Long tenantId) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT payload_json FROM douyin_session_snapshot WHERE tenant_id = ? LIMIT 1",
                tenantId
        );
        if (rows.isEmpty()) {
            Map<String, Object> defaults = new LinkedHashMap<>();
            defaults.put("tenant_id", tenantId);
            defaults.put("ready", false);
            defaults.put("logged_in", false);
            defaults.put("requires_auth", true);
            defaults.put("profile_busy", false);
            defaults.put("message", "尚未登录抖店商家后台");
            defaults.put("shop_count", 0);
            defaults.put("shops", List.of());
            return defaults;
        }
        return parseJson(String.valueOf(rows.get(0).get("payload_json")));
    }

    private void writeSessionSnapshot(Long tenantId, Map<String, Object> payload) {
        String json;
        try {
            json = objectMapper.writeValueAsString(payload == null ? Map.of() : payload);
        } catch (Exception ex) {
            json = "{}";
        }
        jdbc.update(
                """
                INSERT INTO douyin_session_snapshot (tenant_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
                """,
                tenantId,
                json,
                now()
        );
    }

    private void insertAgentTask(
            Long tenantId,
            String taskId,
            String taskType,
            Map<String, Object> payload,
            String agentId
    ) {
        String payloadJson;
        try {
            payloadJson = objectMapper.writeValueAsString(payload);
        } catch (Exception ex) {
            payloadJson = "{}";
        }
        jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, agent_id, task_type, status, payload_json, result_json,
                  error_code, error_message, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                taskId,
                tenantId,
                agentId == null ? "" : agentId,
                taskType,
                "pending",
                payloadJson,
                "{}",
                "",
                "",
                now(),
                "",
                ""
        );
    }

    private Map<String, Object> parseJson(String json) {
        try {
            return objectMapper.readValue(
                    json == null || json.isBlank() ? "{}" : json,
                    new TypeReference<Map<String, Object>>() {}
            );
        } catch (Exception ex) {
            return new LinkedHashMap<>();
        }
    }

    private String normalizeScope(String scope) {
        return scope == null || scope.isBlank() ? "orders" : scope.trim().toLowerCase(Locale.ROOT);
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static String firstNonBlank(String... values) {
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

    private static int intVal(Object value, int fallback) {
        if (value instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value).trim());
        } catch (Exception ex) {
            return fallback;
        }
    }

    private static double doubleVal(Object value, double fallback) {
        if (value instanceof Number n) {
            return n.doubleValue();
        }
        try {
            String text = String.valueOf(value).trim();
            if (text.isEmpty() || "null".equalsIgnoreCase(text)) {
                return fallback;
            }
            return Double.parseDouble(text);
        } catch (Exception ex) {
            return fallback;
        }
    }

    private static Double doubleVal(Object value) {
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value).trim();
        if (text.isEmpty() || "null".equalsIgnoreCase(text)) {
            return null;
        }
        if (value instanceof Number n) {
            return n.doubleValue();
        }
        try {
            return Double.parseDouble(text);
        } catch (Exception ex) {
            return null;
        }
    }
}
