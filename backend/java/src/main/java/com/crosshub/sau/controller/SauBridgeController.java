package com.crosshub.sau.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.sau.service.SauBridgeService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/sau")
public class SauBridgeController {
    private final SauBridgeService sauBridgeService;

    public SauBridgeController(SauBridgeService sauBridgeService) {
        this.sauBridgeService = sauBridgeService;
    }

    /** Employee / Boss portal: silently exchange CrossHub session for a SAU API token. */
    @PostMapping("/token")
    public Map<String, Object> token() {
        return ApiResult.ok(sauBridgeService.issueTokenForCurrentEmployee());
    }
}
