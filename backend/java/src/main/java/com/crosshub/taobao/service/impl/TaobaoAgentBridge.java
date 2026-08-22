package com.crosshub.taobao.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.service.impl.AgentServiceImpl;
import com.crosshub.taobao.service.TaobaoAgentTasks;
import com.crosshub.taobao.service.TaobaoOpsService;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 淘宝/天猫 Agent 任务回调桥接。对齐抖音 {@code DouyinAgentBridge} / 拼多多 {@code PddAgentBridge}：
 * Agent 任务 started/completed 时回写 sync job 状态与会话快照。
 */
@Component
public class TaobaoAgentBridge implements AgentServiceImpl.TaobaoBridge {
    private final TaobaoOpsService taobaoOpsService;

    public TaobaoAgentBridge(TaobaoOpsService taobaoOpsService) {
        this.taobaoOpsService = taobaoOpsService;
    }

    @Override
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null || !TaobaoAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        taobaoOpsService.onAgentTaskStarted(task);
    }

    @Override
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !TaobaoAgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        taobaoOpsService.onAgentTaskCompleted(task, status, result, errorCode, errorMessage);
    }
}
