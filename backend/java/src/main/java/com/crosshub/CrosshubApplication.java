package com.crosshub;

import com.crosshub.config.AgentProfileProperties;
import com.crosshub.config.AgentProperties;
import com.crosshub.config.CrawlerProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableConfigurationProperties({CrawlerProperties.class, AgentProperties.class, AgentProfileProperties.class})
@EnableScheduling
public class CrosshubApplication {
    public static void main(String[] args) {
        SpringApplication.run(CrosshubApplication.class, args);
    }
}
