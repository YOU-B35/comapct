package com.crosshub.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtServiceTest {
    @Test
    void rejectsShortSecrets() {
        assertThrows(IllegalStateException.class, () -> new JwtService("too-short"));
    }

    @Test
    void rejectsPublicPlaceholderSecrets() {
        assertThrows(
                IllegalStateException.class,
                () -> new JwtService("crosshub-prod-secret-change-me")
        );
    }
}
