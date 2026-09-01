package com.crosshub.agent.service;

import com.crosshub.alibaba1688.service.Alibaba1688AgentTasks;
import com.crosshub.amazon.service.AmazonChatService;
import com.crosshub.amazon.service.AmazonWriteService;
import com.crosshub.douyin.service.DouyinAgentTasks;
import com.crosshub.temu.service.TemuAgentTasks;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Agent 浏览器任务并发：按 session_key / browser_id 互斥，并限制平台与全局槽位。
 * 默认（16GB）：Temu≤3、AliExpress≤2、Amazon≤1、全局≤5。
 */
public final class AgentTaskConcurrency {
    public static final int DEFAULT_MAX_TEMU = 3;
    public static final int DEFAULT_MAX_ALIEXPRESS = 2;
    public static final int DEFAULT_MAX_AMAZON = 1;
    public static final int DEFAULT_MAX_1688 = 1;
    public static final int DEFAULT_MAX_GLOBAL = 8;
    public static final int DEFAULT_MAX_CLAIM_BATCH = 5;
    public static final int DEFAULT_TEMU_PARALLEL_SESSIONS = 3;

    public enum Family {
        TEMU,
        ALIEXPRESS,
        AMAZON,
        DOUYIN,
        _1688,
        OTHER
    }

    public record Limits(
            int maxTemu,
            int maxAliExpress,
            int maxAmazon,
            int maxDouyin,
            int max1688,
            int maxGlobal,
            int maxClaimBatch,
            int temuParallelSessions
    ) {
        public static Limits defaults() {
            return new Limits(
                    DEFAULT_MAX_TEMU,
                    DEFAULT_MAX_ALIEXPRESS,
                    DEFAULT_MAX_AMAZON,
                    1,
                    DEFAULT_MAX_1688,
                    DEFAULT_MAX_GLOBAL,
                    DEFAULT_MAX_CLAIM_BATCH,
                    DEFAULT_TEMU_PARALLEL_SESSIONS
            );
        }
    }

    public record Requirement(
            Family family,
            Set<String> lockKeys,
            int browserSlots
    ) {
        public Requirement {
            lockKeys = lockKeys == null ? Set.of() : Set.copyOf(lockKeys);
            browserSlots = Math.max(0, browserSlots);
        }

        public boolean isBrowserTask() {
            return browserSlots > 0 && family != Family.OTHER;
        }
    }

    public static final class State {
        private final Limits limits;
        private final Set<String> busyLocks = new HashSet<>();
        private int temu;
        private int aliexpress;
        private int amazon;
        private int douyin;
        private int browser1688;
        private int global;

        public State(Limits limits) {
            this.limits = limits == null ? Limits.defaults() : limits;
        }

        public boolean canAdmit(Requirement req) {
            if (req == null || !req.isBrowserTask()) {
                return true;
            }
            for (String key : req.lockKeys()) {
                if (busyLocks.contains(key)) {
                    return false;
                }
            }
            if (global + req.browserSlots() > limits.maxGlobal()) {
                return false;
            }
            return switch (req.family()) {
                case TEMU -> temu + req.browserSlots() <= limits.maxTemu();
                case ALIEXPRESS -> aliexpress + req.browserSlots() <= limits.maxAliExpress();
                case AMAZON -> amazon + req.browserSlots() <= limits.maxAmazon();
                case DOUYIN -> douyin + req.browserSlots() <= limits.maxDouyin();
                case _1688 -> browser1688 + req.browserSlots() <= limits.max1688();
                case OTHER -> true;
            };
        }

        public void admit(Requirement req) {
            if (req == null || !req.isBrowserTask()) {
                return;
            }
            busyLocks.addAll(req.lockKeys());
            global += req.browserSlots();
            switch (req.family()) {
                case TEMU -> temu += req.browserSlots();
                case ALIEXPRESS -> aliexpress += req.browserSlots();
                case AMAZON -> amazon += req.browserSlots();
                case DOUYIN -> douyin += req.browserSlots();
                case _1688 -> browser1688 += req.browserSlots();
                case OTHER -> {
                }
            }
        }
    }

    private AgentTaskConcurrency() {
    }

    public static Requirement analyze(
            String taskType,
            Map<String, Object> payload,
            Long tenantId,
            Limits limits
    ) {
        Limits lim = limits == null ? Limits.defaults() : limits;
        String type = taskType == null ? "" : taskType.trim();
        Map<String, Object> body = payload == null ? Map.of() : payload;
        long tid = tenantId == null ? 0L : tenantId;

        if (TemuAgentTasks.BROWSER_BUSY_TYPES.contains(type)) {
            return temuRequirement(type, body, tid, lim);
        }
        if (DouyinAgentTasks.BROWSER_BUSY_TYPES.contains(type)) {
            return douyinRequirement(body, tid);
        }
        if (Alibaba1688AgentTasks.BROWSER_BUSY_TYPES.contains(type) || type.startsWith("1688_")) {
            return alibaba1688Requirement(body, tid);
        }
        if (AgentService.TASK_TYPE.equals(type)
                || AmazonWriteService.WRITE_TASK_TYPE.equals(type)
                || AmazonChatService.TASK_TYPE.equals(type)) {
            return amazonRequirement(body, tid);
        }
        if (type.startsWith("aliexpress_") || type.startsWith("ae_")) {
            return aliexpressRequirement(body, tid);
        }
        return new Requirement(Family.OTHER, Set.of(), 0);
    }

    public static Map<String, Object> parsePayload(ObjectMapper mapper, String payloadJson) {
        if (mapper == null || payloadJson == null || payloadJson.isBlank()) {
            return Map.of();
        }
        try {
            return mapper.readValue(payloadJson, new TypeReference<Map<String, Object>>() {});
        } catch (Exception ex) {
            return Map.of();
        }
    }

    private static Requirement temuRequirement(
            String type,
            Map<String, Object> body,
            long tenantId,
            Limits limits
    ) {
        if (TemuAgentTasks.FRONTEND_LOGIN_OPEN.equals(type)
                || TemuAgentTasks.COMPETITOR_DISCOVER.equals(type)) {
            String key = "temu:buyer:" + tenantId;
            return new Requirement(Family.TEMU, Set.of(key), 1);
        }

        Set<String> sessions = extractTemuSessionKeys(body);
        if (sessions.isEmpty()) {
            sessions = Set.of("default");
        }
        Set<String> locks = new LinkedHashSet<>();
        for (String session : sessions) {
            locks.add("temu:seller:" + tenantId + ":" + normalizeKey(session));
        }
        int slots = Math.min(sessions.size(), Math.max(1, limits.temuParallelSessions()));
        // 单会话任务（登录/探活/单店爬）占 1 槽；多会话聚合爬取按并行上限占槽
        if (!TemuAgentTasks.CRAWL.equals(type) || sessions.size() <= 1) {
            slots = 1;
        }
        return new Requirement(Family.TEMU, locks, slots);
    }

    private static Requirement amazonRequirement(Map<String, Object> body, long tenantId) {
        String browserId = firstNonBlank(
                stringValue(body.get("browser_id")),
                stringValue(body.get("external_shop_id")),
                stringValue(body.get("platform_account_id")),
                "default"
        );
        String key = "amazon:" + tenantId + ":" + normalizeKey(browserId);
        return new Requirement(Family.AMAZON, Set.of(key), 1);
    }

    private static Requirement aliexpressRequirement(Map<String, Object> body, long tenantId) {
        String session = firstNonBlank(
                stringValue(body.get("session_key")),
                stringValue(body.get("platform_account_id")),
                "default"
        );
        String key = "aliexpress:" + tenantId + ":" + normalizeKey(session);
        return new Requirement(Family.ALIEXPRESS, Set.of(key), 1);
    }

    private static Requirement douyinRequirement(Map<String, Object> body, long tenantId) {
        String session = firstNonBlank(
                stringValue(body.get("session_key")),
                stringValue(body.get("store_id")),
                stringValue(body.get("platform_account_id")),
                "default"
        );
        String key = "douyin:" + tenantId + ":" + normalizeKey(session);
        return new Requirement(Family.DOUYIN, Set.of(key), 1);
    }

    /** Share DOUYIN family slot (max 1) with a distinct lock key so 1688 ≠ 抖音 profile. */
    private static Requirement alibaba1688Requirement(Map<String, Object> body, long tenantId) {
        String session = firstNonBlank(
                stringValue(body.get("session_key")),
                stringValue(body.get("store_id")),
                stringValue(body.get("platform_account_id")),
                "default"
        );
        String key = "1688:" + tenantId + ":" + normalizeKey(session);
        return new Requirement(Family._1688, Set.of(key), 1);
    }

    @SuppressWarnings("unchecked")
    static Set<String> extractTemuSessionKeys(Map<String, Object> body) {
        Set<String> keys = new LinkedHashSet<>();
        String direct = stringValue(body.get("session_key"));
        if (!direct.isBlank()) {
            keys.add(normalizeKey(direct));
        }
        Object raw = body.get("seller_sessions");
        if (raw instanceof Collection<?> collection) {
            for (Object item : collection) {
                if (item instanceof Map<?, ?> map) {
                    Object sk = map.get("session_key");
                    if (sk != null && !String.valueOf(sk).isBlank()) {
                        keys.add(normalizeKey(String.valueOf(sk)));
                    }
                }
            }
        }
        return keys;
    }

    private static String normalizeKey(String raw) {
        String text = raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
        return text.isBlank() ? "default" : text;
    }

    private static String stringValue(Object value) {
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

    public static State seedFromRunning(
            List<?> runningTasks,
            ObjectMapper mapper,
            Limits limits,
            java.util.function.Function<Object, String> typeGetter,
            java.util.function.Function<Object, String> payloadGetter,
            java.util.function.Function<Object, Long> tenantGetter
    ) {
        State state = new State(limits);
        if (runningTasks == null) {
            return state;
        }
        for (Object task : runningTasks) {
            if (task == null) {
                continue;
            }
            Requirement req = analyze(
                    typeGetter.apply(task),
                    parsePayload(mapper, payloadGetter.apply(task)),
                    tenantGetter.apply(task),
                    limits
            );
            state.admit(req);
        }
        return state;
    }

    public static Set<String> lockKeysOf(Requirement req) {
        return req == null ? Collections.emptySet() : req.lockKeys();
    }

    public static boolean sameLocks(Requirement a, Requirement b) {
        return Objects.equals(lockKeysOf(a), lockKeysOf(b));
    }
}
