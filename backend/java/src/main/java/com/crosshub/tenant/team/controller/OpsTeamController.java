package com.crosshub.tenant.team.controller;

import com.crosshub.tenant.team.OpsTeamService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/tenant/ops-teams")
public class OpsTeamController {
    private final OpsTeamService opsTeamService;

    public OpsTeamController(OpsTeamService opsTeamService) {
        this.opsTeamService = opsTeamService;
    }

    @GetMapping
    public Map<String, Object> list() {
        return Map.of("code", 0, "data", opsTeamService.listTeams());
    }

    @GetMapping("/mine")
    public Map<String, Object> mine() {
        return Map.of("code", 0, "data", opsTeamService.getMyTeam());
    }

    @GetMapping("/unassigned-employees")
    public Map<String, Object> unassigned() {
        return Map.of("code", 0, "data", opsTeamService.listUnassignedEmployees());
    }

    @PostMapping
    public Map<String, Object> create(@RequestBody Map<String, Object> body) {
        String name = text(body.get("name"));
        Long leaderUserId = asLong(body.get("leaderUserId"));
        return Map.of("code", 0, "data", opsTeamService.createTeam(name, leaderUserId));
    }

    @PutMapping("/{id}")
    public Map<String, Object> update(@PathVariable("id") Long id, @RequestBody Map<String, Object> body) {
        String name = body.containsKey("name") ? text(body.get("name")) : null;
        Long leaderUserId = body.containsKey("leaderUserId") ? asLong(body.get("leaderUserId")) : null;
        return Map.of("code", 0, "data", opsTeamService.updateTeam(id, name, leaderUserId));
    }

    @PostMapping("/{id}/archive")
    public Map<String, Object> archive(@PathVariable("id") Long id) {
        opsTeamService.archiveTeam(id);
        return Map.of("code", 0, "data", true);
    }

    @GetMapping("/{id}/members")
    public Map<String, Object> members(@PathVariable("id") Long id) {
        return Map.of("code", 0, "data", opsTeamService.listMembers(id));
    }

    @PostMapping("/{id}/members")
    public Map<String, Object> addMember(@PathVariable("id") Long id, @RequestBody Map<String, Object> body) {
        Long userId = asLong(body.get("userId"));
        return Map.of("code", 0, "data", opsTeamService.addMember(id, userId));
    }

    @DeleteMapping("/{id}/members/{userId}")
    public Map<String, Object> removeMember(@PathVariable("id") Long id, @PathVariable("userId") Long userId) {
        opsTeamService.removeMember(id, userId);
        return Map.of("code", 0, "data", true);
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static Long asLong(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number n) {
            return n.longValue();
        }
        String text = String.valueOf(value).trim();
        if (text.isEmpty()) {
            return null;
        }
        return Long.parseLong(text);
    }
}
