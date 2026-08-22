package com.crosshub.pdd.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.service.impl.AgentServiceImpl;
import com.crosshub.pdd.service.PddAgentTasks;
import com.crosshub.pdd.service.PddOpsService;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 拼多多 Agent 任务回调桥接。对齐抖音 {@code DouyinAgentBridge}：
 * Agent 任务 started/completed 时回写 sync job 状态与会话快照。
 */
@Component
public class PddAgentBridge implements AgentServiceImpl.PddBridge {
    private final PddOpsService pddOpsService;

    public PddAgentBridge(PddOpsService pddOpsService) {
        this.pddOpsService = pddOpsService;
    }

    @Override
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null || !PddAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        pddOpsService.onAgentTaskStarted(task);
    }

    @Override
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !PddAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        pddOpsService.onAgentTaskCompleted(task, status, result, errorCode, errorMessage);
    }
}
