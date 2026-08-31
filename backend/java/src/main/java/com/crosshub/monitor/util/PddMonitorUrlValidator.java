package com.crosshub.monitor.util;

import com.crosshub.common.AppErrorCode;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * 拼多多竞店 monitor URL 校验：接受店铺页 mall_id 或商品页 goods_id。
 */
public final class PddMonitorUrlValidator {
    private PddMonitorUrlValidator() {
    }

    public static boolean isValidPddMonitorUrl(String url) {
        return !canonicalize(url).isBlank();
    }

    public static void requireValidForCreate(String url) {
        if (!isValidPddMonitorUrl(url)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    AppErrorCode.MONITOR_TARGET_URL_INVALID.getUserMessage()
            );
        }
    }

    public static String canonicalize(String url) {
        if (url == null || url.isBlank()) {
            return "";
        }
        URI uri;
        try {
            uri = URI.create(url.trim());
        } catch (Exception ex) {
            return "";
        }
        String scheme = uri.getScheme();
        if (scheme == null) {
            return "";
        }
        String schemeLower = scheme.toLowerCase(Locale.ROOT);
        if (!schemeLower.equals("http") && !schemeLower.equals("https")) {
            return "";
        }
        String host = uri.getHost();
        if (host == null) {
            return "";
        }
        String hostLower = host.toLowerCase(Locale.ROOT);
        if (!(hostLower.equals("yangkeduo.com")
                || hostLower.endsWith(".yangkeduo.com")
                || hostLower.equals("pinduoduo.com")
                || hostLower.endsWith(".pinduoduo.com"))) {
            return "";
        }
        String path = uri.getPath() == null ? "" : uri.getPath().toLowerCase(Locale.ROOT);
        String mallId = queryParam(uri.getRawQuery(), "mall_id");
        if (path.endsWith("/mall_page.html") && mallId != null && !mallId.isBlank()) {
            return "https://mobile.yangkeduo.com/mall_page.html?mall_id=" + mallId;
        }
        String goodsId = queryParam(uri.getRawQuery(), "goods_id");
        if (path.endsWith("/goods.html") && goodsId != null && !goodsId.isBlank()) {
            String out = "https://mobile.yangkeduo.com/goods.html?goods_id=" + goodsId;
            return mallId == null || mallId.isBlank() ? out : out + "&mall_id=" + mallId;
        }
        return "";
    }

    private static String queryParam(String rawQuery, String key) {
        if (rawQuery == null || rawQuery.isBlank() || key == null || key.isBlank()) {
            return null;
        }
        for (String part : rawQuery.split("&")) {
            if (part == null || part.isBlank()) {
                continue;
            }
            int eq = part.indexOf('=');
            String name = eq >= 0 ? part.substring(0, eq) : part;
            String value = eq >= 0 ? part.substring(eq + 1) : "";
            try {
                name = URLDecoder.decode(name, StandardCharsets.UTF_8);
                value = URLDecoder.decode(value, StandardCharsets.UTF_8);
            } catch (Exception ignored) {
                // keep raw
            }
            if (key.equalsIgnoreCase(name)) {
                return value == null ? "" : value.trim();
            }
        }
        return null;
    }
}
