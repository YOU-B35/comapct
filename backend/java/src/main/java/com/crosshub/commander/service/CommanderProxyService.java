package com.crosshub.commander.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Service
public class CommanderProxyService {
    private static final Duration UPSTREAM_TIMEOUT = Duration.ofSeconds(300);
    private static final Set<String> HOP_BY_HOP = Set.of(
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "content-length",
            "authorization",
            "host",
            "cookie",
            "server",
            "date",
            // upstream CORS / openresty；本站已有 CORS，勿二次转发
            "access-control-allow-credentials",
            "access-control-allow-headers",
            "access-control-allow-methods",
            "access-control-allow-origin",
            "access-control-expose-headers",
            "vary"
    );

    private final CommanderSessionService sessionService;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    public CommanderProxyService(CommanderSessionService sessionService, ObjectMapper objectMapper) {
        this.sessionService = sessionService;
        this.objectMapper = objectMapper;
    }

    public ResponseEntity<byte[]> forward(
            String method,
            String commanderPathAndQuery,
            byte[] body,
            String contentType
    ) {
        return forwardInternal(method, commanderPathAndQuery, body, contentType, true);
    }

    private ResponseEntity<byte[]> forwardInternal(
            String method,
            String commanderPathAndQuery,
            byte[] body,
            String contentType,
            boolean retryOnAuthFailure
    ) {
        String token = sessionService.getToken();
        String target = sessionService.baseUrl() + commanderPathAndQuery;
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(target))
                    .timeout(UPSTREAM_TIMEOUT)
                    .header("Authorization", "Bearer " + token);
            if (contentType != null && !contentType.isBlank()) {
                builder.header("Content-Type", contentType);
            }
            String verb = method == null ? "GET" : method.toUpperCase(Locale.ROOT);
            byte[] payload = body == null ? new byte[0] : body;
            if ("GET".equals(verb) || "DELETE".equals(verb) || "HEAD".equals(verb)) {
                builder.method(verb, HttpRequest.BodyPublishers.noBody());
            } else {
                builder.method(verb, HttpRequest.BodyPublishers.ofByteArray(payload));
            }

            HttpResponse<byte[]> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofByteArray());
            sessionService.acceptTokenFromHeaders(response);

            if (retryOnAuthFailure && isAuthFailure(response)) {
                sessionService.forceRelogin();
                return forwardInternal(method, commanderPathAndQuery, body, contentType, false);
            }

            HttpHeaders headers = new HttpHeaders();
            response.headers().map().forEach((name, values) -> {
                if (name == null || values == null || values.isEmpty()) {
                    return;
                }
                // HttpClient 可能带上 HTTP/2 伪头（如 :status），转发给浏览器/Vite 会 502
                if (name.startsWith(":")) {
                    return;
                }
                String lower = name.toLowerCase(Locale.ROOT);
                if (HOP_BY_HOP.contains(lower) || "x-access-token".equals(lower)) {
                    return;
                }
                headers.put(name, List.copyOf(values));
            });
            return ResponseEntity.status(response.statusCode()).headers(headers).body(response.body());
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY,
                    "Commander 代理失败: " + ex.getMessage()
            );
        }
    }

    private boolean isAuthFailure(HttpResponse<byte[]> response) {
        if (response.statusCode() == 401) {
            return true;
        }
        byte[] body = response.body();
        if (body == null || body.length == 0) {
            return false;
        }
        String contentType = response.headers().firstValue("content-type").orElse("");
        if (!contentType.toLowerCase(Locale.ROOT).contains("json")) {
            // still try parse small bodies
            if (body.length > 4096) {
                return false;
            }
        }
        try {
            JsonNode root = objectMapper.readTree(body);
            int code = root.path("code").asInt(root.path("status").asInt(0));
            return code == 401;
        } catch (Exception ignored) {
            return false;
        }
    }

    /** Browser /api/commander/v1/... → upstream /api/v1/... */
    public static String toCommanderPath(String requestUri, String queryString) {
        if (requestUri == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少请求路径");
        }
        int idx = requestUri.indexOf("/api/commander");
        if (idx < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "非法 Commander 代理路径");
        }
        String suffix = requestUri.substring(idx + "/api/commander".length());
        if (!suffix.startsWith("/v1/") && !suffix.equals("/v1")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "仅允许代理 /api/commander/v1/**");
        }
        String path = "/api" + suffix;
        if (queryString != null && !queryString.isBlank()) {
            return path + "?" + queryString;
        }
        return path;
    }
}
