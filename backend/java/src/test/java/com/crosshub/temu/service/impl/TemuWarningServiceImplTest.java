package com.crosshub.temu.service.impl;

import com.crosshub.temu.entity.TemuSale;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TemuWarningServiceImplTest {
    private final TemuWarningServiceImpl warnings = new TemuWarningServiceImpl();

    @Test
    void isHotProduct_matchesFrontendSurgeRule() throws Exception {
        TemuSale hot = sale(15, 35);
        TemuSale cold = sale(2, 70);
        TemuSale newSales = sale(3, 0);
        TemuSale zero = sale(0, 0);

        assertTrue(warnings.isHotProduct(hot));
        assertFalse(warnings.isHotProduct(cold));
        assertTrue(warnings.isHotProduct(newSales));
        assertFalse(warnings.isHotProduct(zero));
    }

    @Test
    void overloadProducts_filtersByHotFormulaNotTopSevenDaySales() throws Exception {
        TemuSale highSevenNotHot = sale(1, 500);
        TemuSale hot = sale(20, 40);
        List<TemuSale> out = warnings.overloadProducts(List.of(highSevenNotHot, hot), 300);
        assertEquals(1, out.size());
        assertEquals(hot.getExtCode(), out.get(0).getExtCode());
    }

    private static TemuSale sale(int today, int seven) throws Exception {
        TemuSale s = new TemuSale();
        set(s, "extCode", "sku-" + today + "-" + seven);
        set(s, "sonTodaySales", today);
        set(s, "sonSalesSevenDays", seven);
        set(s, "sonSalesThirtyDays", Math.max(seven, today));
        set(s, "warehouseAvailableStock", 10);
        set(s, "status", "300");
        return s;
    }

    private static void set(Object target, String field, Object value) throws Exception {
        Field f = TemuSale.class.getDeclaredField(field);
        f.setAccessible(true);
        f.set(target, value);
    }
}
