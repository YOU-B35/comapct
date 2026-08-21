package com.crosshub.monitor.util;

import com.crosshub.common.AppErrorCode;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class Alibaba1688MonitorUrlValidator {
    private static final Pattern SHOP_HOST = Pattern.compile("(?i)^shop[a-z0-9]+\\.1688\\.com$");
    private static final Pattern OFFER_PATH = Pattern.compile("(?i)/offer/(\\d+)\\.html");

    private Alibaba1688MonitorUrlValidator() {
    }

    public static void requireValidForCreate(String url, String crawlStrategy) {
        boolean strategyExpectsOffer = "1688_pinned_offers".equalsIgnoreCase(crawlStrategy);
        boolean isOffer = OFFER_PATH.matcher(pathOf(url)).find();
        if (strategyExpectsOffer != isOffer) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    AppErrorCode.MONITOR_TARGET_URL_INVALID.getUserMessage()
            );
        }
        if (canonicalize(url).isBlank()) {
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
        String host = uri.getHost();
        if (host == null) {
            return "";
        }
        String hostLower = host.toLowerCase(Locale.ROOT);
        if (SHOP_HOST.matcher(hostLower).matches()) {
            return "https://" + hostLower;
        }
        Matcher m = OFFER_PATH.matcher(pathOf(url));
        if (m.find()) {
            return "https://detail.1688.com/offer/" + m.group(1) + ".html";
        }
        return "";
    }

    private static String pathOf(String url) {
        try {
            URI uri = URI.create(url.trim());
            return uri.getPath() == null ? "" : uri.getPath();
        } catch (Exception ex) {
            return "";
        }
    }
}
