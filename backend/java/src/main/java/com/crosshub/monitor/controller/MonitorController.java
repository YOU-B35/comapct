package com.crosshub.monitor.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.monitor.service.MonitorJobConflictException;
import com.crosshub.monitor.service.MonitorService;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.nio.file.Path;
import java.util.Map;

@RestController
@RequestMapping("/api/monitor")
public class MonitorController {
    private final MonitorService monitorService;

    public MonitorController(MonitorService monitorService) {
        this.monitorService = monitorService;
    }

    @GetMapping("/targets")
    public Map<String, Object> listTargets(@RequestParam(value = "platform", required = false) String platform) {
        return ApiResult.ok(monitorService.listTargets(platform));
    }

    @PostMapping("/targets")
    public Map<String, Object> createTarget(@RequestBody Map<String, Object> payload) {
        return ApiResult.ok(monitorService.createTarget(payload));
    }

    @PutMapping("/targets/{id}")
    public Map<String, Object> updateTarget(@PathVariable String id, @RequestBody Map<String, Object> payload) {
        return ApiResult.ok(monitorService.updateTarget(id, payload));
    }

    @DeleteMapping("/targets/{id}")
    public Map<String, Object> deleteTarget(@PathVariable String id) {
        monitorService.deleteTarget(id);
        return ApiResult.ok(Map.of("deleted", true, "id", id));
    }

    @PutMapping("/targets/{id}/schedule")
    public Map<String, Object> updateSchedule(@PathVariable String id, @RequestBody Map<String, Object> payload) {
        return ApiResult.ok(monitorService.updateSchedule(id, payload));
    }

    @PostMapping("/targets/{id}/trigger")
    public ResponseEntity<Map<String, Object>> trigger(
            @PathVariable String id,
            @RequestBody(required = false) Map<String, Object> payload
    ) {
        try {
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResult.ok(monitorService.trigger(id, payload)));
        } catch (MonitorJobConflictException ex) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResult.conflict(
                    409,
                    AppErrorCode.MONITOR_JOB_IN_PROGRESS.getUserMessage(),
                    AppErrorCode.MONITOR_JOB_IN_PROGRESS.getCode(),
                    ex.getExistingJob()
            ));
        }
    }

    @GetMapping("/targets/{id}/latest")
    public Map<String, Object> latest(@PathVariable String id) {
        return ApiResult.ok(monitorService.getLatest(id));
    }

    @GetMapping("/targets/{id}/history")
    public Map<String, Object> history(@PathVariable String id) {
        return ApiResult.ok(monitorService.getHistory(id));
    }

    @GetMapping("/targets/{id}/trend")
    public Map<String, Object> trend(
            @PathVariable String id,
            @RequestParam(defaultValue = "30") int days,
            @RequestParam(required = false) String product_id
    ) {
        return ApiResult.ok(monitorService.getTrend(id, days, product_id));
    }

    @GetMapping("/targets/{id}/signals")
    public Map<String, Object> signals(
            @PathVariable String id,
            @RequestParam(defaultValue = "50") int limit
    ) {
        return ApiResult.ok(monitorService.getSignals(id, limit));
    }

    @GetMapping("/jobs/{jobId}")
    public Map<String, Object> job(@PathVariable String jobId) {
        return ApiResult.ok(monitorService.getJob(jobId));
    }

    @GetMapping("/jobs")
    public Map<String, Object> jobs(
            @RequestParam("target_id") String targetId,
            @RequestParam(defaultValue = "20") int limit
    ) {
        return ApiResult.ok(Map.of("jobs", monitorService.listRecentJobs(targetId, limit)));
    }

    @GetMapping("/targets/{id}/report.xlsx")
    public ResponseEntity<Resource> report(@PathVariable String id) {
        Path file = monitorService.resolveReportXlsx(id);
        Resource resource = new FileSystemResource(file);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + file.getFileName() + "\"")
                .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                .body(resource);
    }
}
