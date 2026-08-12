package com.crosshub.commander.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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

/**
 * 服务端缓存共用 Commander 运维账号的 token；不对浏览器暴露。
 */
@Service
public class CommanderSessionService {
    private static final Logger log = LoggerFactory.getLogger(CommanderSessionService.class);
    private static final String ACCESS_TOKEN_HEADER = "x-access-token";

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    private final String baseUrl;
    private final String username;
    private final String password;

    private final Object lock = new Object();
    private volatile String cachedToken = "";

    public CommanderSessionService(
            ObjectMapper objectMapper,
            @Value("${crosshub.commander.base-url:https://www.yoto.work}") String baseUrl,
            @Value("${crosshub.commander.username:}") String username,
            @Value("${crosshub.commander.password:}") String password
    ) {
        this.objectMapper = objectMapper;
        // Windows CRLF .env → Docker 注入时常带尾部 \\r；用户名已 trim，密码也必须清洗
        this.baseUrl = normalizeBaseUrl(baseUrl);
        this.username = sanitizeSecret(username);
        this.password = sanitizeSecret(password);
    }

    static String sanitizeSecret(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("\r", "").trim();
    }

    static String normalizeBaseUrl(String baseUrl) {
        String trimmed = sanitizeSecret(baseUrl);
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }

    @PostConstruct
    void logConfig() {
        if (baseUrl.isBlank() || username.isBlank() || password.isBlank()) {
            log.warn(
                    "Commander BFF 未配置运维账号：所有 CrossHub 账号（含新注册）的自动上货代登不可用。"
                            + "请设置 CROSSHUB_COMMANDER_USERNAME / CROSSHUB_COMMANDER_PASSWORD"
            );
        } else {
            log.info("Commander BFF 已配置：baseUrl={} username={}（全站共用，含新注册账号）", baseUrl, username);
        }
    }

    public String baseUrl() {
        return baseUrl;
    }

    public void ensureConfigured() {
        if (baseUrl.isBlank() || username.isBlank() || password.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "未配置 Commander 运维账号（CROSSHUB_COMMANDER_USERNAME / CROSSHUB_COMMANDER_PASSWORD）"
            );
        }
    }

    public String getToken() {
        ensureConfigured();
        String token = cachedToken;
        if (token != null && !token.isBlank()) {
            return token;
        }
        synchronized (lock) {
            if (cachedToken != null && !cachedToken.isBlank()) {
                return cachedToken;
            }
            loginLocked();
            return cachedToken;
        }
    }

    public void invalidate() {
        synchronized (lock) {
            cachedToken = "";
        }
    }

    /** 强制重新登录；返回新 token。 */
    public String forceRelogin() {
        ensureConfigured();
        synchronized (lock) {
            cachedToken = "";
            loginLocked();
            return cachedToken;
        }
    }

    public void acceptTokenFromUpstream(String token) {
        if (token == null || token.isBlank()) {
            return;
        }
        synchronized (lock) {
            cachedToken = token.trim();
        }
    }

    public void acceptTokenFromHeaders(HttpResponse<?> response) {
        if (response == null) {
            return;
        }
        response.headers().firstValue(ACCESS_TOKEN_HEADER)
                .or(() -> response.headers().firstValue("X-Access-Token"))
                .ifPresent(this::acceptTokenFromUpstream);
    }

    private void loginLocked() {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("username", username);
            body.put("password", password);
            String json = objectMapper.writeValueAsString(body);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/api/v1/user/login"))
                    .timeout(Duration.ofSeconds(30))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            acceptTokenFromHeaders(response);
            if (response.statusCode() >= 400) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY,
                        "Commander 运维账号登录失败(" + response.statusCode() + ")"
                );
            }
            String token = extractToken(response.body());
            if (token == null || token.isBlank()) {
                token = cachedToken;
            }
            if (token == null || token.isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Commander 登录成功但未返回 token");
            }
            cachedToken = token.trim();
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY,
                    "无法连接 Commander（" + baseUrl + "）: " + ex.getMessage()
            );
        }
    }

    static String extractToken(String responseBody) {
        if (responseBody == null || responseBody.isBlank()) {
            return null;
        }
        try {
            ObjectMapper mapper = new ObjectMapper();
            JsonNode root = mapper.readTree(responseBody);
            if (root == null || root.isNull()) {
                return null;
            }
            if (root.isTextual()) {
                return root.asText();
            }
            JsonNode data = root.get("data");
            if (data != null && data.isTextual()) {
                return data.asText();
            }
            if (data != null && data.isObject()) {
                JsonNode nested = data.get("token");
                if (nested != null && nested.isTextual()) {
                    return nested.asText();
                }
            }
            JsonNode token = root.get("token");
            if (token != null && token.isTextual()) {
                return token.asText();
            }
        } catch (Exception ignored) {
            // fall through
        }
        return null;
    }
}
