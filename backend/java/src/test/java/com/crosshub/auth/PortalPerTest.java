package com.crosshub.auth;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class PortalPerTest {

    @Test
    void fromRole_mapsAdminToBossPer0() {
        assertEquals(PortalPer.BOSS, PortalPer.fromRole("admin"));
        assertEquals(PortalPer.BOSS, PortalPer.fromRole("ADMIN"));
    }

    @Test
    void fromRole_mapsWarehouseToPer2() {
        assertEquals(PortalPer.WAREHOUSE, PortalPer.fromRole("warehouse"));
    }

    @Test
    void fromRole_mapsOtherToEmployeePer1() {
        assertEquals(PortalPer.EMPLOYEE, PortalPer.fromRole("user"));
        assertEquals(PortalPer.EMPLOYEE, PortalPer.fromRole(null));
        assertEquals(PortalPer.EMPLOYEE, PortalPer.fromRole(""));
    }

    @Test
    void portalFromPer_resolvesWorkbench() {
        assertEquals("boss", PortalPer.portalFromPer(PortalPer.BOSS));
        assertEquals("employee", PortalPer.portalFromPer(PortalPer.EMPLOYEE));
        assertEquals("warehouse", PortalPer.portalFromPer(PortalPer.WAREHOUSE));
        assertEquals("employee", PortalPer.portalFromPer("999"));
        assertEquals("employee", PortalPer.portalFromPer(null));
    }

    @Test
    void landingPathFromPer_matchesWorkbenchHome() {
        assertEquals("/boss/dashboard", PortalPer.landingPathFromPer(PortalPer.BOSS));
        assertEquals("/employee/dashboard", PortalPer.landingPathFromPer(PortalPer.EMPLOYEE));
        assertEquals("/warehouse/pending-review", PortalPer.landingPathFromPer(PortalPer.WAREHOUSE));
    }

    @Test
    void preferredPortalDoesNotOverrideAccountPer() {
        // 登录选项卡仅作提示：账号 per 决定实际入口
        assertEquals("employee", PortalPer.resolvePortal(PortalPer.EMPLOYEE, "boss"));
        assertEquals("boss", PortalPer.resolvePortal(PortalPer.BOSS, "employee"));
        assertEquals("warehouse", PortalPer.resolvePortal(PortalPer.WAREHOUSE, "boss"));
    }
}
