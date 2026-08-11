package com.crosshub.auth.repository;

import com.crosshub.auth.entity.AppUser;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface AppUserRepository extends JpaRepository<AppUser, Long> {
    Optional<AppUser> findByUsernameIgnoreCase(String username);

    List<AppUser> findAllByUsernameIgnoreCase(String username);

    Optional<AppUser> findByTenantIdAndUsernameIgnoreCase(Long tenantId, String username);

    List<AppUser> findByTenantIdOrderByIdAsc(Long tenantId);

    List<AppUser> findByTenantIdAndRoleOrderByIdAsc(Long tenantId, String role);

    Optional<AppUser> findByIdAndTenantId(Long id, Long tenantId);

    boolean existsByUsernameIgnoreCase(String username);

    boolean existsByTenantIdAndUsernameIgnoreCase(Long tenantId, String username);

    boolean existsByUsernameIgnoreCaseAndIdNot(String username, Long id);

    boolean existsByTenantIdAndUsernameIgnoreCaseAndIdNot(Long tenantId, String username, Long id);
}
