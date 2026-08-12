package com.crosshub.tenant.team.impl;

import com.crosshub.auth.entity.AppUser;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.team.OpsTeamService;
import com.crosshub.tenant.team.TeamScopeService;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

@Service
public class OpsTeamServiceImpl implements OpsTeamService {
    private static final DateTimeFormatter DT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;
    private final AuthContext authContext;
    private final TeamScopeService teamScopeService;
    private final AppUserRepository userRepository;

    public OpsTeamServiceImpl(
            JdbcTemplate jdbc,
            AuthContext authContext,
            TeamScopeService teamScopeService,
            AppUserRepository userRepository
    ) {
        this.jdbc = jdbc;
        this.authContext = authContext;
        this.teamScopeService = teamScopeService;
        this.userRepository = userRepository;
    }

    @Override
    public List<Map<String, Object>> listTeams() {
        Long tenantId = requireBossTenant();
        return jdbc.query(
                """
                        SELECT t.*, u.nickname AS leader_name, u.username AS leader_account
                        FROM ops_team t
                        LEFT JOIN app_user u ON u.id = t.leader_user_id
                        WHERE t.tenant_id = ?
                        ORDER BY CASE WHEN t.status = 'active' THEN 0 ELSE 1 END, t.id DESC
                        """,
                (rs, i) -> {
                    Map<String, Object> row = mapTeam(rs);
                    long teamId = rs.getLong("id");
                    row.put("leaderName", rs.getString("leader_name"));
                    row.put("leaderAccount", rs.getString("leader_account"));
                    List<Long> memberIds = listMemberUserIds(teamId);
                    row.put("memberCount", memberIds.size());
                    row.put("memberUserIds", memberIds);
                    return row;
                },
                tenantId
        );
    }

    private List<Long> listMemberUserIds(Long teamId) {
        return jdbc.query(
                "SELECT user_id FROM ops_team_member WHERE team_id = ?",
                (rs, i) -> rs.getLong(1),
                teamId
        );
    }

    @Override
    public Map<String, Object> getMyTeam() {
        Long tenantId = requireTenant();
        Long userId = requireUser();
        Map<String, Object> team = teamScopeService.findActiveLedTeam(tenantId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "仅小组主管可查看本组"));
        enrichLeader(team);
        team.put("members", listMembers(((Number) team.get("id")).longValue()));
        return team;
    }

    @Override
    @Transactional
    public Map<String, Object> createTeam(String name, Long leaderUserId) {
        Long tenantId = requireBossTenant();
        String teamName = requireName(name);
        AppUser leader = requireEmployee(tenantId, leaderUserId);
        assertLeaderAvailable(tenantId, leaderUserId, null);
        if (teamScopeService.isUserInActiveTeam(leaderUserId)
                && teamScopeService.findActiveTeamIdOfMember(leaderUserId).isPresent()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "该员工已在其他小组中，请先移出");
        }
        String now = nowText();
        KeyHolder keys = new GeneratedKeyHolder();
        Long actorId = authContext.userId();
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement(
                    """
                            INSERT INTO ops_team (tenant_id, name, leader_user_id, status, created_by, created_at, updated_at)
                            VALUES (?, ?, ?, 'active', ?, ?, ?)
                            """,
                    Statement.RETURN_GENERATED_KEYS
            );
            ps.setLong(1, tenantId);
            ps.setString(2, teamName);
            ps.setLong(3, leaderUserId);
            if (actorId == null) {
                ps.setObject(4, null);
            } else {
                ps.setLong(4, actorId);
            }
            ps.setString(5, now);
            ps.setString(6, now);
            return ps;
        }, keys);
        Number key = keys.getKey();
        if (key == null) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "创建小组失败");
        }
        return getTeam(tenantId, key.longValue());
    }

    @Override
    @Transactional
    public Map<String, Object> updateTeam(Long teamId, String name, Long leaderUserId) {
        Long tenantId = requireBossTenant();
        Map<String, Object> existing = getTeam(tenantId, teamId);
        if (!"active".equals(String.valueOf(existing.get("status")))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "已归档小组不可修改");
        }
        String teamName = name == null || name.isBlank() ? String.valueOf(existing.get("name")) : requireName(name);
        Long nextLeader = leaderUserId == null
                ? ((Number) existing.get("leaderUserId")).longValue()
                : leaderUserId;
        if (!Objects.equals(nextLeader, ((Number) existing.get("leaderUserId")).longValue())) {
            requireEmployee(tenantId, nextLeader);
            assertLeaderAvailable(tenantId, nextLeader, teamId);
            // 新主管若是本组员，先移出成员表
            jdbc.update("DELETE FROM ops_team_member WHERE team_id = ? AND user_id = ?", teamId, nextLeader);
            if (teamScopeService.findActiveTeamIdOfMember(nextLeader).isPresent()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "该员工已在其他小组中，请先移出");
            }
        }
        jdbc.update(
                "UPDATE ops_team SET name = ?, leader_user_id = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                teamName,
                nextLeader,
                nowText(),
                tenantId,
                teamId
        );
        return getTeam(tenantId, teamId);
    }

    @Override
    @Transactional
    public void archiveTeam(Long teamId) {
        Long tenantId = requireBossTenant();
        getTeam(tenantId, teamId);
        jdbc.update("DELETE FROM ops_team_member WHERE team_id = ?", teamId);
        jdbc.update(
                "UPDATE ops_team SET status = 'archived', updated_at = ? WHERE tenant_id = ? AND id = ?",
                nowText(),
                tenantId,
                teamId
        );
    }

    @Override
    public List<Map<String, Object>> listMembers(Long teamId) {
        Long tenantId = requireTenant();
        Long userId = requireUser();
        Map<String, Object> team = getTeam(tenantId, teamId);
        if (!(authContext.isBossPortal() && authContext.isAdmin())) {
            Long leaderId = ((Number) team.get("leaderUserId")).longValue();
            if (!userId.equals(leaderId) || !"active".equals(String.valueOf(team.get("status")))) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员或本组主管可查看成员");
            }
        }
        return jdbc.query(
                """
                        SELECT m.*, u.nickname, u.username, u.job_title, u.other_role, u.status AS user_status
                        FROM ops_team_member m
                        INNER JOIN app_user u ON u.id = m.user_id
                        WHERE m.team_id = ?
                        ORDER BY m.id ASC
                        """,
                (rs, i) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("teamId", rs.getLong("team_id"));
                    row.put("userId", rs.getLong("user_id"));
                    row.put("name", rs.getString("nickname"));
                    row.put("account", rs.getString("username"));
                    row.put("role", rs.getString("job_title"));
                    row.put("otherRole", rs.getString("other_role"));
                    row.put("status", "active".equalsIgnoreCase(rs.getString("user_status")));
                    row.put("joinedAt", rs.getString("joined_at"));
                    row.put("addedBy", rs.getObject("added_by"));
                    return row;
                },
                teamId
        );
    }

    @Override
    public List<Map<String, Object>> listUnassignedEmployees() {
        Long tenantId = requireTenant();
        Long userId = requireUser();
        teamScopeService.assertBossOrLeader(tenantId, userId);
        return jdbc.query(
                """
                        SELECT u.id, u.nickname, u.username, u.job_title, u.other_role, u.status
                        FROM app_user u
                        WHERE u.tenant_id = ? AND lower(u.role) = 'user'
                          AND u.id NOT IN (
                            SELECT leader_user_id FROM ops_team WHERE tenant_id = ? AND status = 'active'
                          )
                          AND u.id NOT IN (
                            SELECT m.user_id FROM ops_team_member m
                            INNER JOIN ops_team t ON t.id = m.team_id AND t.status = 'active'
                          )
                        ORDER BY u.id ASC
                        """,
                (rs, i) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("userId", rs.getLong("id"));
                    row.put("name", rs.getString("nickname"));
                    row.put("account", rs.getString("username"));
                    row.put("role", rs.getString("job_title"));
                    row.put("otherRole", rs.getString("other_role"));
                    row.put("status", "active".equalsIgnoreCase(rs.getString("status")));
                    return row;
                },
                tenantId,
                tenantId
        );
    }

    @Override
    @Transactional
    public Map<String, Object> addMember(Long teamId, Long memberUserId) {
        Long tenantId = requireTenant();
        Long actorId = requireUser();
        Map<String, Object> team = getTeam(tenantId, teamId);
        if (!"active".equals(String.valueOf(team.get("status")))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "已归档小组不可加人");
        }
        boolean boss = authContext.isBossPortal() && authContext.isAdmin();
        Long leaderId = ((Number) team.get("leaderUserId")).longValue();
        if (!boss && !actorId.equals(leaderId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员或本组主管可添加成员");
        }
        AppUser member = requireEmployee(tenantId, memberUserId);
        if (memberUserId.equals(leaderId)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "主管无需加入成员列表");
        }
        if (teamScopeService.isUserInActiveTeam(memberUserId)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "该员工已在其他小组中");
        }
        jdbc.update(
                """
                        INSERT INTO ops_team_member (tenant_id, team_id, user_id, joined_at, added_by)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                tenantId,
                teamId,
                memberUserId,
                nowText(),
                actorId
        );
        jdbc.update("UPDATE ops_team SET updated_at = ? WHERE id = ?", nowText(), teamId);
        return Map.of(
                "userId", member.getId(),
                "name", member.getNickname() == null ? "" : member.getNickname(),
                "account", member.getUsername()
        );
    }

    @Override
    @Transactional
    public void removeMember(Long teamId, Long memberUserId) {
        Long tenantId = requireTenant();
        Long actorId = requireUser();
        Map<String, Object> team = getTeam(tenantId, teamId);
        boolean boss = authContext.isBossPortal() && authContext.isAdmin();
        Long leaderId = ((Number) team.get("leaderUserId")).longValue();
        if (!boss && !actorId.equals(leaderId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员或本组主管可移除成员");
        }
        int n = jdbc.update(
                "DELETE FROM ops_team_member WHERE team_id = ? AND user_id = ?",
                teamId,
                memberUserId
        );
        if (n == 0) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "成员不在该小组中");
        }
        jdbc.update("UPDATE ops_team SET updated_at = ? WHERE id = ?", nowText(), teamId);
    }

    private Map<String, Object> getTeam(Long tenantId, Long teamId) {
        List<Map<String, Object>> rows = jdbc.query(
                "SELECT * FROM ops_team WHERE tenant_id = ? AND id = ? LIMIT 1",
                (rs, i) -> mapTeam(rs),
                tenantId,
                teamId
        );
        if (rows.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "小组不存在");
        }
        Map<String, Object> team = rows.get(0);
        enrichLeader(team);
        team.put("memberCount", countMembers(teamId));
        return team;
    }

    private void enrichLeader(Map<String, Object> team) {
        Long leaderId = ((Number) team.get("leaderUserId")).longValue();
        userRepository.findById(leaderId).ifPresent(u -> {
            team.put("leaderName", u.getNickname());
            team.put("leaderAccount", u.getUsername());
        });
    }

    private int countMembers(Long teamId) {
        Integer n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM ops_team_member WHERE team_id = ?",
                Integer.class,
                teamId
        );
        return n == null ? 0 : n;
    }

    private void assertLeaderAvailable(Long tenantId, Long leaderUserId, Long excludeTeamId) {
        List<Long> ids = jdbc.query(
                """
                        SELECT id FROM ops_team
                        WHERE tenant_id = ? AND leader_user_id = ? AND status = 'active'
                        """,
                (rs, i) -> rs.getLong(1),
                tenantId,
                leaderUserId
        );
        for (Long id : ids) {
            if (excludeTeamId == null || !id.equals(excludeTeamId)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "该员工已是其他小组的主管");
            }
        }
    }

    private AppUser requireEmployee(Long tenantId, Long userId) {
        AppUser user = userRepository.findByIdAndTenantId(userId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "员工不存在"));
        if (!"user".equalsIgnoreCase(user.getRole())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "只能指定员工账号为主管或组员");
        }
        if (!user.isActive()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "账号已停用");
        }
        return user;
    }

    private Long requireBossTenant() {
        if (!authContext.isBossPortal() || !authContext.isAdmin()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员可管理运营小组");
        }
        return requireTenant();
    }

    private Long requireTenant() {
        Long tenantId = authContext.tenantId();
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        return tenantId;
    }

    private Long requireUser() {
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        return userId;
    }

    private String requireName(String name) {
        String value = name == null ? "" : name.trim();
        if (value.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请填写小组名称");
        }
        return value;
    }

    private String nowText() {
        return LocalDateTime.now().format(DT);
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
