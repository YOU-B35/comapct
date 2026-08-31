package com.crosshub.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SecretValueServiceTest {
    private final SecretValueService secretValueService =
            new SecretValueService("test-data-secret-that-is-long-enough");

    @Test
    void encryptsAndDecryptsSecretValues() {
        String encrypted = secretValueService.encrypt("store-password");

        assertTrue(secretValueService.isEncrypted(encrypted));
        assertNotEquals("store-password", encrypted);
        assertEquals("store-password", secretValueService.decrypt(encrypted));
    }

    @Test
    void leavesLegacyPlaintextReadable() {
        assertEquals("legacy-store-password", secretValueService.decrypt("legacy-store-password"));
    }
}
