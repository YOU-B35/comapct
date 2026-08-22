<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed } from 'vue'
import { ChatDotRound, WarningFilled } from '@element-plus/icons-vue'
import { TASK_PLATFORM_OPTIONS, PLATFORM_LABELS } from '@/constants/assignedTasks'
import {
  buildAssignedTaskDetail,
  priorityMeta,
  statusMeta,
} from '@/utils/assignedTaskFlow'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  task: { type: Object, default: null },
  feedbacks: { type: Array, default: () => [] },
  viewerRole: { type: String, default: 'boss' },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const detail = computed(() => buildAssignedTaskDetail(props.task, props.feedbacks))

const platformLabel = computed(() => {
  const key = props.task?.platformKey
  return PLATFORM_LABELS[key] || TASK_PLATFORM_OPTIONS.find((item) => item.value === key)?.label || key || '—'
})

const priority = computed(() => priorityMeta(props.task?.priority))
const status = computed(() => statusMeta(props.task?.status))
const isEmployeeView = computed(() => props.viewerRole === 'employee')

const displayTimeline = computed(() =>
  detail.value.timeline.map((item) => ({
    ...item,
    title: isEmployeeView.value && item.type === 'feedback'
      ? item.title.replace('员工反馈', '我的反馈')
      : item.title,
  })),
)
</script>

<template>
  <el-drawer
    v-model="visible"
    :title="task ? `任务详情 · ${task.title}` : '任务详情'"
    size="560px"
  >
    <template v-if="task">
      <div class="detail-head">
        <el-tag :type="status.type" effect="light">{{ task.status }}</el-tag>
        <el-tag :type="priority.type" size="small" effect="plain">{{ priority.label }}优先级</el-tag>
        <el-tag v-if="detail.needsAttention" type="warning" size="small" effect="dark" :icon="WarningFilled">
          需管理员关注
        </el-tag>
      </div>

      <el-alert
        v-if="detail.needsAttention && detail.latestFeedback"
        type="warning"
        :closable="false"
        show-icon
        class="attention-alert"
        :title="isEmployeeView ? '反馈需协助' : '员工反馈需协助'"
        :description="detail.latestFeedback.feedback"
      />

      <h4 class="section-title">处理进度</h4>
      <el-steps :active="detail.flowActive" finish-status="success" align-center class="flow-steps">
        <el-step
          v-for="step in detail.flowSteps"
          :key="step.key"
          :title="step.title"
          :description="step.description"
        />
      </el-steps>

      <h4 class="section-title">任务信息</h4>
      <el-descriptions :column="1" border class="detail-block">
        <el-descriptions-item label="负责人类型">
          {{ task.assigneeType === 'warehouse' ? '仓库管理员' : '运营人员' }}
        </el-descriptions-item>
        <el-descriptions-item label="负责人">{{ task.assignee }}</el-descriptions-item>
        <el-descriptions-item :label="task.assigneeType === 'warehouse' ? '关联仓库' : '关联平台'">
          {{ task.assigneeType === 'warehouse' ? (task.warehouseName || platformLabel) : platformLabel }}
        </el-descriptions-item>
        <el-descriptions-item label="任务类型">{{ task.category || '—' }}</el-descriptions-item>
        <el-descriptions-item label="截止时间">{{ task.due || '—' }}</el-descriptions-item>
        <el-descriptions-item label="分配人">{{ task.assignedBy || '企业管理员' }}</el-descriptions-item>
        <el-descriptions-item label="分配时间">{{ formatUtc8(task.assignedAt) }}</el-descriptions-item>
        <el-descriptions-item label="最近更新">{{ formatUtc8(task.updatedAt) }}</el-descriptions-item>
      </el-descriptions>

      <div v-if="task.description" class="desc-block">
        <h4 class="section-title">任务说明</h4>
        <p>{{ task.description }}</p>
      </div>

      <h4 class="section-title">
        反馈记录
        <el-tag v-if="detail.summary.feedbackCount" size="small" type="info" effect="plain">
          {{ detail.summary.feedbackCount }} 条
        </el-tag>
      </h4>

      <el-empty
        v-if="!detail.timeline.filter((item) => item.type === 'feedback').length"
        :description="isEmployeeView ? '你尚未提交反馈' : '员工尚未提交反馈'"
        :image-size="72"
      />

      <el-timeline v-else class="feedback-timeline">
        <el-timeline-item
          v-for="item in displayTimeline"
          :key="item.id"
          :timestamp="item.time"
          :type="item.type === 'feedback' ? (item.tag?.type === 'danger' ? 'danger' : item.tag?.type === 'warning' ? 'warning' : item.tag?.type === 'success' ? 'success' : 'primary') : 'info'"
          placement="top"
        >
          <div class="timeline-card">
            <div class="timeline-card__head">
              <strong>{{ item.title }}</strong>
              <el-tag v-if="item.tag" size="small" :type="item.tag.type" effect="plain">
                {{ item.tag.label }}
              </el-tag>
            </div>
            <p v-if="item.content" class="timeline-card__content">{{ item.content }}</p>
            <span v-if="item.actor" class="timeline-card__actor">
              <el-icon><ChatDotRound /></el-icon>
              {{ item.actor }}
            </span>
          </div>
        </el-timeline-item>
      </el-timeline>
    </template>
  </el-drawer>
</template>

<style scoped>
.detail-head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.attention-alert {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 20px 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ch-text);
}

.flow-steps {
  margin-bottom: 8px;
}

.detail-block {
  margin-bottom: 4px;
}

.desc-block p {
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--ch-radius-md);
  background: var(--ch-surface-muted);
  font-size: 13px;
  line-height: 1.6;
  color: var(--ch-text-secondary);
}

.feedback-timeline {
  padding-left: 4px;
}

.timeline-card {
  padding: 2px 0 4px;
}

.timeline-card__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}

.timeline-card__head strong {
  font-size: 13px;
  color: var(--ch-text);
}

.timeline-card__content {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--ch-text-secondary);
}

.timeline-card__actor {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--ch-text-muted);
}
</style>
