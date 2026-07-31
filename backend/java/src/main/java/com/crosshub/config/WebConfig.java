package com.crosshub.config;

import com.crosshub.security.AgentAuthInterceptor;
import com.crosshub.security.JwtAuthInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {
    private final JwtAuthInterceptor jwtAuthInterceptor;
    private final AgentAuthInterceptor agentAuthInterceptor;

    public WebConfig(JwtAuthInterceptor jwtAuthInterceptor, AgentAuthInterceptor agentAuthInterceptor) {
        this.jwtAuthInterceptor = jwtAuthInterceptor;
        this.agentAuthInterceptor = agentAuthInterceptor;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOriginPatterns("*")
                .allowedMethods("*")
                .allowedHeaders("*");
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
                        "/api/amazon/**",
                        "/api/aliexpress/**",
                        "/api/monitor/**"
                );
        registry.addInterceptor(agentAuthInterceptor)
                .addPathPatterns(
                        "/api/agent/heartbeat",
                        "/api/agent/tasks",
                        "/api/agent/tasks/**",
                        "/api/agent/temu/**",
                        "/api/agent/tenants",
                        "/api/agent/platform-accounts",
                        "/api/agent/platform-accounts/**",
                        "/api/agent/amazon/**",
                        "/api/agent/profiles",
                        "/api/agent/profiles/**"
                );
    }
}
