package com.crosshub.common.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.common.CrawlCooldownException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.Map;

@RestControllerAdvice
public class ApiExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(CrawlCooldownException.class)
    public ResponseEntity<Map<String, Object>> handleCooldown(CrawlCooldownException ex) {
        String msg = ex.getMessage();
        if (msg == null || msg.isBlank()) {
            msg = AppErrorCode.CRAWL_COOLDOWN.getUserMessage();
        }
        return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                .body(ApiResult.error(
                        HttpStatus.TOO_MANY_REQUESTS.value(),
                        AppErrorCode.CRAWL_COOLDOWN.getCode(),
                        msg
                ));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(NoResourceFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResult.error(
                        HttpStatus.NOT_FOUND.value(),
                        AppErrorCode.UNKNOWN.getCode(),
                        "接口不存在"
                ));
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> handle(ResponseStatusException ex) {
        String reason = ex.getReason() == null ? "" : ex.getReason().trim();
        AppErrorCode errorCode = AppErrorCode.fromReason(reason);
        String message = errorCode == AppErrorCode.UNKNOWN && !reason.isBlank()
                ? reason
                : errorCode.getUserMessage();
        return ResponseEntity.status(ex.getStatusCode())
                .body(ApiResult.error(ex.getStatusCode().value(), errorCode.getCode(), message));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGeneric(Exception ex) {
        log.error("Unhandled API error", ex);
        AppErrorCode errorCode = AppErrorCode.SERVER_ERROR;
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResult.error(
                        HttpStatus.INTERNAL_SERVER_ERROR.value(),
                        errorCode.getCode(),
                        errorCode.getUserMessage()
                ));
    }
}
