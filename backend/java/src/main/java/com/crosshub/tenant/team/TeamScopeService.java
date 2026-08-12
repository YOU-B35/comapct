package com.crosshub.tenant.team;

import java.util.List;
import java.util.Map;
import java.util.Optional;

public interface TeamScopeService {
    Optional<Map<String, Object>> findActiveLedTeam(Long tenantId, Long userId);

    boolean isTeamLeader(Long tenantId, Long userId);

    List<Long> listMemberUserIds(Long teamId);

    /** 本组员 ∪ 主管本人 */
    List<Long> listManageableUserIds(Long tenantId, Long leaderUserId);

    void assertBossOrLeader(Long tenantId, Long userId);

    void assertCanManageUser(Long tenantId, Long actorUserId, Long targetUserId);

    boolean isUserInActiveTeam(Long userId);

    Optional<Long> findActiveTeamIdOfMember(Long userId);
}
