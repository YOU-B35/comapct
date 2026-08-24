package com.crosshub.config;

import com.crosshub.common.ApiResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 本机 Sync Helper 发布信息：用于前端提示/强制更新旧版本助手。 */
@RestController
@RequestMapping("/api/helper")
public class HelperUpdateController {
    public static final String HELPER_VERSION = "2026.08.24.1";
    public static final String HELPER_DOWNLOAD_URL =
            "https://www.yoto.work/crosshub/downloads/CrossHub-Sync-Helper.zip";

    @GetMapping("/update-info")
    public Map<String, Object> updateInfo() {
        return ApiResult.ok(Map.of(
                "version", HELPER_VERSION,
                "download_url", HELPER_DOWNLOAD_URL
        ));
    }
}
