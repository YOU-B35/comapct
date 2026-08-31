package com.crosshub.tenant.service.impl;

import com.crosshub.tenant.service.TenantRegistrationService;

import com.crosshub.auth.entity.AppUser;
import com.crosshub.tenant.entity.Tenant;
import com.crosshub.tenant.entity.TenantFeature;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.security.PasswordService;
import com.crosshub.tenant.repository.SysMenuRepository;
import com.crosshub.tenant.repository.TenantFeatureRepository;
import com.crosshub.tenant.repository.TenantRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Service
public class TenantRegistrationServiceImpl implements TenantRegistrationService {
    private static final DateTimeFormatter CREATED_AT_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final TenantRepository tenantRepository;
    private final AppUserRepository userRepository;
    private final SysMenuRepository menuRepository;
    private final TenantFeatureRepository featureRepository;
    private final PasswordService passwordService;

    public TenantRegistrationServiceImpl(
            TenantRepository tenantRepository,
            AppUserRepository userRepository,
            SysMenuRepository menuRepository,
            TenantFeatureRepository featureRepository,
            PasswordService passwordService
    ) {
        this.tenantRepository = tenantRepository;
        this.userRepository = userRepository;
        this.menuRepository = menuRepository;
        this.featureRepository = featureRepository;
        this.passwordService = passwordService;
    }

    @Transactional
    public Map<String, Object> registerCompany(String companyName, String account, String password) {
        String company = trim(companyName);
        String username = trim(account);
        String pwd = password == null ? "" : password;

        if (company.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请填写企业名称");
        }
        if (username.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请填写登录账号");
        }
        if (pwd.length() < 6) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "密码至少 6 位");
        }

        Tenant tenant = new Tenant();
        tenant.setName(company);
        tenant.setCode(generateTenantCode(company));
        tenant.setStatus("active");
        tenant = tenantRepository.save(tenant);

        AppUser admin = new AppUser();
        admin.setTenantId(tenant.getId());
        admin.setUsername(username);
        admin.setPassword(passwordService.encode(pwd));
        admin.setNickname(company);
        admin.setEnterprise(company);
        admin.setJobTitle("企业管理员");
        admin.setRole("admin");
        admin.setPhone("");
        admin.setStatus("active");
        admin.setCreatedAt(CREATED_AT_FORMAT.format(LocalDateTime.now()));
        admin = userRepository.save(admin);

        seedTenantFeatures(tenant.getId());

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("tenant_id", tenant.getId());
        data.put("tenant_code", tenant.getCode());
        data.put("user_id", admin.getId());
        data.put("company", company);
        data.put("account", admin.getUsername());
        return data;
    }

    private void seedTenantFeatures(Long tenantId) {
        menuRepository.findAll().forEach(menu -> {
            TenantFeature feature = new TenantFeature();
            feature.setTenantId(tenantId);
            feature.setFeatureCode(menu.getCode());
            feature.setEnabled(true);
            featureRepository.save(feature);
        });
    }

    private String generateTenantCode(String companyName) {
        String base = companyName.toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9]+", "-")
                .replaceAll("^-+|-+$", "");
        if (base.isBlank()) {
            return "org-" + UUID.randomUUID().toString().substring(0, 8);
        }
        if (base.length() > 40) {
            base = base.substring(0, 40);
        }

        String code = base;
        int suffix = 1;
        while (tenantRepository.findByCode(code).isPresent()) {
            code = base + "-" + suffix++;
        }
        if (tenantRepository.findByCode(code).isPresent()) {
            code = "org-" + UUID.randomUUID().toString().substring(0, 8);
        }
        return code;
    }

    private String trim(String value) {
        return value == null ? "" : value.trim();
    }
}
