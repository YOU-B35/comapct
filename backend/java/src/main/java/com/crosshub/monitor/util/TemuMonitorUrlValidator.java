package com.crosshub.monitor.util;

import com.crosshub.common.AppErrorCode;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Temu 竞店 monitor URL 校验：仅接受含非空 mall_id 的店铺链接，拒绝商品详情页。
 */
public final class TemuMonitorUrlValidator {
    private static final Pattern PRODUCT_PATH = Pattern.compile("(?i)-g-\\d+\\.html");

    private TemuMonitorUrlValidator() {
    }

    public static boolean isValidTemuMallUrl(String url) {
        if (url == null || url.isBlank()) {
            return false;
        }
        URI uri;
        try {
            uri = URI.create(url.trim());
        } catch (Exception ex) {
            return false;
        }
        String scheme = uri.getScheme();
        if (scheme == null) {
            return false;
        }
        String schemeLower = scheme.toLowerCase(Locale.ROOT);
        if (!schemeLower.equals("http") && !schemeLower.equals("https")) {
            return false;
        }
        String host = uri.getHost();
        if (host == null) {
            return false;
        }
        String hostLower = host.toLowerCase(Locale.ROOT);
        if (!(hostLower.equals("temu.com") || hostLower.endsWith(".temu.com"))) {
            return false;
        }
        String path = uri.getPath() == null ? "" : uri.getPath();
        if (PRODUCT_PATH.matcher(path).find()) {
            return false;
        }
        String mallId = queryParam(uri.getRawQuery(), "mall_id");
        return mallId != null && !mallId.isBlank();
    }

    public static void requireValidForCreate(String url) {
        if (!isValidTemuMallUrl(url)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    AppErrorCode.MONITOR_TARGET_URL_INVALID.getUserMessage()
            );
        }
    }

    /** 可选规范化：统一为 www.temu.com/mall.html?mall_id={id}。非法 URL 原样返回。 */
    public static String canonicalize(String url) {
        if (!isValidTemuMallUrl(url)) {
            return url;
        }
        try {
            URI uri = URI.create(url.trim());
            String mallId = queryParam(uri.getRawQuery(), "mall_id");
            if (mallId == null || mallId.isBlank()) {
                return url;
            }
            return "https://www.temu.com/mall.html?mall_id=" + mallId;
        } catch (Exception ex) {
            return url;
        }
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
