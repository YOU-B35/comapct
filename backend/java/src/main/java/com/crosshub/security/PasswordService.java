package com.crosshub.security;

import com.crosshub.auth.entity.AppUser;
import com.crosshub.auth.repository.AppUserRepository;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class PasswordService {
    private final PasswordEncoder encoder = new BCryptPasswordEncoder(12);

    public String encode(String rawPassword) {
        return encoder.encode(rawPassword == null ? "" : rawPassword);
    }

    public boolean matches(String rawPassword, String storedPassword) {
        String stored = storedPassword == null ? "" : storedPassword;
        String raw = rawPassword == null ? "" : rawPassword;
        if (isHashed(stored)) {
            return encoder.matches(raw, stored);
        }
        return raw.equals(stored);
    }

    public boolean isHashed(String storedPassword) {
        return storedPassword != null
                && (storedPassword.startsWith("$2a$")
                || storedPassword.startsWith("$2b$")
                || storedPassword.startsWith("$2y$"));
    }

    public void upgradeIfLegacy(AppUser user, String rawPassword, AppUserRepository repository) {
        if (user != null && !isHashed(user.getPassword())) {
            user.setPassword(encode(rawPassword));
            repository.save(user);
        }
    }
}
