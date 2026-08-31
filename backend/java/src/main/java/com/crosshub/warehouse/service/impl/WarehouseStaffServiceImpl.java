package com.crosshub.warehouse.service.impl;

import com.crosshub.warehouse.service.WarehouseStaffService;
import com.crosshub.warehouse.dto.StaffPayload;

import com.crosshub.auth.entity.AppUser;
import com.crosshub.warehouse.entity.UserWarehouseScope;
import com.crosshub.warehouse.entity.WarehouseSite;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.warehouse.repository.UserWarehouseScopeRepository;
import com.crosshub.warehouse.repository.WarehouseSiteRepository;
import com.crosshub.security.AuthContext;
import com.crosshub.security.PasswordService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class WarehouseStaffServiceImpl implements WarehouseStaffService {
    private static final String WAREHOUSE_JOB_TITLE = "仓库管理员";
    private static final DateTimeFormatter BOUND_AT_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final AppUserRepository userRepository;
    private final UserWarehouseScopeRepository warehouseScopeRepository;
    private final WarehouseSiteRepository warehouseSiteRepository;
    private final AuthContext authContext;
    private final PasswordService passwordService;

    public WarehouseStaffServiceImpl(
            AppUserRepository userRepository,
            UserWarehouseScopeRepository warehouseScopeRepository,
            WarehouseSiteRepository warehouseSiteRepository,
            AuthContext authContext,
            PasswordService passwordService
    ) {
        this.userRepository = userRepository;
        this.warehouseScopeRepository = warehouseScopeRepository;
        this.warehouseSiteRepository = warehouseSiteRepository;
        this.authContext = authContext;
        this.passwordService = passwordService;
    }

    public List<Map<String, Object>> listStaff() {
        Long tenantId = requireManageStaffTenantId();
        return userRepository.findByTenantIdAndRoleOrderByIdAsc(tenantId, "warehouse").stream()
                .map(this::toStaffDto)
                .toList();
    }

    @Transactional
    public Map<String, Object> createStaff(StaffPayload payload) {
        Long tenantId = requireManageStaffTenantId();
        String account = normalizeAccount(payload.account());
        validateAccountAvailable(account, null);
        validateStaffPayload(payload, true);

        AppUser user = new AppUser();
        user.setTenantId(tenantId);
        user.setUsername(account);
        user.setPassword(passwordService.encode(requirePassword(payload.password(), true)));
        user.setNickname(trim(payload.name()));
        user.setJobTitle(WAREHOUSE_JOB_TITLE);
        user.setEnterprise(resolveEnterprise());
        user.setRole("warehouse");
        user.setPhone(trim(payload.phone()));
        user.setStatus(payload.status() == null || payload.status() ? "active" : "inactive");
        user.setCreatedAt(BOUND_AT_FORMAT.format(LocalDateTime.now()));
        userRepository.save(user);
        replaceWarehouseScopes(tenantId, user.getId(), payload.warehouseIds());
        return toStaffDto(user);
    }

    @Transactional
    public Map<String, Object> updateStaff(Long staffId, StaffPayload payload) {
        Long tenantId = requireManageStaffTenantId();
        AppUser user = requireStaff(tenantId, staffId);
        validateStaffPayload(payload, false);

        if (payload.account() != null) {
            String account = normalizeAccount(payload.account());
            validateAccountAvailable(account, staffId);
            user.setUsername(account);
        }
        if (payload.name() != null) user.setNickname(trim(payload.name()));
        user.setJobTitle(WAREHOUSE_JOB_TITLE);
        if (payload.phone() != null) user.setPhone(trim(payload.phone()));
        if (payload.password() != null && !payload.password().isBlank()) {
            user.setPassword(passwordService.encode(payload.password()));
        }
        if (payload.status() != null) {
            user.setStatus(payload.status() ? "active" : "inactive");
        }
        userRepository.save(user);
        if (payload.warehouseIds() != null) {
            replaceWarehouseScopes(tenantId, user.getId(), payload.warehouseIds());
        }
        return toStaffDto(user);
    }

    @Transactional
    public void deleteStaff(Long staffId) {
        Long tenantId = requireManageStaffTenantId();
        AppUser user = requireStaff(tenantId, staffId);
        warehouseScopeRepository.deleteByTenantIdAndUserId(tenantId, staffId);
        userRepository.delete(user);
    }

    @Transactional
    public Map<String, Object> updateStatus(Long staffId, boolean active) {
        Long tenantId = requireManageStaffTenantId();
        AppUser user = requireStaff(tenantId, staffId);
        user.setStatus(active ? "active" : "inactive");
        userRepository.save(user);
        return toStaffDto(user);
    }

    private Map<String, Object> toStaffDto(AppUser user) {
        Long tenantId = user.getTenantId();
        List<String> warehouseIds = warehouseScopeRepository.findByTenantIdAndUserId(tenantId, user.getId()).stream()
                .map(UserWarehouseScope::getWarehouseId)
                .toList();
        Map<String, String> nameMap = warehouseSiteRepository.findByTenantIdOrderBySortOrderAscNameAsc(tenantId).stream()
                .collect(Collectors.toMap(WarehouseSite::getId, WarehouseSite::getName, (a, b) -> a, LinkedHashMap::new));

        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", user.getId());
        item.put("name", user.getNickname());
        item.put("account", user.getUsername());
        item.put("role", user.getJobTitle());
        item.put("phone", user.getPhone() == null ? "" : user.getPhone());
        item.put("status", user.isActive());
        item.put("boundAt", user.getCreatedAt() == null ? "" : user.getCreatedAt());
        item.put("warehouseIds", warehouseIds);
        item.put("warehouseNames", warehouseIds.stream().map(id -> nameMap.getOrDefault(id, id)).toList());
        return item;
    }

    private void replaceWarehouseScopes(Long tenantId, Long userId, List<String> warehouseIds) {
        warehouseScopeRepository.deleteByTenantIdAndUserId(tenantId, userId);
        if (warehouseIds == null || warehouseIds.isEmpty()) {
            return;
        }

        Set<String> unique = new LinkedHashSet<>();
        for (String warehouseId : warehouseIds) {
            String value = trim(warehouseId);
            if (value.isBlank() || !unique.add(value)) {
                continue;
            }
            warehouseSiteRepository.findByIdAndTenantId(value, tenantId)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "仓库不存在: " + value));

            UserWarehouseScope scope = new UserWarehouseScope();
            scope.setTenantId(tenantId);
            scope.setUserId(userId);
            scope.setWarehouseId(value);
            warehouseScopeRepository.save(scope);
        }
    }

    private AppUser requireStaff(Long tenantId, Long staffId) {
        AppUser user = userRepository.findByIdAndTenantId(staffId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "仓库人员不存在"));
        if (!user.isWarehouse()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "该账号不是仓库人员");
        }
        return user;
    }

    private Long requireManageStaffTenantId() {
        Long tenantId = authContext.tenantId();
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        if (authContext.isBossPortal() && authContext.isAdmin()) {
            return tenantId;
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员可管理仓库人员");
    }

    private void validateStaffPayload(StaffPayload payload, boolean creating) {
        if (creating || payload.name() != null) {
            if (trim(payload.name()).isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请填写员工姓名");
            }
        }
    }

    private void validateAccountAvailable(String account, Long excludeId) {
        boolean exists = excludeId == null
                ? userRepository.existsByUsernameIgnoreCase(account)
                : userRepository.existsByUsernameIgnoreCaseAndIdNot(account, excludeId);
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
