package com.crosshub.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PasswordServiceTest {
    private final PasswordService passwordService = new PasswordService();

    @Test
    void hashesAndVerifiesPasswords() {
        String hash = passwordService.encode("Passw0rd!");

        assertTrue(passwordService.isHashed(hash));
        assertTrue(passwordService.matches("Passw0rd!", hash));
        assertFalse(passwordService.matches("wrong", hash));
    }

    @Test
    void stillMatchesLegacyPlaintextPasswords() {
        assertTrue(passwordService.matches("legacy-secret", "legacy-secret"));
        assertFalse(passwordService.matches("wrong", "legacy-secret"));
    }
}
