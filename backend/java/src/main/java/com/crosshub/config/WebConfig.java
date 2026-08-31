package com.crosshub.config;

import com.crosshub.security.AgentAuthInterceptor;
import com.crosshub.security.JwtAuthInterceptor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;

@Configuration
public class WebConfig implements WebMvcConfigurer {
    private final JwtAuthInterceptor jwtAuthInterceptor;
    private final AgentAuthInterceptor agentAuthInterceptor;
    private final String[] allowedOriginPatterns;

    public WebConfig(
            JwtAuthInterceptor jwtAuthInterceptor,
            AgentAuthInterceptor agentAuthInterceptor,
            @Value("${crosshub.cors.allowed-origin-patterns:http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174}") String allowedOriginPatterns
    ) {
        this.jwtAuthInterceptor = jwtAuthInterceptor;
        this.agentAuthInterceptor = agentAuthInterceptor;
        this.allowedOriginPatterns = parseCsv(allowedOriginPatterns);
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOriginPatterns(allowedOriginPatterns)
                .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                .allowedHeaders("Authorization", "Content-Type", "X-Agent-Token", "X-Requested-With", "Accept", "Origin");
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(jwtAuthInterceptor)
                .addPathPatterns(
                        "/api/temu/**",
                        "/api/auth/menus",
                        "/api/auth/session",
                        "/api/tenant/**",
                        "/api/warehouse/**",
                        "/api/platform-accounts/**",
                        "/api/platform/**",
                        "/api/tasks/**",
                        "/api/ops-feedback/**",
                        "/api/agent/register",
                        "/api/agent/setup",
                        "/api/agent/nodes",
                        "/api/agent/me",
                        "/api/agent/me/**",
                        "/api/amazon/**",
                        "/api/aliexpress/**",
                        "/api/douyin/**",
                        "/api/1688/**",
                        "/api/pdd/**",
                        "/api/taobao/**",
                        "/api/sync-logs",
                        "/api/monitor/**",
                        "/api/sau/**",
                        "/api/commander/**"
                );
        registry.addInterceptor(agentAuthInterceptor)
                .addPathPatterns(
                        "/api/agent/heartbeat",
                        "/api/agent/tasks",
                        "/api/agent/tasks/**",
                        "/api/agent/temu/**",
                        "/api/agent/aliexpress/**",
                        "/api/agent/douyin/**",
                        "/api/agent/1688/**",
                        "/api/agent/pdd/**",
                        "/api/agent/taobao/**",
                        "/api/agent/tenants",
                        "/api/agent/platform-accounts",
                        "/api/agent/platform-accounts/**",
                        "/api/agent/amazon/**",
                        "/api/agent/ops/**",
                        "/api/agent/profiles",
                        "/api/agent/profiles/**"
                );
    }

    private static String[] parseCsv(String raw) {
        String[] values = Arrays.stream((raw == null ? "" : raw).split(","))
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .toArray(String[]::new);
        if (values.length == 0) {
            throw new IllegalStateException("crosshub.cors.allowed-origin-patterns must not be empty");
        }
        return values;
    }
}
