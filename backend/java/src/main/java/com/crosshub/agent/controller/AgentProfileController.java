package com.crosshub.agent.controller;

import com.crosshub.agent.service.AgentProfileService;
import com.crosshub.security.AgentContext;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/agent/profiles")
public class AgentProfileController {
    private final AgentProfileService profileService;
    private final AgentContext agentContext;

    public AgentProfileController(AgentProfileService profileService, AgentContext agentContext) {
        this.profileService = profileService;
        this.agentContext = agentContext;
    }

    @PutMapping(value = "/{platform}/{tenantId}/{sessionKey}")
    public Map<String, Object> uploadProfile(
            @PathVariable String platform,
            @PathVariable Long tenantId,
            @PathVariable String sessionKey,
            @RequestBody byte[] body,
            @RequestHeader(value = "If-Match", required = false) String ifMatch
    ) {
        requireTenantMatch(tenantId);
        String agentId = agentContext.agent() == null ? "" : agentContext.agent().getId();
        AgentProfileService.ProfileRow row = profileService.putBundle(
                tenantId, platform, sessionKey, body, ifMatch, agentId
        );
        return Map.of("success", true, "data", profileService.toDto(row));
    }

    @GetMapping("/{platform}/{tenantId}/{sessionKey}")
    public ResponseEntity<byte[]> downloadProfile(
            @PathVariable String platform,
            @PathVariable Long tenantId,
            @PathVariable String sessionKey,
            @RequestHeader(value = "If-None-Match", required = false) String ifNoneMatch
    ) {
        requireTenantMatch(tenantId);
        byte[] bytes = profileService.getBundle(tenantId, platform, sessionKey, ifNoneMatch);
        if (bytes == null) {
            AgentProfileService.ProfileRow row = profileService.headProfile(tenantId, platform, sessionKey);
            return ResponseEntity.status(HttpStatus.NOT_MODIFIED)
                    .eTag(row.bundleSha256())
                    .build();
        }
        AgentProfileService.ProfileRow row = profileService.headProfile(tenantId, platform, sessionKey);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("application/zip"))
                .eTag(row.bundleSha256())
                .header(HttpHeaders.CONTENT_LENGTH, String.valueOf(bytes.length))
                .body(bytes);
    }

    @RequestMapping(value = "/{platform}/{tenantId}/{sessionKey}", method = RequestMethod.HEAD)
    public ResponseEntity<Void> headProfile(
            @PathVariable String platform,
            @PathVariable Long tenantId,
            @PathVariable String sessionKey
    ) {
        requireTenantMatch(tenantId);
        AgentProfileService.ProfileRow row = profileService.headProfile(tenantId, platform, sessionKey);
        return ResponseEntity.ok()
                .eTag(row.bundleSha256())
                .header(HttpHeaders.CONTENT_LENGTH, String.valueOf(row.bundleBytes()))
                .build();
    }

    @GetMapping("/{platform}/{tenantId}")
    public Map<String, Object> listProfiles(
            @PathVariable String platform,
            @PathVariable Long tenantId
    ) {
        requireTenantMatch(tenantId);
        List<Map<String, Object>> rows = profileService.listByTenant(tenantId, platform).stream()
                .filter(AgentProfileService::hasBundle)
                .map(profileService::toDto)
                .toList();
        return Map.of("success", true, "data", rows);
    }

    private void requireTenantMatch(Long tenantId) {
        Long tokenTenant = agentContext.tenantId();
        if (tokenTenant == null || !tokenTenant.equals(tenantId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "租户不匹配");
        }
    }
}
