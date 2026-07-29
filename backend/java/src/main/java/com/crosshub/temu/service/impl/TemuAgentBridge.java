package com.crosshub.temu.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.service.impl.AgentServiceImpl;
import com.crosshub.temu.service.TemuAgentService;
import com.crosshub.temu.service.TemuAgentTasks;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class TemuAgentBridge implements AgentServiceImpl.TemuBridge {
    private final TemuAgentService temuAgentService;

    public TemuAgentBridge(TemuAgentService temuAgentService) {
        this.temuAgentService = temuAgentService;
    }

    @Override
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null || !TemuAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        temuAgentService.onAgentTaskStarted(task);
    }

    @Override
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !TemuAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        temuAgentService.onAgentTaskCompleted(task, status, result, errorCode, errorMessage);
    }
}
