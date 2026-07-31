package com.crosshub.config;

import jakarta.annotation.PostConstruct;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

@ConfigurationProperties(prefix = "crosshub.agent.profiles")
public class AgentProfileProperties {
    private boolean enabled = true;
    private String root = "/data/agent-profiles";
    private long maxBytes = 10_485_760L;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getRoot() {
        return root;
    }

    public void setRoot(String root) {
        this.root = root == null || root.isBlank() ? "/data/agent-profiles" : root.trim();
    }

    public long getMaxBytes() {
        return maxBytes;
    }

    public void setMaxBytes(long maxBytes) {
        this.maxBytes = maxBytes > 0 ? maxBytes : 10_485_760L;
    }

    public Path rootPath() {
        return Path.of(getRoot()).toAbsolutePath().normalize();
    }

    @PostConstruct
    void ensureRoot() throws IOException {
        if (!enabled) {
            return;
        }
        Files.createDirectories(rootPath());
    }
}
