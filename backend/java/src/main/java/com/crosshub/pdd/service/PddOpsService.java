package com.crosshub.pdd.service;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.pdd.entity.PddCompassSnapshot;
import com.crosshub.pdd.entity.PddIssue;
import com.crosshub.pdd.entity.PddOrder;
import com.crosshub.pdd.entity.PddProduct;
import com.crosshub.pdd.entity.PddSyncJob;
import com.crosshub.pdd.repository.PddCompassSnapshotRepository;
import com.crosshub.pdd.repository.PddIssueRepository;
import com.crosshub.pdd.repository.PddOrderRepository;
import com.crosshub.pdd.repository.PddProductRepository;
import com.crosshub.pdd.repository.PddSyncJobRepository;
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
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * 拼多多运营服务。对齐抖音 {@code DouyinOpsService} 接入模式：
 * Agent + Playwright 爬取卖家后台 → ingest 回写 → 读 API。
 *
 * <p>数据 scope：订单（按时间段 {@code date_window} 分）、商品列表、经营罗盘。
 *
 * <p><b>XHR 契约待账号到位 probe 后填入 Python {@code pdd_tasks.py}</b>，
 * 本服务仅负责任务调度、回写入库与读 API，数据流闭环不依赖具体 XHR。
 */
@Service
public class PddOpsService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");

    private final PddOrderRepository orderRepository;
    private final PddProductRepository productRepository;
    private final PddCompassSnapshotRepository compassSnapshotRepository;
    private final PddSyncJobRepository syncJobRepository;
    private final PddIssueRepository issueRepository;
    private final PlatformAccountRepository platformAccountRepository;
    private final AgentPresenceService agentPresenceService;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public PddOpsService(
            PddOrderRepository orderRepository,
            PddProductRepository productRepository,
            PddCompassSnapshotRepository compassSnapshotRepository,
            PddSyncJobRepository syncJobRepository,
            PddIssueRepository issueRepository,
            PlatformAccountRepository platformAccountRepository,
            AgentPresenceService agentPresenceService,
            DataScopeService dataScopeService,
            AuthContext authContext,
            JdbcTemplate jdbc,
            ObjectMapper objectMapper
    ) {
        this.orderRepository = orderRepository;
        this.productRepository = productRepository;
        this.compassSnapshotRepository = compassSnapshotRepository;
        this.syncJobRepository = syncJobRepository;
        this.issueRepository = issueRepository;
        this.platformAccountRepository = platformAccountRepository;
        this.agentPresenceService = agentPresenceService;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    // ---------------------------------------------------------------- session

    public Map<String, Object> session() {
        return session(null);
    }

    public Map<String, Object> session(String storeIdOrNull) {
        Long tenantId = dataScopeService.requireTenantId();
        boolean agentOnline = agentPresenceService.isAgentOnline(tenantId);
        boolean profileBusy = hasRunningBusy(tenantId);
        Map<String, Object> snapshot = readSessionSnapshot(tenantId, storeIdOrNull);
        boolean loggedIn = Boolean.TRUE.equals(snapshot.get("logged_in")) || Boolean.TRUE.equals(snapshot.get("ready"));
        Map<String, Object> out = new LinkedHashMap<>(snapshot);
        out.put("tenant_id", tenantId);
        out.put("store_id", normalizeStoreKey(storeIdOrNull));
        out.put("agent_online", agentOnline);
        out.put("profile_busy", profileBusy || Boolean.TRUE.equals(snapshot.get("profile_busy")));
        out.put("logged_in", loggedIn);
        out.put("ready", loggedIn && agentOnline && !profileBusy);
        out.putIfAbsent("requires_auth", !loggedIn);
        if (!agentOnline) {
            out.put("message", AppErrorCode.PDD_AGENT_OFFLINE.getUserMessage());
            out.put("requires_auth", true);
            out.put("ready", false);
        } else if (profileBusy) {
            out.putIfAbsent("message", "拼多多浏览器任务进行中，请稍候");
        } else if (!loggedIn) {
            out.putIfAbsent("message", "请打开登录窗口完成拼多多商家后台登录");
        }
        List<PlatformAccount> shops = platformAccountRepository.findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "pdd");
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

    // --------------------------------------------------------------- enqueue

    @Transactional
    public Map<String, Object> enqueueLoginOpen() {
        return enqueueLoginOpen(null);
    }

    @Transactional
    public Map<String, Object> enqueueLoginOpen(String storeIdOrNull) {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        reclaimStaleBusyTasks(tenantId, agent.getId());
        if (hasRunningBusy(tenantId)) {
            return Map.of(
                    "already_open", true,
                    "queued", false,
                    "message", "拼多多浏览器任务进行中；若本机没有弹出登录窗口，请重启 Sync Helper 后再点「打开登录」"
            );
        }
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        payload.put("store_id", storeIdOrNull == null ? "" : storeIdOrNull.trim());
        insertAgentTask(tenantId, taskId, PddAgentTasks.LOGIN_OPEN, payload, agent.getId());
        writeSessionSnapshot(tenantId, storeIdOrNull, Map.of(
                "tenant_id", tenantId,
                "ready", false,
                "logged_in", false,
                "requires_auth", true,
                "profile_busy", true,
                "message", "登录窗口已打开，请在弹出的浏览器中完成拼多多商家后台登录"
        ));
        return Map.of(
                "queued", true,
                "task_id", taskId,
                "message", "已通知本机助手打开拼多多登录窗口"
        );
    }

    @Transactional
    public Map<String, Object> enqueueSessionProbe() {
        return enqueueSessionProbe(null);
    }

    @Transactional
    public Map<String, Object> enqueueSessionProbe(String storeIdOrNull) {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        reclaimStaleBusyTasks(tenantId, agent.getId());
        if (hasRunningBusy(tenantId)) {
            return Map.of(
                    "queued", false,
                    "message", "拼多多浏览器任务进行中，请稍候再刷新登录状态"
            );
        }
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        payload.put("store_id", storeIdOrNull == null ? "" : storeIdOrNull.trim());
        insertAgentTask(tenantId, taskId, PddAgentTasks.SESSION_PROBE, payload, agent.getId());
        writeSessionSnapshot(tenantId, storeIdOrNull, Map.of(
                "tenant_id", tenantId,
                "ready", false,
                "logged_in", false,
                "requires_auth", true,
                "profile_busy", true,
                "message", "正在检测拼多多登录状态…"
        ));
        return Map.of(
                "queued", true,
                "task_id", taskId,
                "message", "已通知本机助手检测拼多多登录状态"
        );
    }

    /**
     * 触发同步。scope ∈ orders / products / compass / all；date_window ∈ today / d1 / d7 / d30 / d90
     * （仅 orders scope 生效，对齐用户「订单按时间段分」需求）。
     */
    @Transactional
    public Map<String, Object> enqueueSync(String scope, boolean force, String storeId, String dateWindow) {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        if (storeId != null && "all".equalsIgnoreCase(storeId.trim())) {
            storeId = null;
        }
        String normalizedScope = normalizeScope(scope);
        if (!"orders".equals(normalizedScope)
                && !"products".equals(normalizedScope)
                && !"compass".equals(normalizedScope)
                && !"issues".equals(normalizedScope)
                && !"all".equals(normalizedScope)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }
        List<PddSyncJob> running = syncJobRepository.findByTenantIdAndStatusInOrderByCreatedAtDesc(
                tenantId, List.of("pending", "running"));
        if (!force && !running.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, AppErrorCode.PDD_SYNC_IN_PROGRESS.getUserMessage());
        }
        if (hasRunningBusy(tenantId) && !force) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, AppErrorCode.PDD_SYNC_IN_PROGRESS.getUserMessage());
        }
        validateStoreMapping(tenantId, storeId);

        String jobId = UUID.randomUUID().toString();
        String taskId = "agt_" + UUID.randomUUID();
        String now = now();
        PddSyncJob job = new PddSyncJob();
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
        if (dateWindow != null && !dateWindow.isBlank()) {
            payload.put("date_window", dateWindow.trim());
        }
        String taskType;
        if ("products".equals(normalizedScope)) {
            taskType = PddAgentTasks.PRODUCTS_SYNC;
        } else if ("issues".equals(normalizedScope)) {
            taskType = PddAgentTasks.ISSUES_SYNC;
        } else {
            taskType = PddAgentTasks.SYNC;
        }
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
        PddSyncJob job = syncJobRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.NOT_FOUND.getUserMessage()));
        return toJobDto(job);
    }

    // ------------------------------------------------------------------ orders

    /** 今日订单（date_window=today 的快捷） */
    public Map<String, Object> todayOrders(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        String today = LocalDate.now().toString();
        List<PddOrder> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = orderRepository.findByTenantIdAndReportDayAndStoreIdOrderByOrderedAtDesc(
                    tenantId, today, storeId.trim());
        } else {
            rows = orderRepository.findByTenantIdAndReportDayOrderByOrderedAtDesc(tenantId, today);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("report_day", today);
        out.put("items", rows.stream().map(PddOpsService::toOrderDto).toList());
        out.put("total", rows.size());
        return out;
    }

    /** 按时间段查询订单。dateWindow ∈ today / d1 / d7 / d30 / d90 */
    public Map<String, Object> ordersByWindow(String storeId, String dateWindow) {
        Long tenantId = dataScopeService.requireTenantId();
        String window = dateWindow == null || dateWindow.isBlank() ? "today" : dateWindow.trim();
        // Agent 统一按 d30 标签入库（避免多窗口重复），因此按日期范围（report_day）查询，
        // 保证 today / d1 / d7 / d90 等窗口都能返回正确数据。
        List<String> reportDays = windowDayList(window);
        List<PddOrder> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = orderRepository.findByTenantIdAndStoreIdAndReportDayInOrderByOrderedAtDesc(
                    tenantId, storeId.trim(), reportDays);
        } else {
            rows = orderRepository.findByTenantIdAndReportDayInOrderByOrderedAtDesc(tenantId, reportDays);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("date_window", window);
        out.put("items", rows.stream().map(PddOpsService::toOrderDto).toList());
        out.put("total", rows.size());
        return out;
    }

    /** 生成窗口覆盖的日期列表（含今天），语义与 agent 端 _window_day_list 对齐。 */
    static List<String> windowDayList(String dateWindow) {
        String window = dateWindow == null || dateWindow.isBlank() ? "today" : dateWindow.trim().toLowerCase();
        int offset = switch (window) {
            case "d1" -> 1;
            case "d7" -> 6;
            case "d30" -> 29;
            case "d90" -> 89;
            default -> 0;
        };
        LocalDate today = LocalDate.now();
        List<String> days = new ArrayList<>(offset + 1);
        for (int i = offset; i >= 0; i--) {
            days.add(today.minusDays(i).toString());
        }
        return days;
    }

    // ---------------------------------------- operations (对齐 alibaba1688 RetailOpsService)

    /**
     * 经营汇总（对齐 Alibaba1688RetailOpsService.summary）。
     * 按 startDate~endDate 范围聚合 pdd_order，返回 paid_sales/refund_amount/net_sales/
     * paid_order_count/refund_order_count/average_order_value/sold_quantity/sold_product_count。
     *
     * <p>agent 携带 cookie 抓取订单 XHR 并写入 pdd_order 后，本方法即可直接读取计算。
     */
    public Map<String, Object> summary(Long tenantId, LocalDate start, LocalDate end, String storeId) {
        String startStr = start.toString();
        String endStr = end.toString();
        StringBuilder sql = new StringBuilder(
                "SELECT " +
                "  COALESCE(SUM(CAST(paid_amount AS REAL)), 0) AS paid_sales, " +
                "  COALESCE(SUM(CAST(refunded_amount AS REAL)), 0) AS refund_amount, " +
                "  COALESCE(SUM(CAST(paid_amount AS REAL)) - SUM(CAST(refunded_amount AS REAL)), 0) AS net_sales, " +
                "  COUNT(DISTINCT order_no) AS paid_order_count, " +
                "  SUM(CASE WHEN CAST(refunded_amount AS REAL) > 0 THEN 1 ELSE 0 END) AS refund_order_count, " +
                "  COALESCE(SUM(quantity), 0) AS sold_quantity, " +
                "  COUNT(DISTINCT product_name) AS sold_product_count " +
                "FROM pdd_order " +
                "WHERE tenant_id = ? AND report_day >= ? AND report_day <= ?"
        );
        List<Object> params = new ArrayList<>();
        params.add(tenantId);
        params.add(startStr);
        params.add(endStr);
        if (storeId != null && !storeId.isBlank() && !"all".equals(storeId)) {
            sql.append(" AND store_id = ?");
            params.add(storeId);
        }
        Map<String, Object> row = jdbc.queryForMap(sql.toString(), params.toArray());
        double paidSales = toDouble(row.get("paid_sales"));
        long paidOrderCount = toLong(row.get("paid_order_count"));
        double aov = paidOrderCount > 0 ? paidSales / paidOrderCount : 0d;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("paid_sales", paidSales);
        out.put("refund_amount", toDouble(row.get("refund_amount")));
        out.put("net_sales", toDouble(row.get("net_sales")));
        out.put("paid_order_count", paidOrderCount);
        out.put("refund_order_count", toLong(row.get("refund_order_count")));
        out.put("average_order_value", aov);
        out.put("sold_quantity", toLong(row.get("sold_quantity")));
        out.put("sold_product_count", toLong(row.get("sold_product_count")));
        return out;
    }

    /**
     * 销售额 / 订单趋势（对齐 Alibaba1688RetailOpsService.trend）。
     * 按日返回 [{date, paid_sales, net_sales, paid_order_count}]，前端 ECharts 直接渲染。
     */
    public List<Map<String, Object>> trend(Long tenantId, LocalDate start, LocalDate end, String storeId) {
        String startStr = start.toString();
        String endStr = end.toString();
        StringBuilder sql = new StringBuilder(
                "SELECT report_day AS date, " +
                "  COALESCE(SUM(CAST(paid_amount AS REAL)), 0) AS paid_sales, " +
                "  COALESCE(SUM(CAST(paid_amount AS REAL)) - SUM(CAST(refunded_amount AS REAL)), 0) AS net_sales, " +
                "  COUNT(DISTINCT order_no) AS paid_order_count " +
                "FROM pdd_order " +
                "WHERE tenant_id = ? AND report_day >= ? AND report_day <= ?"
        );
        List<Object> params = new ArrayList<>();
        params.add(tenantId);
        params.add(startStr);
        params.add(endStr);
        if (storeId != null && !storeId.isBlank() && !"all".equals(storeId)) {
            sql.append(" AND store_id = ?");
            params.add(storeId);
        }
        sql.append(" GROUP BY report_day ORDER BY report_day ASC");
        return jdbc.query(sql.toString(), (rs, n) -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("date", rs.getString("date"));
            m.put("paid_sales", rs.getDouble("paid_sales"));
            m.put("net_sales", rs.getDouble("net_sales"));
            m.put("paid_order_count", rs.getInt("paid_order_count"));
            return m;
        }, params.toArray());
    }

    /**
     * 多店铺经营总览（对齐 Alibaba1688RetailOpsService.overview）。
     * 仅当 selectedStoreId === 'all' 时调用，返回各店铺聚合 + total_* 合计 + store_count。
     */
    public Map<String, Object> overview(Long tenantId, LocalDate start, LocalDate end) {
        String startStr = start.toString();
        String endStr = end.toString();
        String sql =
                "SELECT store_id, " +
                "  COALESCE(SUM(CAST(paid_amount AS REAL)), 0) AS paid_sales, " +
                "  COALESCE(SUM(CAST(refunded_amount AS REAL)), 0) AS refund_amount, " +
                "  COALESCE(SUM(CAST(paid_amount AS REAL)) - SUM(CAST(refunded_amount AS REAL)), 0) AS net_sales, " +
                "  COUNT(DISTINCT order_no) AS paid_order_count, " +
                "  SUM(CASE WHEN CAST(refunded_amount AS REAL) > 0 THEN 1 ELSE 0 END) AS refund_order_count, " +
                "  COALESCE(SUM(quantity), 0) AS sold_quantity, " +
                "  COUNT(DISTINCT product_name) AS sold_product_count " +
                "FROM pdd_order " +
                "WHERE tenant_id = ? AND report_day >= ? AND report_day <= ? " +
                "GROUP BY store_id ORDER BY net_sales DESC";
        List<Map<String, Object>> stores = jdbc.query(sql, (rs, n) -> {
            double paidSales = rs.getDouble("paid_sales");
            long paidOrderCount = rs.getLong("paid_order_count");
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("store_id", rs.getString("store_id"));
            m.put("paid_sales", paidSales);
            m.put("refund_amount", rs.getDouble("refund_amount"));
            m.put("net_sales", rs.getDouble("net_sales"));
            m.put("paid_order_count", paidOrderCount);
            m.put("refund_order_count", rs.getLong("refund_order_count"));
            m.put("average_order_value", paidOrderCount > 0 ? paidSales / paidOrderCount : 0d);
            m.put("sold_quantity", rs.getLong("sold_quantity"));
            m.put("sold_product_count", rs.getLong("sold_product_count"));
            return m;
        }, tenantId, startStr, endStr);

        double totalPaidSales = 0d, totalRefundAmount = 0d, totalNetSales = 0d;
        long totalPaidOrderCount = 0L, totalRefundOrderCount = 0L;
        for (Map<String, Object> s : stores) {
            totalPaidSales += toDouble(s.get("paid_sales"));
            totalRefundAmount += toDouble(s.get("refund_amount"));
            totalNetSales += toDouble(s.get("net_sales"));
            totalPaidOrderCount += toLong(s.get("paid_order_count"));
            totalRefundOrderCount += toLong(s.get("refund_order_count"));
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("stores", stores);
        out.put("store_count", stores.size());
        out.put("total_paid_sales", totalPaidSales);
        out.put("total_refund_amount", totalRefundAmount);
        out.put("total_net_sales", totalNetSales);
        out.put("total_paid_order_count", totalPaidOrderCount);
        out.put("total_refund_order_count", totalRefundOrderCount);
        return out;
    }

    /**
     * 订单列表（对齐 Alibaba1688RetailOpsService.listOrders）。
     * 支持 startDate/endDate 范围 + status/keyword 过滤 + page/pageSize 分页。
     */
    public Map<String, Object> listOrders(Long tenantId, LocalDate start, LocalDate end,
                                          String status, String keyword, String storeId,
                                          int page, int pageSize) {
        String startStr = start == null ? null : start.toString();
        String endStr = end == null ? null : end.toString();
        StringBuilder where = new StringBuilder("WHERE tenant_id = ?");
        List<Object> params = new ArrayList<>();
        params.add(tenantId);
        if (startStr != null && endStr != null) {
            where.append(" AND report_day >= ? AND report_day <= ?");
            params.add(startStr);
            params.add(endStr);
        }
        if (storeId != null && !storeId.isBlank() && !"all".equals(storeId)) {
            where.append(" AND store_id = ?");
            params.add(storeId);
        }
        if (status != null && !status.isBlank()) {
            where.append(" AND LOWER(status) = LOWER(?)");
            params.add(status);
        }
        String kw = keyword == null ? "" : keyword.trim();
        if (!kw.isEmpty()) {
            where.append(" AND (order_no LIKE ? OR product_name LIKE ?)");
            String like = "%" + kw + "%";
            params.add(like);
            params.add(like);
        }

        String countSql = "SELECT COUNT(1) FROM pdd_order " + where;
        Long total = jdbc.queryForObject(countSql, Long.class, params.toArray());
        if (total == null) total = 0L;

        int safePage = Math.max(1, page);
        int safeSize = Math.max(1, Math.min(100, pageSize));
        int offset = (safePage - 1) * safeSize;
        List<Object> pageParams = new ArrayList<>(params);
        pageParams.add(safeSize);
        pageParams.add(offset);
        String listSql = "SELECT * FROM pdd_order " + where +
                " ORDER BY COALESCE(paid_at, ordered_at) DESC LIMIT ? OFFSET ?";
        List<PddOrder> rows = jdbc.query(listSql, (rs, n) -> {
            PddOrder o = new PddOrder();
            o.setId(rs.getString("id"));
            o.setTenantId(rs.getLong("tenant_id"));
            o.setStoreId(rs.getString("store_id"));
            o.setExternalShopId(rs.getString("external_shop_id"));
            o.setReportDay(rs.getString("report_day"));
            o.setDateWindow(rs.getString("date_window"));
            o.setOrderNo(rs.getString("order_no"));
            o.setProductName(rs.getString("product_name"));
            o.setChannel(rs.getString("channel"));
            o.setSku(rs.getString("sku"));
            o.setQuantity(rs.getInt("quantity"));
            o.setAmount(rs.getDouble("amount"));
            o.setCurrency(rs.getString("currency"));
            o.setStatus(rs.getString("status"));
            o.setShipDeadline(rs.getString("ship_deadline"));
            o.setOrderedAt(rs.getString("ordered_at"));
            o.setOrderKey(rs.getString("order_key"));
            o.setRawJson(rs.getString("raw_json"));
            o.setCreatedAt(rs.getString("created_at"));
            o.setUpdatedAt(rs.getString("updated_at"));
            o.setPaidAmount(rs.getString("paid_amount"));
            o.setRefundedAmount(rs.getString("refunded_amount"));
            o.setPaidAt(rs.getString("paid_at"));
            o.setRefundedAt(rs.getString("refunded_at"));
            o.setBuyerMasked(rs.getString("buyer_masked"));
            o.setSyncedAt(rs.getString("synced_at"));
            o.setUnitPrice(rs.getString("unit_price"));
            o.setItemAmount(rs.getString("item_amount"));
            o.setImageUrl(rs.getString("image_url"));
            o.setSkuText(rs.getString("sku_text"));
            return o;
        }, pageParams.toArray());

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", rows.stream().map(PddOpsService::toOrderDto).toList());
        out.put("total", total);
        out.put("page", safePage);
        out.put("page_size", safeSize);
        return out;
    }

    private static double toDouble(Object v) {
        if (v == null) return 0d;
        if (v instanceof Number n) return n.doubleValue();
        try { return Double.parseDouble(String.valueOf(v)); } catch (Exception e) { return 0d; }
    }

    private static String bestsellerTier(double salesQty) {
        if (salesQty >= 30) return "\u7206\u6b3e";
        if (salesQty >= 10) return "\u6f5c\u529b\u7206\u6b3e";
        if (salesQty >= 1) return "\u4e00\u822c";
        return "\u65e0\u9500\u91cf";
    }

    private static long toLong(Object v) {
        if (v == null) return 0L;
        if (v instanceof Number n) return n.longValue();
        try { return Long.parseLong(String.valueOf(v)); } catch (Exception e) { return 0L; }
    }

    @Transactional
    public Map<String, Object> ingestOrders(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        String dateWindow = firstNonBlank(text(body.get("date_window")), text(body.get("dateWindow")), "today");
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
            String replaceDay = firstNonBlank(text(body.get("replace_day")), text(body.get("replaceDay")));
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
            List<PddOrder> saved = new ArrayList<>();
            Object rawOrders = dayBody.get("orders");
            if (rawOrders instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map<?, ?> map) {
                        Map<String, Object> row = new LinkedHashMap<>();
                        for (Map.Entry<?, ?> e : map.entrySet()) {
                            row.put(String.valueOf(e.getKey()), e.getValue());
                        }
                        saved.add(mapOrder(tenantId, storeId, replaceDay, dateWindow, row, now));
                    }
                }
            }
            orderRepository.deleteByTenantIdAndStoreIdAndReportDay(tenantId, storeId, replaceDay);
            if (!saved.isEmpty()) {
                orderRepository.saveAll(saved);
            }
            ingested += saved.size();
            replacedDays.add(replaceDay);
        }

        updateJobCountOnIngest(body, tenantId, ingested, now, true, false);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", ingested);
        out.put("store_id", storeId);
        out.put("date_window", dateWindow);
        out.put("replace_days", replacedDays);
        return out;
    }

    // ---------------------------------------------------------------- products

    public Map<String, Object> listProducts(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        List<PddProduct> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = productRepository.findByTenantIdAndStoreIdOrderByUpdatedAtDesc(tenantId, storeId.trim());
        } else {
            rows = productRepository.findByTenantIdOrderByUpdatedAtDesc(tenantId);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", rows.stream().map(PddOpsService::toProductDto).toList());
        out.put("total", rows.size());
        return out;
    }

    public Map<String, Object> productAnalytics(String type, Long tenantId, String storeId) {
        String normalizedType = type == null || type.isBlank() ? "bestsellers" : type.trim();
        String store = storeId == null || storeId.isBlank() || "all".equals(storeId) ? "" : storeId.trim();
        StringBuilder sql = new StringBuilder(
                "SELECT product_id, product_name, price, stock, status, main_image, sales, updated_at "
                        + "FROM pdd_product WHERE tenant_id = ?"
        );
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        if (!store.isBlank()) {
            sql.append(" AND store_id = ?");
            args.add(store);
        }
        if ("recent_sales".equals(normalizedType)) {
            sql.append(" AND updated_at <> '' AND updated_at >= ?");
            args.add(LocalDateTime.now().minusDays(3).format(TS));
        }
        if ("today_bestsellers".equals(normalizedType)) {
            sql.append(" AND COALESCE(sales, 0) >= 10");
        }
        sql.append(" ORDER BY COALESCE(sales, 0) DESC, product_name");
        List<Map<String, Object>> rows = jdbc.queryForList(sql.toString(), args.toArray());
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            double salesQty = toDouble(row.get("sales"));
            double price = toDouble(row.get("price"));
            Map<String, Object> dto = new LinkedHashMap<>();
            dto.put("productId", row.get("product_id"));
            dto.put("productName", row.get("product_name"));
            dto.put("price", row.get("price"));
            dto.put("stock", row.get("stock"));
            dto.put("status", row.get("status"));
            dto.put("imageUrl", row.get("main_image"));
            dto.put("productUpdatedAt", row.get("updated_at"));
            dto.put("salesQty", salesQty);
            dto.put("salesAmount", salesQty * price);
            dto.put("orderCount", 0L);
            if ("bestsellers".equals(normalizedType)) {
                dto.put("tier", bestsellerTier(salesQty));
            }
            items.add(dto);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("total", items.size());
        out.put("type", normalizedType);
        return out;
    }

    public Map<String, Object> listPeerBestsellers(Long tenantId, String storeId, int page, int pageSize) {
        String store = storeId == null || storeId.isBlank() || "all".equals(storeId) ? "" : storeId.trim();
        int safePage = Math.max(1, page);
        int safeSize = Math.min(50, Math.max(1, pageSize));
        Integer total = jdbc.queryForObject(
                "SELECT COUNT(1) FROM pdd_peer_bestseller WHERE tenant_id = ? AND (? = '' OR store_id = ?)",
                Integer.class,
                tenantId,
                store,
                store
        );
        List<Map<String, Object>> rows = jdbc.queryForList(
                """
                SELECT store_id, product_id, shop_name, title, price, sales, sale_text,
                       offer_url, image_url, quality_score, suggestion, synced_at
                FROM pdd_peer_bestseller
                WHERE tenant_id = ? AND (? = '' OR store_id = ?)
                ORDER BY COALESCE(sales, 0) DESC, product_id
                LIMIT ? OFFSET ?
                """,
                tenantId,
                store,
                store,
                safeSize,
                (safePage - 1) * safeSize
        );
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> dto = new LinkedHashMap<>();
            dto.put("storeId", row.get("store_id"));
            dto.put("productId", row.get("product_id"));
            dto.put("shopName", row.get("shop_name"));
            dto.put("title", row.get("title"));
            dto.put("price", row.get("price"));
            dto.put("sales", row.get("sales"));
            dto.put("saleText", row.get("sale_text"));
            dto.put("offerUrl", row.get("offer_url"));
            dto.put("imageUrl", row.get("image_url"));
            dto.put("qualityScore", row.get("quality_score"));
            dto.put("suggestion", row.get("suggestion"));
            dto.put("syncedAt", row.get("synced_at"));
            items.add(dto);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("total", total == null ? 0 : total.intValue());
        out.put("page", safePage);
        out.put("pageSize", safeSize);
        return out;
    }

    @Transactional
    public Map<String, Object> ingestProducts(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }
        Object raw = body.get("products");
        List<Map<String, Object>> products = new ArrayList<>();
        if (raw instanceof List<?> list) {
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
        String now = now();
        int ingested = 0;
        if (!products.isEmpty()) {
            // 全量替换：先删除该店铺旧商品再写入，确保库中结果 = 平台当前全部商品（含下架）。
            // 空列表不删除，避免同步异常时误清空。
            productRepository.deleteByTenantIdAndStoreId(tenantId, storeId);
        }
        Set<String> seenKeys = new HashSet<>();
        for (Map<String, Object> src : products) {
            String productKey = firstNonBlank(text(src.get("product_key")), text(src.get("productKey")));
            if (productKey.isBlank()) {
                String pid = text(src.get("product_id"));
                productKey = storeId + ":" + pid;
            }
            if (!seenKeys.add(productKey)) {
                continue;
            }
            PddProduct p = new PddProduct();
            p.setId(UUID.randomUUID().toString());
            p.setTenantId(tenantId);
            p.setStoreId(storeId);
            p.setProductKey(productKey);
            p.setCreatedAt(now);
            mapProductFields(p, src, storeId, now);
            productRepository.save(p);
            ingested++;
        }
        updateJobCountOnIngest(body, tenantId, ingested, now, false, true);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", ingested);
        out.put("store_id", storeId);
        return out;
    }

    // ---------------------------------------------------------------- compass

    public Map<String, Object> getCompass(String storeId, Integer dateType) {
        Long tenantId = dataScopeService.requireTenantId();
        String window = compassWindow(dateType);
        Optional<PddCompassSnapshot> row;
        if (storeId != null && !storeId.isBlank()) {
            row = compassSnapshotRepository.findByTenantIdAndStoreIdAndDateWindow(tenantId, storeId.trim(), window);
        } else {
            // 无 storeId 时取最新一条
            List<PddCompassSnapshot> list = compassSnapshotRepository.findByTenantIdOrderByUpdatedAtDesc(tenantId);
            row = list.stream().filter(s -> window.equals(s.getDateWindow())).findFirst();
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("date_type", dateType == null ? 1 : dateType);
        out.put("date_window", window);
        out.put("payload", row.map(PddCompassSnapshot::getPayloadJson).orElse("{}"));
        out.put("synced_at", row.map(PddCompassSnapshot::getSyncedAt).orElse(""));
        return out;
    }

    public Map<String, Object> listCompass(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        List<PddCompassSnapshot> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = compassSnapshotRepository.findByTenantIdAndStoreIdOrderByUpdatedAtDesc(tenantId, storeId.trim());
        } else {
            rows = compassSnapshotRepository.findByTenantIdOrderByUpdatedAtDesc(tenantId);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", rows.stream().map(PddOpsService::toCompassDto).toList());
        out.put("total", rows.size());
        return out;
    }

    @Transactional
    public Map<String, Object> ingestCompass(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        String storeId = text(body.get("store_id"));
        Integer dateType = body.get("date_type") instanceof Number n ? n.intValue() : 1;
        String window = firstNonBlank(text(body.get("date_window")), compassWindow(dateType));
        Object payloadObj = body.getOrDefault("payload", body.get("payload_json"));
        String payloadJson;
        try {
            payloadJson = payloadObj == null
                    ? "{}"
                    : (payloadObj instanceof String s ? s : objectMapper.writeValueAsString(payloadObj));
        } catch (Exception ex) {
            payloadJson = "{}";
        }
        String rawJson = text(body.get("raw_json"));
        String now = now();
        Optional<PddCompassSnapshot> existing = compassSnapshotRepository
                .findByTenantIdAndStoreIdAndDateWindow(tenantId, storeId, window);
        PddCompassSnapshot snap = existing.orElseGet(PddCompassSnapshot::new);
        if (existing.isEmpty()) {
            snap.setId(UUID.randomUUID().toString());
            snap.setTenantId(tenantId);
            snap.setStoreId(storeId);
            snap.setDateWindow(window);
            snap.setCreatedAt(now);
        }
        snap.setDateType(dateType);
        snap.setPayloadJson(payloadJson);
        snap.setRawJson(rawJson);
        snap.setSyncedAt(now);
        snap.setUpdatedAt(now);
        compassSnapshotRepository.save(snap);
        updateJobCountOnIngest(body, tenantId, 1, now, false, false);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", 1);
        out.put("store_id", storeId);
        out.put("date_window", window);
        return out;
    }

    // ------------------------------------------------------------------- issues

    public Map<String, Object> listIssues(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        List<PddIssue> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = issueRepository.findByTenantIdAndStoreIdOrderByReportedAtDesc(tenantId, storeId.trim());
        } else {
            rows = issueRepository.findByTenantIdOrderByReportedAtDesc(tenantId);
        }
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        List<Map<String, Object>> items = new ArrayList<>();
        String syncedAt = "";
        for (PddIssue row : rows) {
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
            Optional<PddIssue> existing = issueRepository.findByTenantIdAndStoreIdAndExternalId(
                    tenantId, storeId, externalId
            );
            PddIssue row;
            boolean isNew;
            if (existing.isPresent()) {
                row = existing.get();
                isNew = false;
            } else {
                row = new PddIssue();
                row.setId(UUID.randomUUID().toString());
                row.setTenantId(tenantId);
                row.setStoreId(storeId);
                row.setExternalId(externalId);
                isNew = true;
            }
            PddIssueUpsert.applyIncoming(row, src, now, isNew);
            issueRepository.save(row);
            upserted++;
        }

        boolean partial = Boolean.TRUE.equals(body.get("partial"));
        String message = firstNonBlank(text(body.get("message")), text(body.get("partial_reason")));
        String jobId = text(body.get("job_id"));
        if (!jobId.isBlank()) {
            String finalStoreId = storeId;
            syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
                // PddSyncJob 暂无 issuesCount 字段，仅更新 store_id/message/updated_at。
                job.setStoreId(finalStoreId);
                if (!message.isBlank()) {
                    job.setMessage(message);
                }
                if (partial) {
                    String existingMsg = text(job.getMessage());
                    if (existingMsg.isBlank()) {
                        job.setMessage(firstNonBlank(message, AppErrorCode.PDD_ISSUES_SOURCE_UNCONFIGURED.getUserMessage()));
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
        PddIssue row = issueRepository.findByIdAndTenantId(id, tenantId)
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

    // ------------------------------------------------------- agent callbacks

    @Transactional
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null) {
            return;
        }
        if (!PddAgentTasks.SYNC.equals(task.getTaskType())
                && !PddAgentTasks.PRODUCTS_SYNC.equals(task.getTaskType())) {
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

    @Transactional
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !PddAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        Long tenantId = task.getTenantId();
        String taskStore = storeIdFromTask(task);
        Map<String, Object> payload = parseJson(task.getPayloadJson());
        if (PddAgentTasks.LOGIN_OPEN.equals(task.getTaskType())
                || PddAgentTasks.SESSION_PROBE.equals(task.getTaskType())) {
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
                snap.putIfAbsent("message", loggedIn ? "拼多多已登录" : "登录未完成，请重试打开登录");
            } else {
                snap.put("logged_in", false);
                snap.put("ready", false);
                snap.put("requires_auth", true);
                snap.put("profile_busy", false);
                snap.put("message", errorMessage == null || errorMessage.isBlank()
                        ? AppErrorCode.PDD_SYNC_FAILED.getUserMessage()
                        : errorMessage);
            }
            writeSessionSnapshot(tenantId, taskStore, snap);
            return;
        }

        if (!PddAgentTasks.SYNC.equals(task.getTaskType())
                && !PddAgentTasks.PRODUCTS_SYNC.equals(task.getTaskType())) {
            return;
        }
        String jobId = text(payload.get("job_id"));
        PddSyncJob job = jobId.isBlank()
                ? syncJobRepository.findFirstByTenantIdAndAgentTaskId(tenantId, task.getId()).orElse(null)
                : syncJobRepository.findByIdAndTenantId(jobId, tenantId).orElse(null);
        if (job == null) {
            return;
        }
        String now = now();
        Map<String, Object> snap = new LinkedHashMap<>(readSessionSnapshot(tenantId, taskStore));
        snap.put("tenant_id", tenantId);
        snap.put("profile_busy", false);
        if ("success".equalsIgnoreCase(status)) {
            Object msg = result == null ? null : result.get("message");
            if (msg != null && !String.valueOf(msg).isBlank()) {
                snap.put("message", String.valueOf(msg));
            }
            snap.remove("error_code");
        } else {
            snap.put("message", errorMessage == null || errorMessage.isBlank()
                    ? AppErrorCode.PDD_SYNC_FAILED.getUserMessage()
                    : errorMessage);
            if (errorCode != null && !errorCode.isBlank()) {
                snap.put("error_code", errorCode);
            }
            if (AppErrorCode.PDD_NOT_LOGGED_IN.getCode().equals(errorCode)
                    || (errorMessage != null && errorMessage.contains("未登录"))) {
                snap.put("logged_in", false);
                snap.put("ready", false);
                snap.put("requires_auth", true);
            }
        }
        writeSessionSnapshot(tenantId, taskStore, snap);
        job.setUpdatedAt(now);
        job.setFinishedAt(now);
        if ("success".equalsIgnoreCase(status)) {
            boolean partial = result != null && Boolean.TRUE.equals(result.get("partial"));
            job.setStatus(partial ? "partial" : "success");
            if (result != null) {
                if (result.get("orders_count") instanceof Number n) job.setOrdersCount(n.intValue());
                if (result.get("products_count") instanceof Number n) job.setProductsCount(n.intValue());
                if (result.get("compass_count") instanceof Number n) job.setCompassCount(n.intValue());
                job.setMessage(text(result.get("message")));
            }
            job.setErrorCode("");
            job.setErrorMessage("");
        } else {
            job.setStatus("failed");
            job.setErrorCode(errorCode == null || errorCode.isBlank()
                    ? AppErrorCode.PDD_SYNC_FAILED.getCode()
                    : errorCode);
            job.setErrorMessage(errorMessage == null ? "" : errorMessage);
        }
        syncJobRepository.save(job);
    }

    // ----------------------------------------------------------------- helpers

    private void updateJobCountOnIngest(Map<String, Object> body, Long tenantId, int ingested, String now,
                                        boolean isOrders, boolean isProducts) {
        String jobId = text(body.get("job_id"));
        if (jobId.isBlank()) {
            return;
        }
        syncJobRepository.findByIdAndTenantId(jobId, tenantId).ifPresent(job -> {
            if (isOrders) {
                job.setOrdersCount((job.getOrdersCount() == null ? 0 : job.getOrdersCount()) + ingested);
            }
            if (isProducts) {
                job.setProductsCount((job.getProductsCount() == null ? 0 : job.getProductsCount()) + ingested);
            }
            job.setUpdatedAt(now);
            syncJobRepository.save(job);
        });
    }

    private static PddOrder mapOrder(Long tenantId, String storeId, String reportDay,
                                     String dateWindow, Map<String, Object> src, String now) {
        String orderKey = firstNonBlank(text(src.get("order_key")), text(src.get("orderKey")));
        if (orderKey.isBlank()) {
            orderKey = storeId + ":" + text(src.get("order_no"));
        }
        String orderId = firstNonBlank(text(src.get("id")), orderKey);
        PddOrder o = new PddOrder();
        o.setId(orderId);
        o.setTenantId(tenantId);
        o.setStoreId(storeId);
        o.setExternalShopId(text(src.get("external_shop_id")));
        o.setReportDay(reportDay);
        o.setDateWindow(dateWindow);
        o.setOrderNo(text(src.get("order_no")));
        o.setProductName(text(src.get("product_name")));
        o.setChannel(text(src.get("channel")));
        o.setSku(text(src.get("sku")));
        o.setQuantity(number(src.get("quantity"), 1));
        o.setAmount(number(src.get("amount"), 0d));
        o.setCurrency(firstNonBlank(text(src.get("currency")), "CNY"));
        o.setStatus(text(src.get("status")));
        o.setShipDeadline(text(src.get("ship_deadline")));
        o.setOrderedAt(firstNonBlank(text(src.get("ordered_at")), now));
        o.setOrderKey(orderKey);
        o.setRawJson(text(src.get("raw_json")));
        o.setCreatedAt(now);
        o.setUpdatedAt(now);
        // 经营驾驶舱字段：agent 携带 cookie 抓取订单 XHR 后回写
        String paidAmount = firstNonBlank(text(src.get("paid_amount")), text(src.get("paidAmount")), "0");
        String paidAtText = firstNonBlank(text(src.get("paid_at")), text(src.get("paidAt")), "");
        o.setPaidAmount(paidAmount);
        o.setRefundedAmount(firstNonBlank(text(src.get("refunded_amount")), text(src.get("refundedAmount")), "0"));
        // 未支付订单（paid_amount=0）不应回退为下单时间。
        o.setPaidAt(
                paidAtText.isBlank() && !"0".equals(paidAmount) ? o.getOrderedAt() : paidAtText
        );
        o.setRefundedAt(text(src.get("refunded_at")));
        o.setBuyerMasked(text(src.get("buyer_masked")));
        o.setSyncedAt(now);
        o.setUnitPrice(firstNonBlank(text(src.get("unit_price")), text(src.get("unitPrice")), "0"));
        o.setItemAmount(firstNonBlank(text(src.get("item_amount")), text(src.get("itemAmount")), "0"));
        o.setImageUrl(text(src.get("image_url")));
        o.setSkuText(text(src.get("sku_text")));
        return o;
    }

    private static void mapProductFields(PddProduct p, Map<String, Object> src, String storeId, String now) {
        p.setExternalShopId(text(src.get("external_shop_id")));
        p.setProductId(text(src.get("product_id")));
        p.setProductName(text(src.get("product_name")));
        p.setStatus(text(src.get("status")));
        p.setStatusLabel(text(src.get("status_label")));
        p.setPrice(number(src.get("price"), null));
        p.setStock(number(src.get("stock"), null));
        p.setSales(number(src.get("sales"), null));
        p.setMainImage(text(src.get("main_image")));
        p.setCategory(text(src.get("category")));
        p.setArticleNo(text(src.get("article_no")));
        p.setSkuCount(number(src.get("sku_count"), 0));
        p.setSkusJson(text(src.get("skus_json")));
        p.setRawJson(text(src.get("raw_json")));
        p.setSyncedAt(now);
        p.setUpdatedAt(now);
    }

    private static String compassWindow(Integer dateType) {
        if (dateType == null) return "realtime";
        return switch (dateType) {
            case 1 -> "realtime";
            case 20 -> "d1";
            case 21 -> "d7";
            case 23 -> "d30";
            default -> "realtime";
        };
    }

    private static Map<String, Object> toOrderDto(PddOrder o) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", o.getId());
        m.put("store_id", o.getStoreId());
        m.put("report_day", o.getReportDay());
        m.put("date_window", o.getDateWindow());
        m.put("order_no", o.getOrderNo());
        m.put("product_name", o.getProductName());
        m.put("channel", o.getChannel());
        m.put("sku", o.getSku());
        m.put("sku_text", o.getSkuText());
        m.put("quantity", o.getQuantity());
        m.put("unit_price", o.getUnitPrice());
        m.put("item_amount", o.getItemAmount());
        m.put("amount", o.getAmount());
        m.put("paid_amount", o.getPaidAmount());
        m.put("refunded_amount", o.getRefundedAmount());
        m.put("currency", o.getCurrency());
        m.put("status", o.getStatus());
        m.put("ship_deadline", o.getShipDeadline());
        m.put("ordered_at", o.getOrderedAt());
        m.put("paid_at", o.getPaidAt());
        m.put("refunded_at", o.getRefundedAt());
        m.put("buyer_masked", o.getBuyerMasked());
        m.put("image_url", o.getImageUrl());
        m.put("synced_at", o.getSyncedAt());
        return m;
    }

    private static Map<String, Object> toProductDto(PddProduct p) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", p.getId());
        m.put("store_id", p.getStoreId());
        m.put("product_id", p.getProductId());
        m.put("product_name", p.getProductName());
        m.put("status", p.getStatus());
        m.put("status_label", p.getStatusLabel());
        m.put("price", p.getPrice());
        m.put("stock", p.getStock());
        m.put("sales", p.getSales());
        m.put("main_image", p.getMainImage());
        m.put("category", p.getCategory());
        m.put("article_no", p.getArticleNo());
        m.put("sku_count", p.getSkuCount());
        m.put("synced_at", p.getSyncedAt());
        return m;
    }

    private static Map<String, Object> toCompassDto(PddCompassSnapshot c) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", c.getId());
        m.put("store_id", c.getStoreId());
        m.put("date_type", c.getDateType());
        m.put("date_window", c.getDateWindow());
        m.put("payload", c.getPayloadJson());
        m.put("synced_at", c.getSyncedAt());
        return m;
    }

    private Map<String, Object> toJobDto(PddSyncJob job) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", job.getId());
        data.put("status", job.getStatus());
        data.put("scope", job.getScope());
        data.put("store_id", job.getStoreId());
        data.put("agent_task_id", job.getAgentTaskId());
        data.put("orders_count", job.getOrdersCount());
        data.put("products_count", job.getProductsCount());
        data.put("compass_count", job.getCompassCount());
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
                    AppErrorCode.PDD_AGENT_OFFLINE.getUserMessage()
            );
        }
        return agent;
    }

    /** 回收僵尸拼多多浏览器任务，避免死掉的 Helper 永久阻塞「打开登录」。 */
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
                    error_code = 'PDD_SYNC_FAILED',
                    error_message = '助手已重启，旧登录任务已取消，请重新打开登录',
                    finished_at = ?
                WHERE tenant_id = ?
                  AND status IN ('pending', 'running')
                  AND task_type IN (
                    'pdd_session_probe',
                    'pdd_login_open',
                    'pdd_sync',
                    'pdd_products_sync'
                  )
                  AND (agent_id IS NULL OR agent_id = '' OR agent_id <> ?)
                """,
                nowTs, tenantId, agentId
        );
        int stale = jdbc.update(
                """
                UPDATE agent_task
                SET status = 'failed',
                    error_code = 'PDD_SYNC_FAILED',
                    error_message = '登录任务已过期，请重新打开登录',
                    finished_at = ?
                WHERE tenant_id = ?
                  AND status IN ('pending', 'running')
                  AND task_type IN (
                    'pdd_session_probe',
                    'pdd_login_open',
                    'pdd_sync',
                    'pdd_products_sync'
                  )
                  AND (
                    (status = 'pending' AND created_at <> '' AND created_at < ?)
                    OR (
                      task_type = 'pdd_session_probe'
                      AND status = 'running'
                      AND CASE WHEN started_at IS NULL OR started_at = '' THEN created_at ELSE started_at END < ?
                    )
                    OR (
                      task_type IN ('pdd_login_open', 'pdd_sync', 'pdd_products_sync')
                      AND status = 'running'
                      AND CASE WHEN started_at IS NULL OR started_at = '' THEN created_at ELSE started_at END < ?
                    )
                  )
                """,
                nowTs, tenantId, pendingCutoff, probeCutoff, loginCutoff
        );
        if (orphaned + stale > 0) {
            Map<String, Object> snap = readSessionSnapshot(tenantId);
            snap.put("profile_busy", false);
            snap.put("ready", false);
            snap.putIfAbsent("logged_in", false);
            snap.put("requires_auth", true);
            snap.put("message", "请重新打开登录窗口完成拼多多商家后台登录");
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
                    'pdd_session_probe',
                    'pdd_login_open',
                    'pdd_sync',
                    'pdd_products_sync'
                  )
                """,
                Integer.class,
                tenantId
        );
        return count != null && count > 0;
    }

    private Map<String, Object> readSessionSnapshot(Long tenantId) {
        return readSessionSnapshot(tenantId, "");
    }

    private Map<String, Object> readSessionSnapshot(Long tenantId, String storeIdOrNull) {
        String storeKey = normalizeStoreKey(storeIdOrNull);
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT payload_json FROM pdd_session_snapshot WHERE tenant_id = ? AND store_id = ? LIMIT 1",
                tenantId, storeKey
        );
        if (rows.isEmpty() && !"default".equals(storeKey)) {
            // 指定店铺若为默认账号对应的店铺（最早绑定），回退到 default 快照，避免误报未登录
            String defaultAccount = "";
            try {
                List<String> ids = jdbc.queryForList(
                        "SELECT id FROM platform_account WHERE tenant_id = ? AND platform = 'pdd' "
                                + "ORDER BY bound_at ASC LIMIT 1",
                        String.class,
                        tenantId
                );
                if (!ids.isEmpty()) {
                    defaultAccount = ids.get(0);
                }
            } catch (Exception ignored) {
                // keep empty
            }
            if (storeKey.equals(defaultAccount)) {
                rows = jdbc.queryForList(
                        "SELECT payload_json FROM pdd_session_snapshot WHERE tenant_id = ? AND store_id = 'default' LIMIT 1",
                        tenantId
                );
            }
        }
        if (rows.isEmpty()) {
            Map<String, Object> defaults = new LinkedHashMap<>();
            defaults.put("tenant_id", tenantId);
            defaults.put("store_id", storeKey);
            defaults.put("ready", false);
            defaults.put("logged_in", false);
            defaults.put("requires_auth", true);
            defaults.put("profile_busy", false);
            defaults.put("message", "尚未登录拼多多商家后台");
            defaults.put("shop_count", 0);
            defaults.put("shops", List.of());
            return defaults;
        }
        return parseJson(String.valueOf(rows.get(0).get("payload_json")));
    }

    private void writeSessionSnapshot(Long tenantId, Map<String, Object> payload) {
        writeSessionSnapshot(tenantId, "", payload);
    }

    private void writeSessionSnapshot(Long tenantId, String storeIdOrNull, Map<String, Object> payload) {
        String storeKey = normalizeStoreKey(storeIdOrNull);
        String json;
        try {
            json = objectMapper.writeValueAsString(payload == null ? Map.of() : payload);
        } catch (Exception ex) {
            json = "{}";
        }
        jdbc.update(
                """
                INSERT INTO pdd_session_snapshot (tenant_id, store_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tenant_id, store_id) DO UPDATE
                  SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
                """,
                tenantId, storeKey, json, now()
        );
    }

    private String normalizeStoreKey(String storeIdOrNull) {
        String storeId = storeIdOrNull == null ? "" : storeIdOrNull.trim();
        return storeId.isBlank() || "all".equalsIgnoreCase(storeId) ? "default" : storeId;
    }

    private String storeIdFromTask(AgentTask task) {
        if (task == null) {
            return "default";
        }
        Map<String, Object> payload = parseJson(task.getPayloadJson());
        return normalizeStoreKey(text(payload.get("store_id")));
    }

    private void insertAgentTask(
            Long tenantId, String taskId, String taskType,
            Map<String, Object> payload, String agentId
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
                taskId, tenantId, agentId == null ? "" : agentId, taskType, "pending",
                payloadJson, "{}", "", "", now(), "", ""
        );
    }

    private void validateStoreMapping(Long tenantId, String storeId) {
        List<PlatformAccount> shops = platformAccountRepository.findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "pdd");
        if (shops.isEmpty()) {
            return;
        }
        if (storeId != null && !storeId.isBlank()) {
            shops.stream()
                    .filter(s -> storeId.trim().equals(s.getId()))
                    .findFirst()
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.ACCOUNT_NOT_FOUND.getUserMessage()));
            return;
        }
        // “全部店铺”同步以平台账号 id 为店铺 key，不依赖外部店铺 ID（external_shop_id 仅是可选的映射字段）。
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

    private Map<String, Object> toIssueDto(PddIssue row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("storeId", row.getStoreId());
        item.put("type", row.getType());
        item.put("typeLabel", firstNonBlank(row.getTypeLabel(), PddIssueUpsert.defaultLabel(row.getType())));
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
        if (values == null) return "";
        for (String v : values) {
            if (v != null && !v.isBlank()) return v.trim();
        }
        return "";
    }

    private static Double number(Object value, Double def) {
        if (value == null) return def;
        if (value instanceof Number n) return n.doubleValue();
        try {
            return Double.parseDouble(String.valueOf(value).trim());
        } catch (Exception ex) {
            return def;
        }
    }

    private static int number(Object value, int def) {
        if (value == null) return def;
        if (value instanceof Number n) return n.intValue();
        try {
            return Integer.parseInt(String.valueOf(value).trim());
        } catch (Exception ex) {
            return def;
        }
    }
}
