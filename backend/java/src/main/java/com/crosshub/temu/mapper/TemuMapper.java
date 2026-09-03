package com.crosshub.temu.mapper;

import com.crosshub.common.AppErrorCode;
import com.crosshub.temu.dto.InventoryWarning;
import com.crosshub.temu.dto.LowSaleWarning;
import com.crosshub.temu.dto.ReplenishResult;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.entity.TemuSale;
import com.crosshub.temu.entity.TemuShop;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

@Component
public class TemuMapper {
    public Map<String, Object> toShopDto(TemuShop shop) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("shop_id", shop.getShopId());
        item.put("shop_name", shop.getShopName());
        item.put("is_upload", shop.isUpload());
        return item;
    }

    public Map<String, Object> toSaleDto(TemuSale sale) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", sale.getId());
        map.put("platform", sale.getPlatform());
        map.put("status", sale.getStatus());
        map.put("report_time", sale.getReportTime());
        map.put("shop_name", sale.getShopName());
        map.put("shop_id", sale.getShopId());
        map.put("tenant_id", sale.getTenantId());
        map.put("user_id", sale.getUserId());
        map.put("cost", sale.getCost());
        map.put("category_name", sale.getCategoryName());
        map.put("img_url", sale.getImgUrl());
        map.put("title", sale.getTitle());
        map.put("skc", sale.getSkc());
        map.put("spu", sale.getSpu());
        map.put("ext_code", sale.getExtCode());
        map.put("son_sku", sale.getSonSku());
        map.put("son_price", sale.getSonPrice());
        map.put("son_today_sales", sale.getSonTodaySales());
        map.put("son_sales_seven_days", sale.getSonSalesSevenDays());
        map.put("son_sales_thirty_days", sale.getSonSalesThirtyDays());
        map.put("join_site_time", sale.getJoinSiteTime());
        map.put("warehouse_available_stock", sale.getWarehouseAvailableStock());
        map.put("nickname", sale.getNickname());
        map.put("username", sale.getUsername());
        map.put("enterprise", sale.getEnterprise());
        return map;
    }

    public Map<String, Object> toLowSaleDto(LowSaleWarning warning) {
        Map<String, Object> map = toSaleDto(warning.sale());
        map.put("s10", warning.s10());
        map.put("s15", warning.s15());
        return map;
    }

    public Map<String, Object> toInventoryDto(InventoryWarning warning) {
        Map<String, Object> map = toSaleDto(warning.sale());
        ReplenishResult calc = warning.calc();
        map.put("s7", safeInt(warning.sale().getSonSalesSevenDays()));
        map.put("s30", safeInt(warning.sale().getSonSalesThirtyDays()));
        map.put("stock", safeInt(warning.sale().getWarehouseAvailableStock()));
        map.put("cover_days", round2(calc.coverDays()));
        map.put("warning_days", calc.warningDays());
        map.put("replenish_qty", calc.replenishQty());
        map.put("target_stock", round2(calc.targetStock()));
        map.put("daily_sales_adj", round2(calc.dailySalesAdjusted()));
        return map;
    }

    public Map<String, Object> toCrawlJobDto(TemuCrawlJob job) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("job_id", job.getId());
        data.put("triggered_by", job.getTriggeredBy());
        data.put("status", job.getStatus());
        data.put("mode", job.getMode());
        data.put("report_time", job.getReportTime());
        data.put("shops_count", job.getShopsCount());
        data.put("rows_count", job.getRowsCount());
        AppErrorCode errorCode = AppErrorCode.fromCode(job.getErrorCode());
        if ("failed".equals(job.getStatus()) && errorCode != AppErrorCode.UNKNOWN) {
            data.put("error_code", errorCode.getCode());
            data.put("error_message", errorCode.getUserMessage());
        } else {
            data.put("error_code", job.getErrorCode());
            data.put("error_message", job.getErrorMessage());
        }
        data.put("started_at", job.getStartedAt());
        data.put("finished_at", job.getFinishedAt());
        data.put("created_at", job.getCreatedAt());
        return data;
    }

    public Map<String, Object> toPlatformAccountDto(PlatformAccount row) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", row.getId());
        map.put("platform", row.getPlatform());
        map.put("storeName", row.getStoreName());
        map.put("account", row.getAccount());
        map.put("companyName", row.getCompanyName());
        map.put("boundAt", row.getBoundAt());
        map.put("externalShopId", row.getExternalShopId());
        map.put("external_shop_id", row.getExternalShopId());
        map.put("integrationMode", row.getIntegrationMode());
        map.put("integration_mode", row.getIntegrationMode());
        map.put("ziniaoStoreId", row.getZiniaoCliStoreId());
        map.put("ziniao_store_id", row.getZiniaoCliStoreId());
        return map;
    }

    private int safeInt(Integer value) {
        return value == null ? 0 : value;
    }

    private double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
