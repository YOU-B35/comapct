package com.crosshub.temu.service.impl;



import com.crosshub.common.AppErrorCode;

import com.crosshub.config.CrawlerProperties;

import com.crosshub.security.AuthContext;

import com.crosshub.temu.service.TemuAgentService;

import com.crosshub.temu.service.TemuSellerSessionService;

import com.crosshub.temu.service.TemuSessionService;

import com.crosshub.tenant.service.DataScopeService;

import com.fasterxml.jackson.databind.JsonNode;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.beans.factory.annotation.Qualifier;

import org.springframework.http.HttpStatus;

import org.springframework.stereotype.Service;

import org.springframework.web.server.ResponseStatusException;



import java.io.BufferedReader;

import java.io.InputStreamReader;

import java.nio.charset.StandardCharsets;

import java.nio.file.Files;

import java.nio.file.Path;

import java.util.ArrayList;

import java.util.LinkedHashMap;

import java.util.List;

import java.util.Map;

import java.util.concurrent.CompletableFuture;

import java.util.concurrent.Executor;

import java.util.concurrent.TimeUnit;

import java.util.concurrent.TimeoutException;



@Service

public class TemuSessionServiceImpl implements TemuSessionService {

    private final DataScopeService dataScopeService;

    private final CrawlerProperties crawlerProperties;

    private final ObjectMapper objectMapper;

    private final Executor crawlExecutor;

    private final TemuAgentService temuAgentService;

    private final TemuSellerSessionService sellerSessionService;

    private final AuthContext authContext;



    public TemuSessionServiceImpl(

            DataScopeService dataScopeService,

            CrawlerProperties crawlerProperties,

            ObjectMapper objectMapper,

            @Qualifier("crawlExecutor") Executor crawlExecutor,

            TemuAgentService temuAgentService,

            TemuSellerSessionService sellerSessionService,

            AuthContext authContext

    ) {

        this.dataScopeService = dataScopeService;

        this.crawlerProperties = crawlerProperties;

        this.objectMapper = objectMapper;

        this.crawlExecutor = crawlExecutor;

        this.temuAgentService = temuAgentService;

        this.sellerSessionService = sellerSessionService;

        this.authContext = authContext;

    }



    @Override

    public Map<String, Object> getSessionStatus() {

        Long tenantId = dataScopeService.requireTenantId();

        if (temuAgentService.useAgentMode()) {

            temuAgentService.maybeEnqueueSessionProbe(tenantId, authContext.userId());

            Map<String, Object> snapshot = temuAgentService.readSessionSnapshot(tenantId);

            Map<String, Object> integration = temuAgentService.integrationStatus(tenantId);

            Map<String, Object> out = new LinkedHashMap<>(snapshot);

            out.put("mode", "agent");

            out.put("agent_online", integration.get("agent_online"));

            out.put("seller_sessions", sellerSessionService.listSellerSessions(tenantId));

            enrichSessionSemantics(out);

            if (!Boolean.TRUE.equals(integration.get("agent_online"))) {

                out.put("ready", false);

                out.put("requires_agent", true);

                out.put("message", AppErrorCode.TEMU_AGENT_OFFLINE.getUserMessage());

                out.put("error_hint", "");

            }

            return out;

        }



        JsonNode json = runPythonJson(tenantId, "seller_session_status.py", buildSessionProbeArgs(tenantId));

        if (json == null || !json.isObject()) {

            return Map.of(

                    "ready", false,

                    "logged_in", false,

                    "profile_busy", false,

                    "mall_id", "",

                    "mall_count", 0,

                    "malls", List.of(),

                    "message", "未检测到会话",

                    "mode", "local"

            );

        }

        Map<String, Object> payload = objectMapper.convertValue(json, new com.fasterxml.jackson.core.type.TypeReference<>() {});

        payload.put("mode", "local");

        payload.put("seller_sessions", sellerSessionService.listSellerSessions(tenantId));

        enrichSessionSemantics(payload);

        return payload;

    }



    @Override

    public Map<String, Object> openLoginWindow(String platformAccountId) {

        Long tenantId = dataScopeService.requireTenantId();

        if (temuAgentService.useAgentMode()) {

            Long userId = authContext.userId();

            if (userId == null) {

                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, AppErrorCode.AUTH_MISSING_USER.getUserMessage());

            }

            return temuAgentService.enqueueLoginOpenForUser(tenantId, userId, platformAccountId);

        }



        List<String> args = new ArrayList<>();

        args.add("--open-only");

        String sessionKey = sellerSessionService.resolveSessionKey(tenantId, platformAccountId);

        if (!"default".equals(sessionKey)) {

            args.add("--session-key");

            args.add(sessionKey);

        }

        JsonNode json = runPythonJson(tenantId, "seller_login.py", args);

        if (json == null || !json.isObject()) {

            return Map.of("opened", true, "tenant_id", tenantId, "mode", "local");

        }

        Map<String, Object> payload = objectMapper.convertValue(json, new com.fasterxml.jackson.core.type.TypeReference<>() {});

        payload.put("mode", "local");

        return payload;

    }

    @Override
    public Map<String, Object> openFrontendLoginWindow(String url) {
        Long tenantId = dataScopeService.requireTenantId();
        if (temuAgentService.useAgentMode()) {
            Long userId = authContext.userId();
            if (userId == null) {
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, AppErrorCode.AUTH_MISSING_USER.getUserMessage());
            }
            return temuAgentService.enqueueFrontendLoginOpenForUser(tenantId, userId, url);
        }
        List<String> args = new ArrayList<>();
        args.add("--open-only");
        args.add("--mode");
        args.add("manual");
        if (url != null && !url.isBlank()) {
            args.add("--url");
            args.add(url.trim());
        }
        JsonNode json = runPythonJson(tenantId, "frontend_login.py", args);
        if (json == null || !json.isObject()) {
            return Map.of(
                    "opened", true,
                    "tenant_id", tenantId,
                    "mode", "local",
                    "engine", "manual_chrome"
            );
        }
        Map<String, Object> payload = objectMapper.convertValue(json, new com.fasterxml.jackson.core.type.TypeReference<>() {});
        payload.put("mode", "local");
        return payload;
    }



    private void enrichSessionSemantics(Map<String, Object> out) {
        if (out == null || Boolean.TRUE.equals(out.get("ready"))) {
            return;
        }
        boolean loggedIn = Boolean.TRUE.equals(out.get("logged_in"));
        boolean requiresAuth = Boolean.TRUE.equals(out.get("requires_auth"));
        boolean profileBusy = Boolean.TRUE.equals(out.get("profile_busy"));
        String mallId = stringValue(out.get("mall_id"));
        int mallCount = intValue(out.get("mall_count"));

        if (loggedIn && mallId.isBlank() && mallCount <= 0) {
            out.put("error_hint", AppErrorCode.CRAWL_MALL_NOT_SELECTED.getCode());
            out.put("message", AppErrorCode.CRAWL_MALL_NOT_SELECTED.getUserMessage());
            return;
        }
        // Login browser still open — keep agent-provided guidance, don't overwrite as plain「未登录」.
        if (profileBusy) {
            if (stringValue(out.get("message")).isBlank()) {
                out.put("message", "登录窗口已打开。请在本机浏览器完成登录并选择店铺，然后点击「我已完成登录」。");
            }
            if (stringValue(out.get("error_hint")).isBlank()) {
                out.put("error_hint", AppErrorCode.CRAWL_NOT_LOGGED_IN.getCode());
            }
            return;
        }
        if (requiresAuth || !loggedIn) {
            out.put("error_hint", AppErrorCode.CRAWL_NOT_LOGGED_IN.getCode());
            out.put("message", AppErrorCode.CRAWL_NOT_LOGGED_IN.getUserMessage());
        }
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private int intValue(Object value) {
        if (value == null) {
            return 0;
        }
        try {
            return Integer.parseInt(String.valueOf(value).split("\\.")[0]);
        } catch (Exception ex) {
            return 0;
        }
    }

    private List<String> buildSessionProbeArgs(Long tenantId) {
        List<String> args = new ArrayList<>();
        args.add("--cache-only");
        List<Map<String, Object>> sessions = sellerSessionService.listSellerSessions(tenantId);
        if (sessions.size() > 1 || !sessions.isEmpty() && !"default".equals(String.valueOf(sessions.get(0).get("session_key")))) {
            try {
                args.add("--seller-sessions-json");
                args.add(objectMapper.writeValueAsString(sessions));
            } catch (Exception ignored) {
                // fall back to single default probe
            }
        }
        return args;
    }

    private JsonNode runPythonJson(Long tenantId, String script, List<String> extraArgs) {

        Path scriptDir = Path.of(crawlerProperties.getScriptDir()).toAbsolutePath().normalize();

        if (!Files.isDirectory(scriptDir)) {

            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_SCRIPT_MISSING.getUserMessage());

        }

        List<String> command = new ArrayList<>();

        command.add(crawlerProperties.getPythonExecutable());

        command.add(script);

        command.add("--tenant-id");

        command.add(String.valueOf(tenantId));

        command.add("--json");

        if (extraArgs != null) {

            command.addAll(extraArgs);

        }



        ProcessBuilder builder = new ProcessBuilder(command);

        builder.directory(scriptDir.toFile());

        builder.environment().put("TENANT_ID", String.valueOf(tenantId));

        builder.redirectErrorStream(false);



        try {

            Process process = builder.start();

            CompletableFuture<String> stdoutFuture = CompletableFuture.supplyAsync(

                    () -> safeReadStream(process.getInputStream()),

                    crawlExecutor

            );

            CompletableFuture<String> stderrFuture = CompletableFuture.supplyAsync(

                    () -> safeReadStream(process.getErrorStream()),

                    crawlExecutor

            );



            boolean finished = process.waitFor(Math.max(30, crawlerProperties.getTimeoutSeconds()), TimeUnit.SECONDS);

            if (!finished) {

                process.destroyForcibly();

                stdoutFuture.cancel(true);

                stderrFuture.cancel(true);

                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_TIMEOUT.getUserMessage());

            }



            String stdout = "";

            String stderr = "";

            try { stdout = stdoutFuture.get(2, TimeUnit.SECONDS); } catch (TimeoutException ignored) { stdoutFuture.cancel(true); }

            try { stderr = stderrFuture.get(2, TimeUnit.SECONDS); } catch (TimeoutException ignored) { stderrFuture.cancel(true); }



            if (process.exitValue() != 0) {

                AppErrorCode code = AppErrorCode.classifyCrawlRaw(stderr + "\n" + stdout);

                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, code.getUserMessage());

            }



            for (String line : stdout.split("\\R")) {

                String trimmed = line.trim();

                if (!trimmed.startsWith("{")) continue;

                try {

                    return objectMapper.readTree(trimmed);

                } catch (Exception ignored) {

                    // try next line

                }

            }

            return null;

        } catch (ResponseStatusException ex) {

            throw ex;

        } catch (Exception ex) {

            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_PROCESS_FAILED.getUserMessage());

        }

    }



    private String safeReadStream(java.io.InputStream stream) {

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {

            StringBuilder sb = new StringBuilder();

            String line;

            while ((line = reader.readLine()) != null) {

                if (!sb.isEmpty()) sb.append(System.lineSeparator());

                sb.append(line);

            }

            return sb.toString();

        } catch (Exception ex) {

            return "";

        }

    }

}


