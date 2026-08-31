package com.crosshub.auth.controller;

import com.crosshub.auth.PortalPer;
import com.crosshub.auth.entity.AppUser;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.security.AuthContext;
import com.crosshub.security.JwtService;
import com.crosshub.security.PasswordService;
import com.crosshub.tenant.service.DataScopeService;
import com.crosshub.tenant.service.MenuService;
import com.crosshub.tenant.service.TenantRegistrationService;
import org.springframework.http.HttpStatus;
import com.crosshub.auth.dto.LoginRequest;
import com.crosshub.auth.dto.RegisterRequest;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AppUserRepository userRepository;
    private final JwtService jwtService;
    private final MenuService menuService;
    private final DataScopeService dataScopeService;
    private final TenantRegistrationService tenantRegistrationService;
    private final AuthContext authContext;
    private final PasswordService passwordService;

    public AuthController(
            AppUserRepository userRepository,
            JwtService jwtService,
            MenuService menuService,
            DataScopeService dataScopeService,
            TenantRegistrationService tenantRegistrationService,
            AuthContext authContext,
            PasswordService passwordService
    ) {
        this.userRepository = userRepository;
        this.jwtService = jwtService;
        this.menuService = menuService;
        this.dataScopeService = dataScopeService;
        this.tenantRegistrationService = tenantRegistrationService;
        this.authContext = authContext;
        this.passwordService = passwordService;
    }

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody RegisterRequest request) {
        return Map.of(
                "code", 0,
                "data", tenantRegistrationService.registerCompany(
                        request.company(),
                        request.account(),
                        request.password()
                )
        );
    }

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody LoginRequest request) {
        String account = request.account() == null ? "" : request.account().trim();
        String password = request.password() == null ? "" : request.password();
        // preferred portal（登录页选项卡）仅提示；实际入口由账号 per 决定
        String preferredPortal = request.portalRole();

        Optional<AppUser> userOpt = resolveLoginUser(account, password);
        if (userOpt.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "账号或密码错误");
        }

        AppUser user = userOpt.get();
        passwordService.upgradeIfLegacy(user, password, userRepository);
        if (user.getTenantId() == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "账号未绑定租户");
        }
        if (!user.isActive()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "账号已停用");
        }

        String per = user.getPer();
        String portalRole = PortalPer.resolvePortal(per, preferredPortal);
        String landingPath = PortalPer.landingPathFromPer(per);

        boolean bossPortal = "boss".equalsIgnoreCase(portalRole);
        List<String> platforms = dataScopeService.resolvePlatformsForLogin(user.getTenantId(), user.getId(), bossPortal);
        List<String> shopScope = dataScopeService.resolveScopeForLogin(user.getTenantId(), user.getId(), bossPortal);
        List<String> warehouseScope = dataScopeService.resolveWarehouseScopeForLogin(
                user.getTenantId(), user.getId(), portalRole
        );
        List<String> warehouseScopeNames = dataScopeService.resolveWarehouseScopeNamesForLogin(
                user.getTenantId(), user.getId(), portalRole
        );
        String token = jwtService.createToken(user, portalRole, platforms, shopScope, warehouseScope);
        List<Map<String, Object>> menus = menuService.menusForUser(user, portalRole);

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("token", token);
        data.put("per", per);
        data.put("portal_role", portalRole);
        data.put("landing_path", landingPath);
        data.put("role", user.getRole());
        data.put("tenant_id", user.getTenantId());
        data.put("user_id", user.getId());
        data.put("account", user.getUsername());
        data.put("company", user.getEnterprise());
        data.put("nickname", user.getNickname());
        data.put("job_title", user.getJobTitle());
        data.put("platforms", platforms);
        data.put("shop_scope", shopScope);
        data.put("warehouse_scope", warehouseScope);
        data.put("warehouse_scope_names", warehouseScopeNames);
        data.put("menus", menus);

        return Map.of("code", 0, "data", data);
    }

    @GetMapping("/menus")
    public Map<String, Object> menus() {
        Long userId = authContext.userId();
        Long tenantId = authContext.tenantId();
        String portalRole = authContext.portalRole();
        if (userId == null || tenantId == null || portalRole == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }

        AppUser user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "用户不存在"));
        if (!tenantId.equals(user.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "租户不匹配");
        }

        return Map.of(
                "code", 0,
                "data", menuService.menusForUser(user, portalRole)
        );
    }

    @GetMapping("/session")
    public Map<String, Object> session() {
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        AppUser user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "用户不存在"));

        String portalRole = authContext.portalRole();
        String per = user.getPer();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("tenant_id", authContext.tenantId());
        data.put("user_id", userId);
        data.put("per", per);
        data.put("portal_role", portalRole);
        data.put("landing_path", PortalPer.landingPathFromPer(per));
        data.put("role", user.getRole());
        data.put("account", user.getUsername());
        data.put("company", user.getEnterprise());
        data.put("nickname", user.getNickname());
        data.put("platforms", authContext.platforms());
        data.put("shop_scope", authContext.shopScope());
        data.put("warehouse_scope", authContext.warehouseScope());
        data.put("warehouse_scope_names", dataScopeService.resolveWarehouseScopeNamesForLogin(
                authContext.tenantId(), userId, portalRole
        ));
        data.put("menus", menuService.menusForUser(user, portalRole));
        return Map.of("code", 0, "data", data);
    }

    private Optional<AppUser> resolveLoginUser(String account, String password) {
        List<AppUser> candidates = userRepository.findAllByUsernameIgnoreCase(account).stream()
                .filter(user -> passwordService.matches(password, user.getPassword()))
                .toList();
        if (candidates.isEmpty()) {
            return Optional.empty();
        }
        if (candidates.size() > 1) {
            throw new ResponseStatusException(
                    HttpStatus.FORBIDDEN,
                    "该账号绑定多个企业，请使用企业专用账号登录"
            );
        }
        return Optional.of(candidates.get(0));
    }
}
