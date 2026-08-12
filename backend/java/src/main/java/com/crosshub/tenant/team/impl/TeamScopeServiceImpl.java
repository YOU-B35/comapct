package com.crosshub.tenant.team.impl;

import com.crosshub.security.AuthContext;
import com.crosshub.tenant.team.TeamScopeService;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
public class TeamScopeServiceImpl implements TeamScopeService {
    private final JdbcTemplate jdbc;
    private final AuthContext authContext;

    public TeamScopeServiceImpl(JdbcTemplate jdbc, AuthContext authContext) {
        this.jdbc = jdbc;
        this.authContext = authContext;
    }

    @Override
    public Optional<Map<String, Object>> findActiveLedTeam(Long tenantId, Long userId) {
        if (tenantId == null || userId == null) {
            return Optional.empty();
        }
        List<Map<String, Object>> rows = jdbc.query(
                """
                        SELECT id, tenant_id, name, leader_user_id, status, created_by, created_at, updated_at
                        FROM ops_team
                        WHERE tenant_id = ? AND leader_user_id = ? AND status = 'active'
                        LIMIT 1
                        """,
                (rs, i) -> mapTeam(rs),
                tenantId,
                userId
        );
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }

    @Override
    public boolean isTeamLeader(Long tenantId, Long userId) {
        return findActiveLedTeam(tenantId, userId).isPresent();
    }

    @Override
    public List<Long> listMemberUserIds(Long teamId) {
        if (teamId == null) {
            return List.of();
        }
        return jdbc.query(
                "SELECT user_id FROM ops_team_member WHERE team_id = ?",
                (rs, i) -> rs.getLong(1),
                teamId
        );
    }

    @Override
    public List<Long> listManageableUserIds(Long tenantId, Long leaderUserId) {
        Optional<Map<String, Object>> team = findActiveLedTeam(tenantId, leaderUserId);
        if (team.isEmpty()) {
            return List.of();
        }
        Long teamId = ((Number) team.get().get("id")).longValue();
        List<Long> ids = new ArrayList<>(listMemberUserIds(teamId));
        if (!ids.contains(leaderUserId)) {
            ids.add(leaderUserId);
        }
        return ids;
    }

    @Override
    public void assertBossOrLeader(Long tenantId, Long userId) {
        if (authContext.isBossPortal() && authContext.isAdmin()) {
            return;
        }
        if (!isTeamLeader(tenantId, userId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员或小组主管可操作");
        }
    }

    @Override
    public void assertCanManageUser(Long tenantId, Long actorUserId, Long targetUserId) {
        if (authContext.isBossPortal() && authContext.isAdmin()) {
            return;
        }
        Optional<Map<String, Object>> team = findActiveLedTeam(tenantId, actorUserId);
        if (team.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅小组主管可操作本组员工");
        }
        Long teamId = ((Number) team.get().get("id")).longValue();
        Long leaderId = ((Number) team.get().get("leaderUserId")).longValue();
        if (targetUserId != null && targetUserId.equals(leaderId)) {
            // 主管改自己绑定：允许读自己，写绑定按产品可选；第一期允许管理自己（派任务）
            return;
        }
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM ops_team_member WHERE team_id = ? AND user_id = ?",
                Integer.class,
                teamId,
                targetUserId
        );
        if (count == null || count == 0) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "目标员工不在您的小组管辖范围");
        }
    }

    @Override
    public boolean isUserInActiveTeam(Long userId) {
        if (userId == null) {
            return false;
        }
        Integer asMember = jdbc.queryForObject(
                """
                        SELECT COUNT(*) FROM ops_team_member m
                        INNER JOIN ops_team t ON t.id = m.team_id AND t.status = 'active'
                        WHERE m.user_id = ?
                        """,
                Integer.class,
                userId
        );
        if (asMember != null && asMember > 0) {
            return true;
        }
        Integer asLeader = jdbc.queryForObject(
                "SELECT COUNT(*) FROM ops_team WHERE leader_user_id = ? AND status = 'active'",
                Integer.class,
                userId
        );
        return asLeader != null && asLeader > 0;
    }

    @Override
    public Optional<Long> findActiveTeamIdOfMember(Long userId) {
        if (userId == null) {
            return Optional.empty();
        }
        List<Long> ids = jdbc.query(
                """
                        SELECT m.team_id FROM ops_team_member m
                        INNER JOIN ops_team t ON t.id = m.team_id AND t.status = 'active'
                        WHERE m.user_id = ?
                        LIMIT 1
                        """,
                (rs, i) -> rs.getLong(1),
                userId
        );
        return ids.isEmpty() ? Optional.empty() : Optional.of(ids.get(0));
    }

    private Map<String, Object> mapTeam(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", rs.getLong("id"));
        row.put("tenantId", rs.getLong("tenant_id"));
        row.put("name", rs.getString("name"));
        row.put("leaderUserId", rs.getLong("leader_user_id"));
        row.put("status", rs.getString("status"));
        row.put("createdBy", rs.getObject("created_by"));
        row.put("createdAt", rs.getString("created_at"));
        row.put("updatedAt", rs.getString("updated_at"));
        return row;
    }
}
