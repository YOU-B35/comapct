package com.crosshub.security;

import com.crosshub.auth.entity.AppUser;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Set;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class JwtService {
    private static final Set<String> FORBIDDEN_SECRETS = Set.of(
            "crosshub-dev-secret-change-in-production",
            "crosshub-prod-secret-change-me",
            "crosshub-prod-jwt-secret-must-be-at-least-32-bytes"
    );

    private final SecretKey key;
    private final long ttlSeconds = 86400;

    public JwtService(@Value("${crosshub.jwt-secret}") String secret) {
        String value = secret == null ? "" : secret.trim();
        if (value.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("crosshub.jwt-secret must be at least 32 bytes");
        }
        if (FORBIDDEN_SECRETS.contains(value)) {
            throw new IllegalStateException("crosshub.jwt-secret is a public placeholder and must be replaced");
        }
        this.key = Keys.hmacShaKeyFor(value.getBytes(StandardCharsets.UTF_8));
    }

    public String createToken(
            AppUser user,
            String portalRole,
            List<String> platforms,
            List<String> shopScope,
            List<String> warehouseScope
    ) {
        Instant now = Instant.now();
        Map<String, Object> claims = new HashMap<>();
        claims.put("uid", user.getId());
        claims.put("tid", user.getTenantId());
        claims.put("role", user.getRole());
        claims.put("portal_role", portalRole);
        claims.put("username", user.getUsername());
        claims.put("platforms", platforms == null ? List.of() : platforms);
        claims.put("shop_scope", shopScope == null ? List.of() : shopScope);
        claims.put("warehouse_scope", warehouseScope == null ? List.of() : warehouseScope);

        return Jwts.builder()
                .claims(claims)
                .subject(user.getUsername())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(ttlSeconds)))
                .signWith(key)
                .compact();
    }

    public Claims parse(String token) {
        return Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
