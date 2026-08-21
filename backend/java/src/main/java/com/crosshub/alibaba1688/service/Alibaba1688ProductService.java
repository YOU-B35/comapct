package com.crosshub.alibaba1688.service;

import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.alibaba1688.entity.Alibaba1688Product;
import com.crosshub.alibaba1688.entity.Alibaba1688ProductCategory;
import com.crosshub.alibaba1688.repository.Alibaba1688ProductCategoryRepository;
import com.crosshub.alibaba1688.repository.Alibaba1688ProductRepository;
import com.crosshub.common.AppErrorCode;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.HashSet;
import java.util.Optional;
import java.util.UUID;

@Service
public class Alibaba1688ProductService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final AgentPresenceService agentPresenceService;
    private final Alibaba1688SessionService sessionService;
    private final Alibaba1688ProductRepository productRepository;
    private final Alibaba1688ProductCategoryRepository categoryRepository;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;
    private final Alibaba1688StoreKeyResolver storeKeyResolver;

    public Alibaba1688ProductService(
            DataScopeService dataScopeService,
            AuthContext authContext,
            AgentPresenceService agentPresenceService,
            Alibaba1688SessionService sessionService,
            Alibaba1688ProductRepository productRepository,
            Alibaba1688ProductCategoryRepository categoryRepository,
            JdbcTemplate jdbc,
            ObjectMapper objectMapper,
            Alibaba1688StoreKeyResolver storeKeyResolver
    ) {
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.agentPresenceService = agentPresenceService;
        this.sessionService = sessionService;
        this.productRepository = productRepository;
        this.categoryRepository = categoryRepository;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
        this.storeKeyResolver = storeKeyResolver;
    }

    @Transactional
    public Map<String, Object> enqueueProductsSync() {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        sessionService.reclaimStaleBusyTasks(tenantId, agent.getId());
        if (hasRunningBusy(tenantId)) {
            return Map.of(
                    "already_open", true,
                    "queued", false,
                    "message", AppErrorCode.A1688_PROFILE_BUSY.getUserMessage()
            );
        }
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        payload.put("scope", "full");
        insertAgentTask(tenantId, taskId, Alibaba1688AgentTasks.PRODUCTS_SYNC, payload, agent.getId());
        sessionService.markProductsSyncQueued(tenantId);
        return Map.of(
                "queued", true,
                "task_id", taskId,
                "message", "已通知本机助手同步 1688 商品"
        );
    }

    @Transactional
    public Map<String, Object> ingestProducts(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        if (body == null) {
            body = Map.of();
        }
        String defaultStoreId = text(body.get("store_id"));
        if (defaultStoreId.isBlank() || "default".equalsIgnoreCase(defaultStoreId)) {
            String resolved = tenantId == null ? "" : storeKeyResolver.resolveDefaultAccountId(tenantId);
            defaultStoreId = resolved == null || resolved.isBlank() ? "default" : resolved;
        }
        boolean resetGrowth = truthy(body.get("reset_growth_fields"));
        if (resetGrowth) {
            // 全量同步前清掉成长标签/指数，避免上次误打标残留（如 index4 假 4.0）
            jdbc.update(
                    """
                    UPDATE alibaba1688_product
                    SET tag_potential = 0, tag_yanxuan = 0, tag_underperform = 0, index_score = ''
                    WHERE tenant_id = ? AND store_id = ?
                    """,
                    tenantId,
                    defaultStoreId
            );
        }
        List<Map<String, Object>> products = readMapList(body.get("products"));
        String now = now();
        int upserted = 0;
        for (Map<String, Object> src : products) {
            String offerId = text(src.get("offer_id"));
            if (offerId.isBlank()) {
                continue;
            }
            String storeId = text(src.get("store_id"));
            if (storeId.isBlank()) {
                storeId = defaultStoreId;
            }
            Optional<Alibaba1688Product> existingOpt =
                    productRepository.findByTenantIdAndStoreIdAndOfferId(tenantId, storeId, offerId);
            Alibaba1688Product row;
            if (existingOpt.isPresent()) {
                row = existingOpt.get();
            } else {
                row = new Alibaba1688Product();
                row.setId(UUID.randomUUID().toString());
                row.setTenantId(tenantId);
                row.setStoreId(storeId);
                row.setOfferId(offerId);
                row.setCreatedAt(now);
            }
            applyProductFields(row, src, now);
            productRepository.save(row);
            upserted++;
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ingested", upserted);
        out.put("store_id", defaultStoreId);
        String syncId = text(body.get("sync_id"));
        Map<String, Object> categoryResults = new LinkedHashMap<>();
        Object rawCategories = body.get("categories");
        if (rawCategories instanceof Map<?, ?> categories) {
            for (Map.Entry<?, ?> entry : categories.entrySet()) {
                String categoryCode = text(entry.getKey());
                if (!(entry.getValue() instanceof Map<?, ?> rawResult)) {
                    continue;
                }
                Map<String, Object> result = new LinkedHashMap<>();
                rawResult.forEach((key, value) -> result.put(String.valueOf(key), value));
                if ("success".equalsIgnoreCase(text(result.get("status")))) {
                    List<String> offerIds = readStringList(result.get("offer_ids"));
                    replaceCategory(tenantId, defaultStoreId, categoryCode, offerIds, syncId);
                    saveCategorySyncState(tenantId, defaultStoreId, categoryCode, "success", "", "", syncId);
                    categoryResults.put(categoryCode, Map.of("status", "success", "count", offerIds.size()));
                } else {
                    saveCategorySyncState(
                            tenantId,
                            defaultStoreId,
                            categoryCode,
                            "failed",
                            text(result.get("error_code")),
                            text(result.get("error_message")),
                            syncId
                    );
                    categoryResults.put(categoryCode, result);
                }
            }
        }
        out.put("categories", categoryResults);
        out.put("partial", truthy(body.get("partial")) || categoryResults.values().stream()
                .anyMatch(value -> value instanceof Map<?, ?> result
                        && !"success".equalsIgnoreCase(text(result.get("status")))));
        return out;
    }

    private void saveCategorySyncState(
            Long tenantId,
            String storeId,
            String categoryCode,
            String status,
            String errorCode,
            String errorMessage,
            String syncId
    ) {
        String now = now();
        jdbc.update(
                """
                INSERT INTO alibaba1688_product_category_sync (
                  tenant_id, store_id, category_code, status, error_code,
                  error_message, source_sync_id, synced_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, store_id, category_code) DO UPDATE SET
                  status = excluded.status,
                  error_code = excluded.error_code,
                  error_message = excluded.error_message,
                  source_sync_id = excluded.source_sync_id,
                  synced_at = excluded.synced_at,
                  updated_at = excluded.updated_at
                """,
                tenantId, storeId, categoryCode, status, errorCode, errorMessage, syncId, now, now
        );
    }

    @Transactional
    public void replaceCategory(
            Long tenantId,
            String storeId,
            String categoryCode,
            java.util.Collection<String> offerIds,
            String syncId
    ) {
        String normalizedCode = requireCategoryCode(categoryCode);
        String normalizedStoreId = text(storeId);
        if (normalizedStoreId.isBlank()) {
            normalizedStoreId = "default";
        }
        Set<String> incoming = new HashSet<>();
        if (offerIds != null) {
            for (String offerId : offerIds) {
                String normalizedOfferId = text(offerId);
                if (!normalizedOfferId.isBlank()) {
                    incoming.add(normalizedOfferId);
                }
            }
        }
        List<Alibaba1688ProductCategory> existing = categoryRepository
                .findByTenantIdAndStoreIdAndCategoryCode(tenantId, normalizedStoreId, normalizedCode);
        Map<String, Alibaba1688ProductCategory> existingByOffer = new LinkedHashMap<>();
        for (Alibaba1688ProductCategory row : existing) {
            existingByOffer.put(row.getOfferId(), row);
        }
        List<Alibaba1688ProductCategory> removed = existing.stream()
                .filter(row -> !incoming.contains(row.getOfferId()))
                .toList();
        if (!removed.isEmpty()) {
            categoryRepository.deleteAll(removed);
        }
        String now = now();
        List<Alibaba1688ProductCategory> replacements = new ArrayList<>();
        for (String offerId : incoming) {
            Alibaba1688ProductCategory row = existingByOffer.get(offerId);
            if (row == null) {
                row = new Alibaba1688ProductCategory();
                row.setId(UUID.randomUUID().toString());
                row.setTenantId(tenantId);
                row.setStoreId(normalizedStoreId);
                row.setOfferId(offerId);
                row.setCategoryCode(normalizedCode);
                row.setCreatedAt(now);
            }
            row.setSourceSyncId(syncId);
            row.setSyncedAt(now);
            row.setUpdatedAt(now);
            replacements.add(row);
        }
        categoryRepository.saveAll(replacements);
    }

    public Map<String, Object> listProducts(String tab, String status, String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        String normalizedTab = normalizeTab(tab);
        String normalizedStatus = normalizeStatus(status);
        List<Alibaba1688Product> rows;
        if (storeId != null && !storeId.isBlank()) {
            rows = productRepository.findByTenantIdAndStoreIdOrderBySyncedAtDesc(tenantId, storeId.trim());
        } else {
            rows = productRepository.findByTenantIdOrderBySyncedAtDesc(tenantId);
        }
        Set<String> categoryMembership = categoryMembership(tenantId, storeId, normalizedTab);
        List<Alibaba1688ProductCategory> allRelations = categoryRepository.findByTenantId(tenantId);
        if (allRelations == null) {
            allRelations = List.of();
        }
        List<String> scope = authContext.shopScope();
        boolean boss = authContext.isBossPortal() || authContext.isAdmin();
        List<Map<String, Object>> items = new ArrayList<>();
        Map<String, Integer> statusCounts = new LinkedHashMap<>();
        statusCounts.put("all", 0);
        statusCounts.put("on_sale", 0);
        statusCounts.put("sold_out", 0);
        statusCounts.put("pending_list", 0);
        statusCounts.put("reviewing", 0);
        statusCounts.put("violation_off", 0);
        statusCounts.put("draft", 0);
        for (Alibaba1688Product row : rows) {
            if (!boss && scope != null && !scope.isEmpty() && !scope.contains(row.getStoreId())) {
                continue;
            }
            if (!matchesTab(row, normalizedTab, categoryMembership)) {
                continue;
            }
            String st = blankToEmpty(row.getStatus());
            statusCounts.put("all", statusCounts.get("all") + 1);
            if ("sold_out".equals(st)) {
                statusCounts.put("sold_out", statusCounts.get("sold_out") + 1);
                // 1688：库存售罄计入销售中
                statusCounts.put("on_sale", statusCounts.get("on_sale") + 1);
            } else if (statusCounts.containsKey(st)) {
                statusCounts.put(st, statusCounts.get(st) + 1);
            }
            if ("all".equals(normalizedTab) && !"all".equals(normalizedStatus)) {
                if ("on_sale".equals(normalizedStatus)) {
                    if (!("on_sale".equals(st) || "sold_out".equals(st))) {
                        continue;
                    }
                } else if (!normalizedStatus.equals(st)) {
                    continue;
                }
            }
            items.add(toProductDto(row));
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("total", items.size());
        out.put("tab", normalizedTab);
        out.put("status", normalizedStatus);
        out.put("statusCounts", statusCounts);
        Map<String, Integer> categoryCounts = new LinkedHashMap<>();
        for (String code : validCategoryCodes()) {
            categoryCounts.put(code, 0);
        }
        for (Alibaba1688ProductCategory relation : allRelations) {
            if (storeId != null && !storeId.isBlank() && !storeId.trim().equals(relation.getStoreId())) {
                continue;
            }
            categoryCounts.computeIfPresent(relation.getCategoryCode(), (key, value) -> value + 1);
        }
        Map<String, Map<String, Object>> categorySync = new LinkedHashMap<>();
        List<Map<String, Object>> syncRows = jdbc.queryForList(
                """
                SELECT category_code, status, error_code, error_message, source_sync_id, synced_at
                FROM alibaba1688_product_category_sync
                WHERE tenant_id = ?
                  AND (? = '' OR store_id = ?)
                """,
                tenantId,
                storeId == null ? "" : storeId.trim(),
                storeId == null ? "" : storeId.trim()
        );
        if (syncRows != null) {
            for (Map<String, Object> row : syncRows) {
                Map<String, Object> sync = new LinkedHashMap<>();
                sync.put("status", text(row.get("status")));
                sync.put("errorCode", text(row.get("error_code")));
                sync.put("errorMessage", text(row.get("error_message")));
                sync.put("syncId", text(row.get("source_sync_id")));
                sync.put("syncedAt", text(row.get("synced_at")));
                categorySync.put(text(row.get("category_code")), sync);
            }
        }
        out.put("categoryCounts", categoryCounts);
        out.put("categorySync", categorySync);
        return out;
    }

    /** Tag OR-merge for 0/1 flags: max(existing, incoming). */
    static int orMergeTag(Integer existing, Integer incoming) {
        int left = existing == null ? 0 : (existing > 0 ? 1 : 0);
        int right = incoming == null ? 0 : (incoming > 0 ? 1 : 0);
        return Math.max(left, right);
    }

    /** Blank incoming score must not wipe a previously synced index. */
    static String mergeIndexScore(String existing, String incoming) {
        String next = incoming == null ? "" : incoming.trim();
        if (next.isEmpty()) {
            return existing;
        }
        return next;
    }

    /**
     * Full product sync sends the merged snapshot per offer; non-blank incoming wins
     * so a later sync can correct a previously wrong bucket. Blank/unknown does not wipe.
     */
    static String mergeProductStatus(String existing, String incoming) {
        String next = incoming == null ? "" : incoming.trim();
        String cur = existing == null ? "" : existing.trim();
        if (next.isEmpty() || "unknown".equals(next) || "all".equals(next)) {
            return cur;
        }
        return next;
    }

    private void applyProductFields(Alibaba1688Product row, Map<String, Object> src, String now) {
        setIfPresentText(row::setProductName, src, "product_name");
        setIfPresentText(row::setGoodsNo, src, "goods_no");
        if (src.containsKey("quality_score")) {
            row.setQualityScore(doubleVal(src.get("quality_score")));
        }
        if (src.containsKey("price")) {
            String nextPrice = text(src.get("price"));
            if (!nextPrice.isBlank() || row.getPrice() == null || row.getPrice().isBlank()) {
                row.setPrice(nextPrice);
            }
        }
        if (src.containsKey("stock")) {
            row.setStock(intObj(src.get("stock")));
        }
        if (src.containsKey("search_expose_7d")) {
            row.setSearchExpose7d(intObj(src.get("search_expose_7d")));
        }
        if (src.containsKey("visitor_30d")) {
            row.setVisitor30d(intObj(src.get("visitor_30d")));
        }
        setIfPresentText(row::setGmv30d, src, "gmv_30d");
        setIfPresentText(row::setGmv1d, src, "gmv_1d");
        setIfPresentText(row::setProductUpdatedAt, src, "product_updated_at");
        if (src.containsKey("status")) {
            row.setStatus(mergeProductStatus(row.getStatus(), text(src.get("status"))));
        }
        if (src.containsKey("tag_potential")) {
            row.setTagPotential(orMergeTag(row.getTagPotential(), intFlag(src.get("tag_potential"))));
        }
        if (src.containsKey("tag_yanxuan")) {
            row.setTagYanxuan(orMergeTag(row.getTagYanxuan(), intFlag(src.get("tag_yanxuan"))));
        }
        if (src.containsKey("tag_underperform")) {
            row.setTagUnderperform(orMergeTag(row.getTagUnderperform(), intFlag(src.get("tag_underperform"))));
        }
        if (src.containsKey("index_score")) {
            row.setIndexScore(mergeIndexScore(row.getIndexScore(), text(src.get("index_score"))));
        }
        if (src.containsKey("image_url")) {
            String next = text(src.get("image_url"));
            if (!next.isBlank() || row.getImageUrl() == null || row.getImageUrl().isBlank()) {
                row.setImageUrl(next);
            }
        }
        if (src.containsKey("raw_json")) {
            row.setRawJson(text(src.get("raw_json")));
        }
        row.setSyncedAt(now);
        row.setUpdatedAt(now);
        if (row.getCreatedAt() == null || row.getCreatedAt().isBlank()) {
            row.setCreatedAt(now);
        }
    }

    private static void setIfPresentText(
            java.util.function.Consumer<String> setter,
            Map<String, Object> src,
            String key
    ) {
        if (src.containsKey(key)) {
            setter.accept(text(src.get(key)));
        }
    }

    private Map<String, Object> toProductDto(Alibaba1688Product row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", row.getId());
        item.put("storeId", row.getStoreId());
        item.put("offerId", row.getOfferId());
        item.put("productName", row.getProductName());
        item.put("goodsNo", row.getGoodsNo());
        item.put("qualityScore", row.getQualityScore());
        item.put("price", row.getPrice());
        item.put("stock", row.getStock());
        item.put("searchExpose7d", row.getSearchExpose7d());
        item.put("visitor30d", row.getVisitor30d());
        item.put("gmv30d", row.getGmv30d());
        item.put("gmv1d", row.getGmv1d());
        item.put("productUpdatedAt", row.getProductUpdatedAt());
        item.put("status", row.getStatus());
        item.put("tagPotential", row.getTagPotential() != null && row.getTagPotential() > 0);
        item.put("tagYanxuan", row.getTagYanxuan() != null && row.getTagYanxuan() > 0);
        item.put("tagUnderperform", row.getTagUnderperform() != null && row.getTagUnderperform() > 0);
        item.put("indexScore", row.getIndexScore());
        item.put("imageUrl", row.getImageUrl() == null ? "" : row.getImageUrl());
        item.put("syncedAt", row.getSyncedAt());
        item.put("updatedAt", row.getUpdatedAt());
        return item;
    }

    private boolean matchesTab(Alibaba1688Product row, String tab, Set<String> categoryMembership) {
        return switch (tab) {
            case "potential", "yanxuan", "index", "on_sale", "pending_list", "sold_out", "reviewing", "violation_off", "draft" -> categoryMembership.contains(row.getStoreId() + "\u0000" + row.getOfferId());
            default -> true;
        };
    }

    private String normalizeTab(String tab) {
        if (tab == null || tab.isBlank() || "all".equalsIgnoreCase(tab.trim())) {
            return "all";
        }
        String t = tab.trim().toLowerCase();
        if (Set.of("potential", "index", "index4", "yanxuan", "on_sale", "pending_list", "sold_out", "reviewing", "violation_off", "draft").contains(t)) {
            if ("index4".equals(t)) {
                return "index";
            }
            return t;
        }
        return "all";
    }

    private Set<String> categoryMembership(Long tenantId, String storeId, String tab) {
        String categoryCode = switch (tab) {
            case "potential" -> "growth_potential";
            case "yanxuan" -> "growth_yanxuan";
            case "index" -> "growth_index";
            case "on_sale" -> "status_on_sale";
            case "pending_list" -> "status_pending_list";
            case "sold_out" -> "status_sold_out";
            case "reviewing" -> "status_reviewing";
            case "violation_off" -> "status_violation_off";
            case "draft" -> "status_draft";
            default -> "";
        };
        if (categoryCode.isBlank()) {
            return Set.of();
        }
        List<Alibaba1688ProductCategory> relations;
        if (storeId != null && !storeId.isBlank()) {
            relations = categoryRepository.findByTenantIdAndStoreIdAndCategoryCode(
                    tenantId,
                    storeId.trim(),
                    categoryCode
            );
        } else {
            relations = categoryRepository.findByTenantIdAndCategoryCode(tenantId, categoryCode);
        }
        Set<String> membership = new HashSet<>();
        for (Alibaba1688ProductCategory relation : relations) {
            membership.add(relation.getStoreId() + "\u0000" + relation.getOfferId());
        }
        return membership;
    }

    private Set<String> validCategoryCodes() {
        return Set.of(
                "status_on_sale",
                "status_pending_list",
                "status_sold_out",
                "status_reviewing",
                "status_violation_off",
                "status_draft",
                "growth_potential",
                "growth_yanxuan",
                "growth_index"
        );
    }

    private String requireCategoryCode(String categoryCode) {
        String normalized = text(categoryCode);
        Set<String> validCodes = Set.of(
                "status_on_sale",
                "status_pending_list",
                "status_sold_out",
                "status_reviewing",
                "status_violation_off",
                "status_draft",
                "growth_potential",
                "growth_yanxuan",
                "growth_index"
        );
        if (!validCodes.contains(normalized)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid 1688 product category: " + normalized);
        }
        return normalized;
    }

    private List<String> readStringList(Object raw) {
        List<String> values = new ArrayList<>();
        if (!(raw instanceof List<?> list)) {
            return values;
        }
        for (Object item : list) {
            String value = text(item);
            if (!value.isBlank()) {
                values.add(value);
            }
        }
        return values;
    }

    private String normalizeStatus(String status) {
        if (status == null || status.isBlank() || "all".equalsIgnoreCase(status.trim())) {
            return "all";
        }
        return status.trim();
    }

    private IntegrationAgent requireOnlineAgent(Long tenantId) {
        IntegrationAgent agent = agentPresenceService.findLatestOnlineAgentForTenant(tenantId);
        if (agent == null || agent.getId() == null || agent.getId().isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    AppErrorCode.A1688_AGENT_OFFLINE.getUserMessage()
            );
        }
        return agent;
    }

    private boolean hasRunningBusy(Long tenantId) {
        Integer count = jdbc.queryForObject(
                """
                SELECT COUNT(1) FROM agent_task
                WHERE tenant_id = ?
                  AND status IN ('pending', 'running')
                  AND task_type IN ('1688_session_probe', '1688_login_open', '1688_products_sync')
                """,
                Integer.class,
                tenantId
        );
        return count != null && count > 0;
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

    private List<Map<String, Object>> readMapList(Object raw) {
        List<Map<String, Object>> out = new ArrayList<>();
        if (!(raw instanceof List<?> list)) {
            return out;
        }
        for (Object item : list) {
            if (item instanceof Map<?, ?> map) {
                Map<String, Object> row = new LinkedHashMap<>();
                for (Map.Entry<?, ?> e : map.entrySet()) {
                    row.put(String.valueOf(e.getKey()), e.getValue());
                }
                out.add(row);
            }
        }
        return out;
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static boolean truthy(Object value) {
        if (value instanceof Boolean b) {
            return b;
        }
        if (value instanceof Number n) {
            return n.doubleValue() != 0d;
        }
        String s = text(value).toLowerCase();
        return "1".equals(s) || "true".equals(s) || "yes".equals(s);
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }

    private static Double doubleVal(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number n) {
            return n.doubleValue();
        }
        String s = String.valueOf(value).trim();
        if (s.isEmpty()) {
            return null;
        }
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static Integer intObj(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number n) {
            return n.intValue();
        }
        String s = String.valueOf(value).trim();
        if (s.isEmpty()) {
            return null;
        }
        try {
            return (int) Double.parseDouble(s);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static Integer intFlag(Object value) {
        if (value == null) {
            return 0;
        }
        if (value instanceof Boolean b) {
            return b ? 1 : 0;
        }
        Integer n = intObj(value);
        if (n == null) {
            String s = String.valueOf(value).trim().toLowerCase();
            if ("true".equals(s) || "yes".equals(s) || "y".equals(s)) {
                return 1;
            }
            return 0;
        }
        return n > 0 ? 1 : 0;
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
