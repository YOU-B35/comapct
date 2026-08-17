package com.crosshub.alibaba1688.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.service.impl.AgentServiceImpl;
import com.crosshub.alibaba1688.service.Alibaba1688AgentTasks;
import com.crosshub.alibaba1688.service.Alibaba1688SessionService;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class Alibaba1688AgentBridge implements AgentServiceImpl.Alibaba1688Bridge {
    private final Alibaba1688SessionService sessionService;

    public Alibaba1688AgentBridge(Alibaba1688SessionService sessionService) {
        this.sessionService = sessionService;
    }

    @Override
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null || !Alibaba1688AgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        sessionService.onAgentTaskStarted(task);
    }

    @Override
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !Alibaba1688AgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        sessionService.onAgentTaskCompleted(task, status, result, errorCode, errorMessage);
    }
}
