package com.crosshub.temu.service.impl;

import com.crosshub.common.AppErrorCode;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.temu.dto.TemuCompetitorDiscoverRequest;
import com.crosshub.temu.service.TemuAgentService;
import com.crosshub.temu.service.TemuAgentTasks;
import com.crosshub.temu.service.TemuCompetitorService;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

@Service
public class TemuCompetitorServiceImpl implements TemuCompetitorService {
    private static final int DISCOVER_TIMEOUT_SECONDS = 90;
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final DataScopeService dataScopeService;
    private final CrawlerProperties crawlerProperties;
    private final ObjectMapper objectMapper;
    private final Executor crawlExecutor;
    private final TenantCrawlCooldownService crawlCooldownService;
    private final TemuAgentService temuAgentService;
    private final JdbcTemplate jdbc;

    public TemuCompetitorServiceImpl(
            DataScopeService dataScopeService,
            CrawlerProperties crawlerProperties,
            ObjectMapper objectMapper,
            @Qualifier("crawlExecutor") Executor crawlExecutor,
            TenantCrawlCooldownService crawlCooldownService,
            TemuAgentService temuAgentService,
            JdbcTemplate jdbc
    ) {
        this.dataScopeService = dataScopeService;
        this.crawlerProperties = crawlerProperties;
        this.objectMapper = objectMapper;
        this.crawlExecutor = crawlExecutor;
        this.crawlCooldownService = crawlCooldownService;
        this.temuAgentService = temuAgentService;
        this.jdbc = jdbc;
    }

    @Override
    public Map<String, Object> discoverCandidates(TemuCompetitorDiscoverRequest request) {
        Long tenantId = dataScopeService.requireTenantId();
        boolean force = request != null && Boolean.TRUE.equals(request.force());
        crawlCooldownService.assertAllowed(tenantId, force);
        String keyword = request == null || request.keyword() == null || request.keyword().isBlank()
                ? "fishing tackle"
                : request.keyword().trim();
        String region = request == null || request.region() == null || request.region().isBlank()
                ? "za"
                : request.region().trim();
        int limit = request == null || request.limit() == null || request.limit() <= 0 ? 10 : request.limit();

        Map<String, Object> result;
        if (crawlerProperties.isUseAgent()) {
            result = discoverViaAgent(tenantId, keyword, region, limit);
        } else {
            result = discoverViaLocalProcess(tenantId, keyword, region, limit);
        }
        crawlCooldownService.recordSuccess(tenantId);
        return result;
    }

    private Map<String, Object> discoverViaAgent(Long tenantId, String keyword, String region, int limit) {
        temuAgentService.assertAgentOnline(tenantId);
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        payload.put("keyword", keyword);
        payload.put("region", region);
        payload.put("limit", limit);
        insertAgentTask(tenantId, taskId, TemuAgentTasks.COMPETITOR_DISCOVER, payload);

        for (int i = 0; i < DISCOVER_TIMEOUT_SECONDS; i++) {
            Map<String, Object> row = loadAgentTask(tenantId, taskId);
            if (row == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_PROCESS_FAILED.getUserMessage());
            }
            String status = String.valueOf(row.get("status"));
            if ("success".equalsIgnoreCase(status)) {
                return parseDiscoverResult(row.get("result_json"), keyword, region);
            }
            if ("failed".equalsIgnoreCase(status)) {
                String errorMessage = stringValue(row.get("error_message"));
                // Debug: expose raw agent_task error_message so we can pinpoint COMPETITOR_* failure causes.
                // If it is blank, fallback to user-friendly mapping.
                if (errorMessage != null && !errorMessage.isBlank()) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST, errorMessage);
                }
                AppErrorCode code = AppErrorCode.classifyCrawlRaw(errorMessage);
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, code.getUserMessage());
            }
            sleepQuietly(1000);
        }
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_TIMEOUT.getUserMessage());
    }

    private Map<String, Object> discoverViaLocalProcess(Long tenantId, String keyword, String region, int limit) {
        Path scriptDir = Path.of(crawlerProperties.getScriptDir()).toAbsolutePath().normalize();
        if (!Files.isDirectory(scriptDir)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_SCRIPT_MISSING.getUserMessage());
        }

        List<String> command = new ArrayList<>();
        command.add(crawlerProperties.getPythonExecutable());
        command.add("competitor_discover.py");
        command.add("--tenant-id");
        command.add(String.valueOf(tenantId));
        command.add("--keyword");
        command.add(keyword);
        command.add("--region");
        command.add(region);
        command.add("--limit");
        command.add(String.valueOf(limit));
        command.add("--json");

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

            boolean finished = process.waitFor(DISCOVER_TIMEOUT_SECONDS, TimeUnit.SECONDS);
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

            JsonNode json = parseJsonLine(stdout);
            if (json == null || !json.isObject()) {
                Map<String, Object> fallback = new LinkedHashMap<>();
                fallback.put("keyword", keyword);
                fallback.put("region", region);
                fallback.put("candidates", List.of());
                return fallback;
            }
            return objectMapper.convertValue(json, new TypeReference<>() {});
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_PROCESS_FAILED.getUserMessage());
        }
    }

    private Map<String, Object> parseDiscoverResult(Object rawJson, String keyword, String region) {
        if (rawJson == null) {
            return emptyDiscoverResult(keyword, region);
        }
        try {
            Map<String, Object> parsed = objectMapper.readValue(
                    String.valueOf(rawJson),
                    new TypeReference<Map<String, Object>>() {}
            );
            if (parsed == null || parsed.isEmpty()) {
                return emptyDiscoverResult(keyword, region);
            }
            parsed.putIfAbsent("keyword", keyword);
            parsed.putIfAbsent("region", region);
            parsed.putIfAbsent("candidates", List.of());
            return parsed;
        } catch (Exception ex) {
            return emptyDiscoverResult(keyword, region);
        }
    }

    private Map<String, Object> emptyDiscoverResult(String keyword, String region) {
        Map<String, Object> fallback = new LinkedHashMap<>();
        fallback.put("keyword", keyword);
        fallback.put("region", region);
        fallback.put("candidates", List.of());
        return fallback;
    }

    private Map<String, Object> loadAgentTask(Long tenantId, String taskId) {
        List<Map<String, Object>> rows = jdbc.query(
                """
                SELECT status, error_message, result_json
                FROM agent_task
                WHERE id = ? AND tenant_id = ?
                LIMIT 1
                """,
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("status", rs.getString("status"));
                    row.put("error_message", rs.getString("error_message"));
                    row.put("result_json", rs.getString("result_json"));
                    return row;
                },
                taskId,
                tenantId
        );
        return rows.isEmpty() ? null : rows.get(0);
    }

    private void insertAgentTask(Long tenantId, String taskId, String taskType, Map<String, Object> payload) {
        String payloadJson;
        try {
            payloadJson = objectMapper.writeValueAsString(payload);
        } catch (Exception ex) {
            payloadJson = "{}";
        }
        jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, agent_id, task_type, status, payload_json, result_json,
                  error_code, error_message, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                taskId,
                tenantId,
                "",
                taskType,
                "pending",
                payloadJson,
                "{}",
                "",
                "",
                now(),
                "",
                ""
        );
    }

    private JsonNode parseJsonLine(String stdout) {
        if (stdout == null || stdout.isBlank()) return null;
        for (String line : stdout.split("\\R")) {
            String trimmed = line.trim();
            if (!trimmed.startsWith("{")) continue;
            try {
                return objectMapper.readTree(trimmed);
            } catch (Exception ignored) {
                // continue
            }
        }
        return null;
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

    private void sleepQuietly(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
