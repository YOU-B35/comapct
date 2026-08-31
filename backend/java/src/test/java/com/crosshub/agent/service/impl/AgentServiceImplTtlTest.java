package com.crosshub.agent.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.repository.AgentTaskRepository;
import com.crosshub.agent.repository.IntegrationAgentRepository;
import com.crosshub.config.AgentProperties;
import com.crosshub.security.AgentContext;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.mock;

class AgentServiceImplTtlTest {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    @Test
    void runningAmazonAgentTaskStartedTwentyMinutesAgoIsNotStale() {
        AgentServiceImpl service = new AgentServiceImpl(
                mock(IntegrationAgentRepository.class),
                mock(AgentTaskRepository.class),
                new AuthContext(),
                new AgentContext(),
                mock(DataScopeService.class),
                new ObjectMapper(),
                mock(TransactionTemplate.class),
                new AgentProperties(),
                null,
                null,
                null,
                null,
                null,
                null,
                null
        );

        AgentTask task = new AgentTask();
        task.setTaskType("amazon_sync");
        task.setStartedAt(LocalDateTime.now().minusMinutes(20).format(TS));

        assertFalse(service.isStaleAgentTask(task));
    }
}
