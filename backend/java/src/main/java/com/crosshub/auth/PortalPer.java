package com.crosshub.auth;

/**
 * 端口权限码：与登录页选项卡、账号权限对齐。
 * <ul>
 *   <li>{@code 0} — 企业管理员（boss）</li>
 *   <li>{@code 1} — 员工端口（employee）</li>
 *   <li>{@code 2} — 仓库端口（warehouse）</li>
 * </ul>
 * 登录时以账号 {@code per} 为准自动进入对应工作台；选项卡仅作入口提示。
 */
public final class PortalPer {
    public static final String BOSS = "0";
    public static final String EMPLOYEE = "1";
    public static final String WAREHOUSE = "2";

    private PortalPer() {}

    public static String fromRole(String role) {
        if (role == null || role.isBlank()) {
            return EMPLOYEE;
        }
        String normalized = role.trim();
        if ("admin".equalsIgnoreCase(normalized)) {
            return BOSS;
        }
        if ("warehouse".equalsIgnoreCase(normalized)) {
            return WAREHOUSE;
        }
        return EMPLOYEE;
    }

    public static String portalFromPer(String per) {
        if (BOSS.equals(per)) {
            return "boss";
        }
        if (WAREHOUSE.equals(per)) {
            return "warehouse";
        }
        return "employee";
    }

    public static String landingPathFromPer(String per) {
        return switch (portalFromPer(per)) {
            case "boss" -> "/boss/dashboard";
            case "warehouse" -> "/warehouse/pending-review";
            default -> "/employee/dashboard";
        };
    }

    /**
     * 账号 per 决定实际入口；preferredPortal 仅兼容旧调用，不覆盖账号权限。
     */
    public static String resolvePortal(String accountPer, String preferredPortal) {
        return portalFromPer(accountPer);
    }
}
