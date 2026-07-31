package com.crosshub.common;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

public enum AppErrorCode {
    SERVER_ERROR("SERVER_ERROR", "服务器繁忙，请稍后重试"),
    BAD_REQUEST("BAD_REQUEST", "请求参数有误"),
    NOT_FOUND("NOT_FOUND", "资源不存在"),
    FORBIDDEN("FORBIDDEN", "无权执行此操作"),
    UNAUTHORIZED("UNAUTHORIZED", "请先登录"),
    UNKNOWN("UNKNOWN", "操作失败，请稍后重试"),

    CRAWL_IN_PROGRESS("CRAWL_IN_PROGRESS", "已有爬取任务进行中，请稍后再试"),
    CRAWL_NOT_LOGGED_IN("CRAWL_NOT_LOGGED_IN", "Temu 卖家后台未登录，请先在本机完成登录"),
    CRAWL_AE_NOT_LOGGED_IN("CRAWL_AE_NOT_LOGGED_IN", "AliExpress 卖家后台未登录，请先运行 login_aliexpress.py"),
    CRAWL_MALL_NOT_SELECTED("CRAWL_MALL_NOT_SELECTED", "Temu 卖家后台未选择店铺，请登录后选择店铺"),
    TEMU_PRODUCT_MAPPING_ERROR("TEMU_PRODUCT_MAPPING_ERROR", "Temu 货品映射异常：请在卖家后台「商品管理」补全 SKU 货号，并在「销售管理」页确认当前店铺后重试"),
    CRAWL_SCRIPT_MISSING("CRAWL_SCRIPT_MISSING", "爬虫环境未配置，请联系管理员"),
    CRAWL_TIMEOUT("CRAWL_TIMEOUT", "数据同步超时，请稍后重试"),
    CRAWL_PYTHON_ENV("CRAWL_PYTHON_ENV", "爬虫运行环境异常，请检查 Python 与依赖"),
    CRAWL_PROCESS_FAILED("CRAWL_PROCESS_FAILED", "数据同步失败，请稍后重试"),
    CRAWL_SEED_DISABLED("CRAWL_SEED_DISABLED", "当前环境不允许演示数据同步"),
    CRAWL_JOB_NOT_FOUND("CRAWL_JOB_NOT_FOUND", "同步任务不存在"),
    CRAWL_INTERRUPTED("CRAWL_INTERRUPTED", "同步任务已中断，请重新刷新"),
    CRAWL_COOLDOWN("CRAWL_COOLDOWN", "同步冷却中，请稍后再试或使用侧栏「重新同步」强制刷新"),
    CRAWL_DB_BUSY("CRAWL_DB_BUSY", "数据库繁忙，请稍后重试"),

    AUTH_MISSING_USER("AUTH_MISSING_USER", "登录状态无效，请重新登录"),
    AUTH_MISSING_TENANT("AUTH_MISSING_TENANT", "缺少企业上下文，请重新登录"),
    AUTH_NOT_LOGGED_IN("AUTH_NOT_LOGGED_IN", "未登录"),

    ACCOUNT_STORE_NAME_REQUIRED("ACCOUNT_STORE_NAME_REQUIRED", "店铺名称不能为空"),
    ACCOUNT_LOGIN_REQUIRED("ACCOUNT_LOGIN_REQUIRED", "登录账号不能为空"),
    ACCOUNT_PASSWORD_REQUIRED("ACCOUNT_PASSWORD_REQUIRED", "登录密码不能为空"),
    ACCOUNT_NOT_FOUND("ACCOUNT_NOT_FOUND", "店铺不存在"),
    ACCOUNT_PLATFORM_IMMUTABLE("ACCOUNT_PLATFORM_IMMUTABLE", "不允许修改店铺所属平台"),
    ACCOUNT_NAME_CONFLICT("ACCOUNT_NAME_CONFLICT", "该平台下已存在同名店铺"),
    ACCOUNT_BATCH_EMPTY("ACCOUNT_BATCH_EMPTY", "请至少提交一个店铺"),
    ACCOUNT_UNSUPPORTED_PLATFORM("ACCOUNT_UNSUPPORTED_PLATFORM", "不支持的平台"),

    TASK_NOT_FOUND("TASK_NOT_FOUND", "任务不存在"),
    TASK_FORBIDDEN("TASK_FORBIDDEN", "无权查看该任务"),
    TASK_BOSS_ONLY("TASK_BOSS_ONLY", "仅企业管理员可管理任务"),

    FEEDBACK_TASK_ID_REQUIRED("FEEDBACK_TASK_ID_REQUIRED", "缺少任务 ID"),

    HOT_BROADCAST_NOT_FOUND("HOT_BROADCAST_NOT_FOUND", "通报记录不存在"),

    RESTOCK_STATUS_NOT_FOUND("RESTOCK_STATUS_NOT_FOUND", "备货状态不存在"),

    WAREHOUSE_ORDER_NOT_FOUND("WAREHOUSE_ORDER_NOT_FOUND", "订单不存在"),
    WAREHOUSE_ORDER_ALREADY_PUSHED("WAREHOUSE_ORDER_ALREADY_PUSHED", "该订单已推送至仓库"),
    WAREHOUSE_ORDER_FORBIDDEN("WAREHOUSE_ORDER_FORBIDDEN", "无权查看该订单"),
    WAREHOUSE_SCOPE_FORBIDDEN("WAREHOUSE_SCOPE_FORBIDDEN", "未分配仓库管理权限"),
    WAREHOUSE_ORDER_SCOPE_FORBIDDEN("WAREHOUSE_ORDER_SCOPE_FORBIDDEN", "无权操作该仓库订单"),
    WAREHOUSE_CANCEL_FORBIDDEN("WAREHOUSE_CANCEL_FORBIDDEN", "仓库用户不可取消订单"),
    WAREHOUSE_CANCEL_SCOPE_FORBIDDEN("WAREHOUSE_CANCEL_SCOPE_FORBIDDEN", "无权取消该订单"),
    WAREHOUSE_OUTBOUND_FORBIDDEN("WAREHOUSE_OUTBOUND_FORBIDDEN", "无权创建出库单"),
    WAREHOUSE_FEATURE_FORBIDDEN("WAREHOUSE_FEATURE_FORBIDDEN", "未授权仓库下单功能"),
    WAREHOUSE_USER_ONLY("WAREHOUSE_USER_ONLY", "仅仓库用户可操作"),
    WAREHOUSE_BOSS_DELETE_ONLY("WAREHOUSE_BOSS_DELETE_ONLY", "仅企业管理员可删除订单"),
    WAREHOUSE_JSON_ERROR("WAREHOUSE_JSON_ERROR", "数据保存失败，请稍后重试"),

    MEMBER_PLATFORM_REQUIRED("MEMBER_PLATFORM_REQUIRED", "请至少选择一个负责平台"),
    MEMBER_INVALID_MENU("MEMBER_INVALID_MENU", "存在无效的菜单权限"),
    MEMBER_SHOP_PLATFORM_MISMATCH("MEMBER_SHOP_PLATFORM_MISMATCH", "所选店铺与平台不匹配"),
    MEMBER_SHOP_PLATFORM_UNKNOWN("MEMBER_SHOP_PLATFORM_UNKNOWN", "无法识别店铺所属平台"),

    AMAZON_AGENT_OFFLINE("AMAZON_AGENT_OFFLINE", "本机同步程序未运行，请联系运维启动 CrossHub-Sync-Helper.exe"),
    TEMU_AGENT_OFFLINE("TEMU_AGENT_OFFLINE", "本机同步程序未运行，请联系运维启动 CrossHub-Sync-Helper.exe"),
    AMAZON_ZINIAO_OFFLINE("AMAZON_ZINIAO_OFFLINE", "紫鸟 WebDriver 未就绪，请确认开发者模式已启动"),
    AMAZON_SYNC_IN_PROGRESS("AMAZON_SYNC_IN_PROGRESS", "已有 Amazon 同步任务进行中，请稍后再试"),
    AMAZON_SYNC_JOB_NOT_FOUND("AMAZON_SYNC_JOB_NOT_FOUND", "Amazon 同步任务不存在"),
    AMAZON_SYNC_FAILED("AMAZON_SYNC_FAILED", "Amazon 数据同步失败，请稍后重试"),
    AMAZON_LOGIN_REQUIRED("AMAZON_LOGIN_REQUIRED", "Amazon 卖家后台未登录，请在紫鸟浏览器中重新登录 Seller Central"),
    AMAZON_NO_PRODUCT_ROWS("AMAZON_NO_PRODUCT_ROWS", "同步完成，但未解析到带 ASIN 的产品行"),
    AMAZON_SYNC_PARTIAL("AMAZON_SYNC_PARTIAL", "产品数据已同步，但部分数据源（库存或广告报表）未采集完整"),
    AMAZON_WRITE_IN_PROGRESS("AMAZON_WRITE_IN_PROGRESS", "已有 Amazon 写操作任务进行中，请稍后再试"),
    AMAZON_WRITE_JOB_NOT_FOUND("AMAZON_WRITE_JOB_NOT_FOUND", "Amazon 写操作任务不存在"),
    AMAZON_WRITE_FAILED("AMAZON_WRITE_FAILED", "Amazon 写操作失败，请稍后重试"),
    ZINIAO_DISCOVER_FAILED("ZINIAO_DISCOVER_FAILED", "紫鸟店铺发现失败，请确认 Agent 与 WebDriver 已启动"),

    MONITOR_TARGET_NOT_FOUND("MONITOR_TARGET_NOT_FOUND", "竞店监控目标不存在"),
    MONITOR_TARGET_URL_INVALID(
            "MONITOR_TARGET_URL_INVALID",
            "请填写 Temu 店铺链接（含 mall_id），商品详情页无法作为竞店抓取"
    ),
    MONITOR_JOB_NOT_FOUND("MONITOR_JOB_NOT_FOUND", "竞店监控任务不存在"),
    MONITOR_JOB_IN_PROGRESS("MONITOR_JOB_IN_PROGRESS", "该竞店已有监控任务进行中"),

    COMPETITOR_LOGIN_REQUIRED(
            "COMPETITOR_LOGIN_REQUIRED",
            "Temu 前台需要登录或验证，已打开普通 Chrome 登录窗口，请完成后关闭窗口再重试发现"
    ),
    COMPETITOR_FRONTEND_LOGIN_REQUIRED(
            "COMPETITOR_FRONTEND_LOGIN_REQUIRED",
            "Temu 前台需要登录或验证，已打开普通 Chrome 登录窗口，请完成后关闭窗口再重试发现"
    ),
    COMPETITOR_STORE_UNAVAILABLE("COMPETITOR_STORE_UNAVAILABLE", "该竞店在当前地区或账号下不可访问"),
    COMPETITOR_NO_PRODUCTS("COMPETITOR_NO_PRODUCTS", "未识别到竞店商品"),
    COMPETITOR_DISCOVERY_NO_RESULTS("COMPETITOR_DISCOVERY_NO_RESULTS", "南非站未找到渔具候选"),
    COMPETITOR_CRAWL_TIMEOUT("COMPETITOR_CRAWL_TIMEOUT", "竞店爬取超时"),
    COMPETITOR_BROWSER_PROFILE_UNAVAILABLE("COMPETITOR_BROWSER_PROFILE_UNAVAILABLE", "Temu 前台浏览器配置无法打开"),
    COMPETITOR_CRAWL_FAILED("COMPETITOR_CRAWL_FAILED", "竞店爬取失败"),
    COMPETITOR_NAVIGATION_TIMEOUT("COMPETITOR_NAVIGATION_TIMEOUT", "打开 Temu 前台搜索页超时");

    private static final Map<String, AppErrorCode> BY_CODE = new HashMap<>();
    private static final Map<String, AppErrorCode> BY_REASON = new HashMap<>();

    private static final Pattern LOGIN_PATTERN = Pattern.compile(
            "未登录|登录已过期|/login|/auth/|seller\\.kuajingmaihuo|login\\.py",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE
    );
    private static final Pattern AE_LOGIN_PATTERN = Pattern.compile(
            "AliExpress.*未登录|无法获取\\s*AliExpress\\s*SCM\\s*token|login_aliexpress\\.py",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE
    );
    private static final Pattern MALL_PATTERN = Pattern.compile(
            "localStorage|mall-info|店铺\\s*ID|未读取到店铺|手动选择店铺|有 \\d+ 个店铺",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE
    );
    private static final Pattern PYTHON_ENV_PATTERN = Pattern.compile(
            "ModuleNotFoundError|No module named|playwright|python|pip install",
            Pattern.CASE_INSENSITIVE
    );

    static {
        for (AppErrorCode code : values()) {
            BY_CODE.put(code.code, code);
            BY_REASON.put(code.userMessage, code);
        }
        BY_REASON.put("缺少用户上下文", AUTH_MISSING_USER);
        BY_REASON.put("缺少租户上下文", AUTH_MISSING_TENANT);
        BY_REASON.put("任务不存在", TASK_NOT_FOUND);
        BY_REASON.put("同步任务不存在", CRAWL_JOB_NOT_FOUND);
        BY_REASON.put("当前环境不允许 seed 爬取", CRAWL_SEED_DISABLED);
        BY_REASON.put("服务重启中断", CRAWL_INTERRUPTED);
        BY_REASON.put("通报记录不存在", HOT_BROADCAST_NOT_FOUND);
        BY_REASON.put("备货状态不存在", RESTOCK_STATUS_NOT_FOUND);
        BY_REASON.put("订单不存在", WAREHOUSE_ORDER_NOT_FOUND);
        BY_REASON.put("店铺不存在", ACCOUNT_NOT_FOUND);
        BY_REASON.put("爬取进行中", CRAWL_IN_PROGRESS);
        BY_REASON.put("已有爬取任务进行中，请稍后再试", CRAWL_IN_PROGRESS);
        BY_REASON.put("无权查看该订单", WAREHOUSE_ORDER_FORBIDDEN);
        BY_REASON.put("未分配仓库管理权限", WAREHOUSE_SCOPE_FORBIDDEN);
        BY_REASON.put("无权操作该仓库订单", WAREHOUSE_ORDER_SCOPE_FORBIDDEN);
        BY_REASON.put("仓库用户不可取消订单", WAREHOUSE_CANCEL_FORBIDDEN);
        BY_REASON.put("无权取消该订单", WAREHOUSE_CANCEL_SCOPE_FORBIDDEN);
        BY_REASON.put("无权创建出库单", WAREHOUSE_OUTBOUND_FORBIDDEN);
        BY_REASON.put("未授权仓库下单功能", WAREHOUSE_FEATURE_FORBIDDEN);
        BY_REASON.put("仅仓库用户可操作", WAREHOUSE_USER_ONLY);
        BY_REASON.put("仅企业管理员可删除订单", WAREHOUSE_BOSS_DELETE_ONLY);
        BY_REASON.put("该订单已推送至仓库", WAREHOUSE_ORDER_ALREADY_PUSHED);
        BY_REASON.put("无权查看该任务", TASK_FORBIDDEN);
        BY_REASON.put("仅企业管理员可管理任务", TASK_BOSS_ONLY);
        BY_REASON.put("缺少任务 ID", FEEDBACK_TASK_ID_REQUIRED);
        BY_REASON.put("未登录", AUTH_NOT_LOGGED_IN);
    }

    private final String code;
    private final String userMessage;

    AppErrorCode(String code, String userMessage) {
        this.code = code;
        this.userMessage = userMessage;
    }

    public String getCode() {
        return code;
    }

    public String getUserMessage() {
        return userMessage;
    }

    public static AppErrorCode fromCode(String code) {
        if (code == null || code.isBlank()) {
            return UNKNOWN;
        }
        AppErrorCode resolved = BY_CODE.getOrDefault(code.trim(), UNKNOWN);
        if (resolved == COMPETITOR_FRONTEND_LOGIN_REQUIRED) {
            return COMPETITOR_LOGIN_REQUIRED;
        }
        return resolved;
    }

    public static AppErrorCode fromReason(String reason) {
        if (reason == null || reason.isBlank()) {
            return UNKNOWN;
        }
        String trimmed = reason.trim();
        AppErrorCode exact = BY_REASON.get(trimmed);
        if (exact != null) {
            return exact;
        }
        // Agent / Python often returns "ERROR_CODE: detail"
        int colon = trimmed.indexOf(':');
        if (colon > 0) {
            String codePrefix = trimmed.substring(0, colon).trim();
            AppErrorCode byPrefix = BY_CODE.get(codePrefix);
            if (byPrefix != null) {
                if (byPrefix == COMPETITOR_FRONTEND_LOGIN_REQUIRED) {
                    return COMPETITOR_LOGIN_REQUIRED;
                }
                return byPrefix;
            }
        }
        AppErrorCode byCode = BY_CODE.get(trimmed);
        if (byCode != null) {
            if (byCode == COMPETITOR_FRONTEND_LOGIN_REQUIRED) {
                return COMPETITOR_LOGIN_REQUIRED;
            }
            return byCode;
        }
        if (trimmed.contains("已存在名为") || trimmed.contains("已存在同名店铺")) {
            return ACCOUNT_NAME_CONFLICT;
        }
        if (trimmed.contains("不属于已选平台")) {
            return MEMBER_SHOP_PLATFORM_MISMATCH;
        }
        if (trimmed.startsWith("无效的菜单编码")) {
            return MEMBER_INVALID_MENU;
        }
        if (trimmed.startsWith("无法识别店铺所属平台")) {
            return MEMBER_SHOP_PLATFORM_UNKNOWN;
        }
        if (trimmed.startsWith("不支持的平台")) {
            return ACCOUNT_UNSUPPORTED_PLATFORM;
        }
        if (trimmed.length() <= 80 && !looksTechnical(trimmed)) {
            return UNKNOWN;
        }
        return UNKNOWN;
    }

    public static AppErrorCode classifyCrawlRaw(String raw) {
        if (raw == null || raw.isBlank()) {
            return CRAWL_PROCESS_FAILED;
        }
        String text = raw.trim();
        if (text.contains("Python 脚本目录不存在")) {
            return CRAWL_SCRIPT_MISSING;
        }
        if (text.contains("爬取超时")) {
            return CRAWL_TIMEOUT;
        }
        if (text.contains("服务重启中断")) {
            return CRAWL_INTERRUPTED;
        }
        if (text.contains("SQLITE_BUSY") || text.contains("database is locked")) {
            return CRAWL_DB_BUSY;
        }
        if (text.startsWith("COMPETITOR_") || text.contains("COMPETITOR_LOGIN_REQUIRED")
                || text.contains("COMPETITOR_FRONTEND_LOGIN_REQUIRED")) {
            AppErrorCode competitor = fromReason(text);
            if (competitor != UNKNOWN) {
                return competitor;
            }
        }
        if (AE_LOGIN_PATTERN.matcher(text).find()) {
            return CRAWL_AE_NOT_LOGGED_IN;
        }
        if (LOGIN_PATTERN.matcher(text).find()) {
            return CRAWL_NOT_LOGGED_IN;
        }
        if (text.contains("Target page, context or browser has been closed")
                || text.contains("browser has been closed")
                || text.contains("Browser closed")
                || text.contains("登录窗口仍在使用")) {
            return CRAWL_NOT_LOGGED_IN;
        }
        if (MALL_PATTERN.matcher(text).find()) {
            return CRAWL_MALL_NOT_SELECTED;
        }
        if (text.contains("映射关系") || text.contains("2000000") || text.contains("TEMU_PRODUCT_MAPPING")) {
            return TEMU_PRODUCT_MAPPING_ERROR;
        }
        if (PYTHON_ENV_PATTERN.matcher(text).find()) {
            return CRAWL_PYTHON_ENV;
        }
        if (text.toLowerCase(Locale.ROOT).contains("爬取失败")
                && text.toLowerCase(Locale.ROOT).contains("python")) {
            return CRAWL_PYTHON_ENV;
        }
        return CRAWL_PROCESS_FAILED;
    }

    private static boolean looksTechnical(String text) {
        return text.contains("Exception")
                || text.contains("Traceback")
                || text.contains("localStorage")
                || text.contains("agentseller")
                || text.length() > 120;
    }
}
