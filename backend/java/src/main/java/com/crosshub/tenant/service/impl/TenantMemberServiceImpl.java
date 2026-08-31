package com.crosshub.tenant.service.impl;

import com.crosshub.tenant.service.TenantMemberService;
import com.crosshub.tenant.dto.ScopePayload;
import com.crosshub.tenant.dto.MemberPayload;
import com.crosshub.tenant.service.MemberScopeService;



import com.crosshub.auth.entity.AppUser;

import com.crosshub.auth.repository.AppUserRepository;

import com.crosshub.tenant.repository.SysMenuRepository;

import com.crosshub.security.AuthContext;
import com.crosshub.security.PasswordService;

import org.springframework.http.HttpStatus;

import org.springframework.stereotype.Service;

import org.springframework.transaction.annotation.Transactional;

import org.springframework.web.server.ResponseStatusException;



import java.time.LocalDateTime;

import java.time.format.DateTimeFormatter;

import java.util.LinkedHashMap;

import java.util.List;

import java.util.Map;



@Service

public class TenantMemberServiceImpl implements TenantMemberService {

    private static final DateTimeFormatter BOUND_AT_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");



    private final AppUserRepository userRepository;

    private final SysMenuRepository menuRepository;

    private final MemberScopeService memberScopeService;

    private final AuthContext authContext;
    private final PasswordService passwordService;



    public TenantMemberServiceImpl(

            AppUserRepository userRepository,

            SysMenuRepository menuRepository,

            MemberScopeService memberScopeService,

            AuthContext authContext,

            PasswordService passwordService

    ) {

        this.userRepository = userRepository;

        this.menuRepository = menuRepository;

        this.memberScopeService = memberScopeService;

        this.authContext = authContext;
        this.passwordService = passwordService;

    }



    public List<Map<String, Object>> listMembers() {

        Long tenantId = requireBossTenantId();

        return userRepository.findByTenantIdAndRoleOrderByIdAsc(tenantId, "user").stream()

                .map(this::toMemberDto)

                .toList();

    }



    public List<Map<String, Object>> assignableMenus() {

        requireBossTenantId();

        return List.of(Map.of(
                "code", "employee.warehouse",
                "label", "仓库下单",
                "group", "warehouse"
        ));

    }



    @Transactional

    public Map<String, Object> createMember(MemberPayload payload) {

        Long tenantId = requireBossTenantId();

        String account = normalizeAccount(payload.account());

        validateAccountAvailable(account, null);

        validateMemberPayload(payload, true);



        AppUser user = new AppUser();

        user.setTenantId(tenantId);

        user.setUsername(account);

        user.setPassword(passwordService.encode(requirePassword(payload.password(), true)));

        user.setNickname(trim(payload.name()));

        user.setJobTitle(trim(payload.role()));

        user.setEnterprise(resolveEnterprise());

        user.setRole("user");

        user.setPhone(trim(payload.phone()));

        user.setStatus(payload.status() == null || payload.status() ? "active" : "inactive");

        user.setCreatedAt(BOUND_AT_FORMAT.format(LocalDateTime.now()));

        userRepository.save(user);



        memberScopeService.replaceScopes(

                tenantId,

                user.getId(),

                payload.platforms(),

                payload.shopIds(),

                payload.menuCodes(),

                payload.menuCodes() != null

        );

        return toMemberDto(user);

    }



    @Transactional

    public Map<String, Object> updateMember(Long memberId, MemberPayload payload) {

        Long tenantId = requireBossTenantId();

        AppUser user = requireMember(tenantId, memberId);

        validateMemberPayload(payload, false);



        if (payload.account() != null) {

            String account = normalizeAccount(payload.account());

            validateAccountAvailable(account, memberId);

            user.setUsername(account);

        }

        if (payload.name() != null) user.setNickname(trim(payload.name()));

        if (payload.role() != null) user.setJobTitle(trim(payload.role()));

        if (payload.phone() != null) user.setPhone(trim(payload.phone()));

        if (payload.password() != null && !payload.password().isBlank()) {

            user.setPassword(passwordService.encode(payload.password()));

        }

        if (payload.status() != null) {

            user.setStatus(payload.status() ? "active" : "inactive");

        }

        userRepository.save(user);



        if (payload.platforms() != null) {

            memberScopeService.replaceScopes(

                    tenantId,

                    user.getId(),

                    payload.platforms(),

                    payload.shopIds() == null ? List.of() : payload.shopIds(),

                    payload.menuCodes(),

                    payload.menuCodes() != null

            );

        }

        return toMemberDto(user);

    }



    @Transactional

    public Map<String, Object> updateScopes(Long memberId, ScopePayload payload) {

        Long tenantId = requireBossTenantId();

        AppUser user = requireMember(tenantId, memberId);

        if (payload.platforms() == null || payload.platforms().isEmpty()) {

            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请至少选择一个负责平台");

        }

        memberScopeService.replaceScopes(

                tenantId,

                user.getId(),

                payload.platforms(),

                payload.shopIds(),

                payload.menuCodes(),

                payload.menuCodes() != null

        );

        return toMemberDto(user);

    }



    @Transactional

    public void deleteMember(Long memberId) {

        Long tenantId = requireBossTenantId();

        AppUser user = requireMember(tenantId, memberId);

        memberScopeService.deleteAllScopes(tenantId, user.getId());

        userRepository.delete(user);

    }



    @Transactional

    public Map<String, Object> updateStatus(Long memberId, boolean active) {

        Long tenantId = requireBossTenantId();

        AppUser user = requireMember(tenantId, memberId);

        user.setStatus(active ? "active" : "inactive");

        userRepository.save(user);

        return toMemberDto(user);

    }



    private Map<String, Object> toMemberDto(AppUser user) {

        Long tenantId = user.getTenantId();

        Long userId = user.getId();

        Map<String, Object> item = new LinkedHashMap<>();

        item.put("id", userId);

        item.put("name", user.getNickname());

        item.put("account", user.getUsername());

        item.put("role", user.getJobTitle());

        item.put("per", user.getPer());

        item.put("portal_role", com.crosshub.auth.PortalPer.portalFromPer(user.getPer()));

        item.put("phone", user.getPhone() == null ? "" : user.getPhone());

        item.put("status", user.isActive());

        item.put("boundAt", user.getCreatedAt() == null ? "" : user.getCreatedAt());

        item.put("platforms", memberScopeService.platformsForMember(tenantId, userId));

        item.put("assignedStoreIds", memberScopeService.shopIdsForMember(tenantId, userId));

        item.put("menu_codes", memberScopeService.menuCodesForMember(tenantId, userId));

        return item;

    }



    private AppUser requireMember(Long tenantId, Long memberId) {

        AppUser user = userRepository.findByIdAndTenantId(memberId, tenantId)

                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "员工不存在"));

        if (user.isAdmin()) {

            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "不能操作管理员账号");

        }

        return user;

    }



    private Long requireBossTenantId() {

        if (!authContext.isBossPortal() || !authContext.isAdmin()) {

            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员可操作");

        }

        Long tenantId = authContext.tenantId();

        if (tenantId == null) {

            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");

        }

        return tenantId;

    }



    private void validateMemberPayload(MemberPayload payload, boolean creating) {

        if (creating || payload.name() != null) {

            if (trim(payload.name()).isBlank()) {

                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请填写员工姓名");

            }

        }

        if (creating || payload.role() != null) {

            if (trim(payload.role()).isBlank()) {

                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请选择岗位角色");

            }

        }

        if (creating) {

            if (payload.platforms() == null || payload.platforms().isEmpty()) {

                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请至少选择一个负责平台");

            }

        }

    }



    private void validateAccountAvailable(String account, Long excludeId) {
        Long tenantId = requireBossTenantId();
        boolean exists = excludeId == null
                ? userRepository.existsByTenantIdAndUsernameIgnoreCase(tenantId, account)
                : userRepository.existsByTenantIdAndUsernameIgnoreCaseAndIdNot(tenantId, account, excludeId);
        if (exists) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "登录账号已被使用");
        }
    }



    private String normalizeAccount(String account) {

        String value = trim(account);

        if (value.isBlank()) {

            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请填写登录账号");

        }

        return value;

    }



    private String requirePassword(String password, boolean required) {

        String value = password == null ? "" : password;

        if (required && value.isBlank()) {

            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请设置登录密码");

        }

        return value;

    }



    private String trim(String value) {

        return value == null ? "" : value.trim();

    }



    private String resolveEnterprise() {

        return userRepository.findById(authContext.userId())

                .map(AppUser::getEnterprise)

                .orElse("");

    }







}
