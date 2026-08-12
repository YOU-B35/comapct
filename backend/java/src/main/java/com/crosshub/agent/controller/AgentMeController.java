package com.crosshub.agent.controller;

import com.crosshub.agent.service.AgentBindCodeService;
import com.crosshub.security.AuthContext;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/agent")
public class AgentMeController {
    private static final DateTimeFormatter EXPIRES_AT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneOffset.UTC);

    private final AgentBindCodeService bindCodeService;
    private final AuthContext authContext;
    private final String javaApiUrl;

    public AgentMeController(
            AgentBindCodeService bindCodeService,
            AuthContext authContext,
            @Value("${crosshub.java-api-url:https://www.yoto.work}") String javaApiUrl
    ) {
        this.bindCodeService = bindCodeService;
        this.authContext = authContext;
        this.javaApiUrl = javaApiUrl;
    }

    @GetMapping("/me/status")
    public Map<String, Object> meStatus() {
        Long tenantId = requireTenantId();
        return Map.of("success", true, "data", bindCodeService.statusForTenant(tenantId));
    }

    @PostMapping("/me/bind-code")
    public Map<String, Object> createBindCode() {
        Long userId = requireUserId();
        Long tenantId = requireTenantId();
        AgentBindCodeService.CreateCodeResult created = bindCodeService.createCode(userId, tenantId);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("code", created.code());
        data.put("expires_at", EXPIRES_AT.format(created.expiresAt()));
        data.put("expires_in_seconds", AgentBindCodeService.EXPIRES_IN_SECONDS);
        return Map.of("success", true, "data", data);
    }

    /** Public: Helper enrolls with a short-lived website bind code (no JWT / agent token). */
    @PostMapping("/bind")
    public Map<String, Object> bind(@RequestBody Map<String, Object> body) {
        String code = asString(body, "code");
        String fingerprint = asString(body, "machine_fingerprint");
        String displayName = asString(body, "display_name");
        AgentBindCodeService.ConsumeResult result = bindCodeService.consume(code, fingerprint, displayName);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("agent_token", result.agentToken());
        data.put("tenant_id", result.tenantId());
        data.put("user_id", result.userId());
        data.put("java_api_url", javaApiUrl);
        return Map.of("success", true, "data", data);
    }

    private Long requireUserId() {
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        return userId;
    }

    private Long requireTenantId() {
        Long tenantId = authContext.tenantId();
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        return tenantId;
    }

    private static String asString(Map<String, Object> body, String key) {
        if (body == null) {
            return null;
        }
        Object value = body.get(key);
        return value == null ? null : String.valueOf(value);
    }
}
