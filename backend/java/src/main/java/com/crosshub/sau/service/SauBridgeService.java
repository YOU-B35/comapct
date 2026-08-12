package com.crosshub.sau.service;

import com.crosshub.auth.entity.AppUser;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.security.AuthContext;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class SauBridgeService {
    private static final String MEDIA_OPS_ROLE = "自媒体运营";

    private final AuthContext authContext;
    private final AppUserRepository userRepository;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    private final String sauBaseUrl;
    private final String exchangeSecret;
    private final String linkUsername;

    public SauBridgeService(
            AuthContext authContext,
            AppUserRepository userRepository,
            ObjectMapper objectMapper,
            @Value("${crosshub.sau.base-url:https://automedia.yoto.work/api}") String sauBaseUrl,
            @Value("${crosshub.sau.exchange-secret:crosshub-sau-dev-secret}") String exchangeSecret,
            @Value("${crosshub.sau.link-username:admin}") String linkUsername
    ) {
        this.authContext = authContext;
        this.userRepository = userRepository;
        this.objectMapper = objectMapper;
        this.sauBaseUrl = sauBaseUrl.endsWith("/")
                ? sauBaseUrl.substring(0, sauBaseUrl.length() - 1)
                : sauBaseUrl;
        this.exchangeSecret = exchangeSecret;
        this.linkUsername = linkUsername == null ? "" : linkUsername.trim();
    }

    public Map<String, Object> issueTokenForCurrentEmployee() {
        String portal = String.valueOf(authContext.portalRole());
        boolean isEmployee = "employee".equalsIgnoreCase(portal);
        boolean isBoss = "boss".equalsIgnoreCase(portal);
        if (!isEmployee && !isBoss) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅员工端/Boss 端可获取自媒体会话");
        }
        Long tenantId = authContext.tenantId();
        Long userId = authContext.userId();
        if (tenantId == null || userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }

        AppUser user = userRepository.findByIdAndTenantId(userId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "用户不存在"));
        if (isEmployee) {
            String otherRole = user.getOtherRole() == null ? "" : user.getOtherRole().trim();
            if (!MEDIA_OPS_ROLE.equals(otherRole)) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "未开通自媒体运营权限");
            }
        }

        String externalKey = "ch:" + tenantId + ":" + userId;
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("external_key", externalKey);
        body.put("username", user.getUsername());
        // Local default: reuse SAU account that already holds media data (e.g. admin).
        // Leave empty in production for per-employee shadow isolation.
        if (!linkUsername.isBlank()) {
            body.put("link_username", linkUsername);
        }

        try {
            String json = objectMapper.writeValueAsString(body);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(sauBaseUrl + "/auth/crosshub-exchange"))
                    .timeout(Duration.ofSeconds(15))
                    .header("Content-Type", "application/json")
                    .header("X-SAU-Exchange-Secret", exchangeSecret)
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() >= 400) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY,
                        "自媒体服务兑票失败(" + response.statusCode() + ")"
                );
            }
            JsonNode root = objectMapper.readTree(response.body());
            if (root.path("code").asInt(-1) != 200) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY,
                        root.path("msg").asText("自媒体服务兑票失败")
                );
            }
            JsonNode data = root.path("data");
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("token", data.path("token").asText(null));
            out.put("sau_user_id", data.path("user").path("id").asLong());
            out.put("sau_username", data.path("user").path("username").asText(""));
            out.put("external_key", externalKey);
            if (out.get("token") == null || String.valueOf(out.get("token")).isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "自媒体服务未返回 token");
            }
            return out;
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY,
                    "无法连接自媒体服务，请确认 SAU 后端已启动(" + sauBaseUrl + ")"
            );
        }
    }
}
