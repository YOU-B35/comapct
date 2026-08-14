package com.crosshub.douyin.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.service.impl.AgentServiceImpl;
import com.crosshub.douyin.service.DouyinAgentTasks;
import com.crosshub.douyin.service.DouyinOpsService;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class DouyinAgentBridge implements AgentServiceImpl.DouyinBridge {
    private final DouyinOpsService douyinOpsService;

    public DouyinAgentBridge(DouyinOpsService douyinOpsService) {
        this.douyinOpsService = douyinOpsService;
    }

    @Override
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null || !DouyinAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        douyinOpsService.onAgentTaskStarted(task);
    }

    @Override
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !DouyinAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        douyinOpsService.onAgentTaskCompleted(task, status, result, errorCode, errorMessage);
    }
}
