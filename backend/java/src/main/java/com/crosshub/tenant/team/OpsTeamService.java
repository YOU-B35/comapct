package com.crosshub.tenant.team;

import java.util.List;
import java.util.Map;

public interface OpsTeamService {
    List<Map<String, Object>> listTeams();

    Map<String, Object> getMyTeam();

    Map<String, Object> createTeam(String name, Long leaderUserId);

    Map<String, Object> updateTeam(Long teamId, String name, Long leaderUserId);

    void archiveTeam(Long teamId);

    List<Map<String, Object>> listMembers(Long teamId);

    List<Map<String, Object>> listUnassignedEmployees();

    Map<String, Object> addMember(Long teamId, Long userId);

    void removeMember(Long teamId, Long userId);
}
