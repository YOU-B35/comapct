<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Right, View, WarningFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { loadOperationsOverview } from '@/api/operationsOverview'
import { submitTaskFeedback } from '@/api/opsFeedback'
import { syncAssignedTaskFeedback, fetchAssignedTaskDetail } from '@/api/assignedTasks'
import { calcTaskStats } from '@/utils/operations'
import { groupEmployeeTasksByPlatform } from '@/utils/employeeTasks'
import { TASK_STATUS_META } from '@/constants/operations'
import { OUTCOME_MAP } from '@/constants/opsFeedbackDemo'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import AssignedTaskDetailDrawer from '@/components/tasks/AssignedTaskDetailDrawer.vue'
import EmployeeTaskDetailDrawer from '@/components/tasks/EmployeeTaskDetailDrawer.vue'
import TaskFeedbackDialog from '@/components/tasks/TaskFeedbackDialog.vue'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const tasks = ref([])
const activeFilter = ref('all')
const feedbackVisible = ref(false)
const feedbackSubmitting = ref(false)
const activeTask = ref(null)
const detailVisible = ref(false)
const detailTask = ref(null)
const detailFeedbacks = ref([])
const opsDetailVisible = ref(false)
const opsDetailTask = ref(null)
const feedbackForm = reactive({
  outcome: 'resolved',
  feedback: '',
})

const priorityMap = {
  high: { label: '高', type: 'danger' },
  medium: { label: '中', type: 'warning' },
  low: { label: '低', type: 'info' },
}

const sourceMap = {
  issue: { label: '运营预警', type: 'danger' },
  plan: { label: '计划任务', type: 'info' },
}

const assignedTasks = computed(() => tasks.value.filter((task) => task.source === 'assigned'))
const operationalTasks = computed(() => tasks.value.filter((task) => task.source !== 'assigned'))
const platformGroups = computed(() => groupEmployeeTasksByPlatform(operationalTasks.value))

const stats = computed(() => calcTaskStats(tasks.value))
const assignedStats = computed(() => calcTaskStats(assignedTasks.value))
const issueCount = computed(() => tasks.value.filter((t) => t.source === 'issue' && t.status !== '已完成').length)
const assignedPending = computed(() => assignedTasks.value.filter((t) => t.status !== '已完成').length)

const showAssignedSection = computed(() => activeFilter.value === 'all' || activeFilter.value === 'assigned')
const showPlatformSections = computed(() => activeFilter.value !== 'assigned')

const visibleAssignedTasks = computed(() => {
  if (!showAssignedSection.value) return []
  return assignedTasks.value
})

const visibleGroups = computed(() => {
  if (!showPlatformSections.value) return []
  if (activeFilter.value === 'all') return platformGroups.value
  return platformGroups.value.filter((g) => g.platformKey === activeFilter.value)
})

const filterOptions = computed(() => {
  const options = [
    {
      value: 'all',
      label: '全部',
      count: tasks.value.filter((t) => t.status !== '已完成').length,
    },
  ]
  if (assignedTasks.value.length) {
    options.push({
      value: 'assigned',
      label: '管理员分配',
      count: assignedPending.value,
    })
  }
  for (const group of platformGroups.value) {
    options.push({
      value: group.platformKey,
      label: group.platform,
      count: group.pending,
    })
  }
  return options
})

const platformLabels = computed(() => {
  const map = {
    temu: 'Temu',
    aliexpress: 'AliExpress',
    amazon: 'Amazon',
    walmart: 'Walmart',
    pdd: '拼多多',
    taobao: '淘宝',
    douyin: '抖音',
    channels: '视频号',
    '1688': '1688',
    dtc: '独立站',
    shopify: '独立站',
    wordpress: '独立站',
  }
  const labels = (auth.employee.platforms || []).map((p) => map[p] || p)
  return [...new Set(labels)].join(' · ') || '—'
})

const isAssignedFeedback = computed(() => activeTask.value?.source === 'assigned')
const feedbackSourceMeta = computed(() => {
  const source = activeTask.value?.source
  return sourceMap[source] || { label: '任务', type: 'info' }
})

async function loadTasks() {
  loading.value = true
  try {
    const res = await loadOperationsOverview(auth)
    tasks.value = (res.data?.tasks || []).map((t) => ({ ...t }))
  } catch {
    tasks.value = []
  } finally {
    loading.value = false
  }
}

function latestFeedbackLabel(task) {
  if (!task?.lastOutcome) return ''
  return OUTCOME_MAP[task.lastOutcome]?.label || ''
}

function rowNeedsAttention(task) {
  if (!task || task.status === '已完成') return false
  return task.lastOutcome === 'need_help' || task.lastOutcome === 'blocked'
}

function isTaskNudged(task) {
  if (!task || task.status === '已完成' || task.status === '已取消') return false
  return Boolean(String(task.nudgedAt || '').trim())
}

function assignedTableRowClass({ row }) {
  if (isTaskNudged(row)) return 'is-nudged-row'
  if (rowNeedsAttention(row)) return 'is-attention-row'
  return ''
}

function openFeedback(task) {
  activeTask.value = task
  feedbackForm.outcome = task.lastOutcome === 'resolved' ? 'resolved' : 'in_progress'
  feedbackForm.feedback = ''
  feedbackVisible.value = true
}

function openTaskDetail(row) {
  if (row.source === 'assigned') {
    openAssignedDetail(row)
    return
  }
  opsDetailTask.value = row
  opsDetailVisible.value = true
}

async function openAssignedDetail(row) {
  try {
    const res = await fetchAssignedTaskDetail(row.id, auth)
    detailTask.value = res.data.task
    detailFeedbacks.value = res.data.feedbacks
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(err.message || '加载任务详情失败')
  }
}

async function submitFeedback() {
  if (!activeTask.value) return
  if (!feedbackForm.feedback.trim()) {
    ElMessage.warning('请填写处理说明，便于管理员了解进展')
    return
  }

  feedbackSubmitting.value = true
  try {
    await submitTaskFeedback({
      taskId: String(activeTask.value.id),
      employeeId: auth.employee.id,
      employeeName: auth.employee.name,
      employeeRole: auth.employee.role,
      platform: activeTask.value.platform,
      platformKey: activeTask.value.platformKey,
      taskTitle: activeTask.value.title,
      category: activeTask.value.category,
      storeName: activeTask.value.storeName,
      outcome: feedbackForm.outcome,
      feedback: feedbackForm.feedback,
    }, auth)

    if (activeTask.value.source === 'assigned') {
      await syncAssignedTaskFeedback(activeTask.value.id, {
        outcome: feedbackForm.outcome,
        feedback: feedbackForm.feedback,
        assigneeName: auth.employee.name,
      }, auth)
      ElMessage.success('反馈已提交，已同步至管理员任务分配')
    } else {
      ElMessage.success('反馈已提交，将同步至运营总览')
    }

    feedbackVisible.value = false
    feedbackForm.feedback = ''
    await loadTasks()
  } catch (err) {
    ElMessage.error(err.message || '提交失败')
  } finally {
    feedbackSubmitting.value = false
  }
}

function closeFeedbackDialog() {
  activeTask.value = null
}

function goPlatform(route) {
  if (route) router.push(route)
}

onMounted(loadTasks)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="任务中心"
        eyebrow="协作"
        :description="`${auth.employee.name} · ${auth.employee.role} · 负责 ${platformLabels}`"
      >
        <template #actions>
          <el-button :icon="Refresh" :loading="loading" @click="loadTasks">刷新</el-button>
        </template>
      </PageHeader>
    </template>

    <div v-loading="loading" class="task-center">
      <PageSection title="概览">
      <div class="metrics-bar metrics-bar--4">
        <div class="metric-item">
          <div class="metric-value" :class="assignedPending ? 'is-primary' : ''">{{ assignedPending }}</div>
          <div class="metric-label">管理员分配</div>
          <div class="metric-hint">反馈与 Boss 端同步</div>
        </div>
        <div class="metric-item">
          <div class="metric-value" :class="issueCount ? 'is-danger' : ''">{{ issueCount }}</div>
          <div class="metric-label">运营预警</div>
          <div class="metric-hint">来自各平台实时问题</div>
        </div>
        <div class="metric-item">
          <div class="metric-value" :class="stats.pending + stats.inProgress ? 'is-warning' : ''">
            {{ stats.pending + stats.inProgress }}
          </div>
          <div class="metric-label">待完成</div>
          <div class="metric-hint">含分配 / 计划 / 预警</div>
        </div>
        <div class="metric-item">
          <div class="metric-value is-success">{{ assignedStats.completionRate }}<small>%</small></div>
          <div class="metric-label">分配完成率</div>
          <div class="metric-hint">{{ assignedStats.completed }}/{{ assignedStats.total || 0 }} 已完成</div>
        </div>
      </div>
      </PageSection>

      <PageSection title="任务列表">
      <div class="filter-bar">
        <button
          v-for="item in filterOptions"
          :key="item.value"
          type="button"
          class="filter-chip"
          :class="{ 'is-active': activeFilter === item.value }"
          @click="activeFilter = item.value"
        >
          {{ item.label }}
          <span v-if="item.count" class="filter-chip__count">{{ item.count }}</span>
        </button>
      </div>

      <el-empty
        v-if="!loading && !visibleAssignedTasks.length && !visibleGroups.length"
        description="暂无与你相关的任务"
        :image-size="88"
      />

      <section v-if="visibleAssignedTasks.length" class="task-section">
        <header class="task-section__head">
          <div class="task-section__title">
            <strong>管理员分配</strong>
            <el-tag type="primary" size="small" effect="plain">反馈同步</el-tag>
            <el-tag v-if="assignedPending" type="warning" size="small" effect="plain">
              {{ assignedPending }} 待完成
            </el-tag>
            <el-tag
              v-if="assignedTasks.some((t) => isTaskNudged(t))"
              type="danger"
              size="small"
              effect="plain"
            >
              有催办
            </el-tag>
          </div>
        </header>

        <el-table
          :data="visibleAssignedTasks"
          size="small"
          stripe
          class="task-table"
          :row-class-name="assignedTableRowClass"
        >
          <el-table-column label="任务" min-width="220">
            <template #default="{ row }">
              <div class="task-title">
                {{ row.title }}
                <el-tag v-if="isTaskNudged(row)" type="warning" size="small" effect="plain" class="nudge-tag">
                  催办
                </el-tag>
              </div>
              <div v-if="row.detail" class="task-detail">{{ row.detail }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="platform" label="平台" width="100" show-overflow-tooltip />
          <el-table-column prop="category" label="类型" width="80" />
          <el-table-column label="优先级" width="72" align="center">
            <template #default="{ row }">
              <el-tag :type="priorityMap[row.priority]?.type || 'info'" size="small">
                {{ priorityMap[row.priority]?.label || '中' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最新反馈" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <template v-if="row.lastFeedback">
                <el-tag
                  v-if="latestFeedbackLabel(row)"
                  size="small"
                  :type="OUTCOME_MAP[row.lastOutcome]?.type || 'info'"
                  effect="plain"
                  class="feedback-tag"
                >
                  {{ latestFeedbackLabel(row) }}
                </el-tag>
                <span class="feedback-snippet">{{ row.lastFeedback }}</span>
              </template>
              <el-text v-else type="info" size="small">待提交反馈</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="due" label="截止" width="110" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-space :size="4">
                <el-tag :type="TASK_STATUS_META[row.status]?.type" size="small">
                  {{ row.status }}
                </el-tag>
                <el-icon v-if="rowNeedsAttention(row)" class="need-help-icon" color="var(--el-color-warning)">
                  <WarningFilled />
                </el-icon>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="168" align="center" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                size="small"
                :icon="View"
                @click="openTaskDetail(row)"
              >
                详情
              </el-button>
              <el-button
                v-if="row.status !== '已完成'"
                link
                type="primary"
                size="small"
                @click="openFeedback(row)"
              >
                提交反馈
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <div v-if="visibleGroups.length" class="platform-groups">
        <section v-for="group in visibleGroups" :key="group.platformKey" class="platform-group">
          <header class="platform-group__head">
            <div class="platform-group__title">
              <strong>{{ group.platform }}</strong>
              <el-tag size="small" effect="plain">运营任务</el-tag>
              <el-tag v-if="group.high" type="danger" size="small" effect="plain">
                {{ group.high }} 项高优
              </el-tag>
              <el-tag v-if="group.pending" type="warning" size="small" effect="plain">
                {{ group.pending }} 待完成
              </el-tag>
            </div>
            <el-button
              v-if="group.route"
              link
              type="primary"
              :icon="Right"
              @click="goPlatform(group.route)"
            >
              进入运营
            </el-button>
          </header>

          <el-table :data="group.tasks" size="small" stripe class="task-table">
            <el-table-column label="任务" min-width="240">
              <template #default="{ row }">
                <div class="task-title">{{ row.title }}</div>
                <div v-if="row.detail" class="task-detail">{{ row.detail }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="storeName" label="店铺" width="130" show-overflow-tooltip />
            <el-table-column prop="category" label="类型" width="80" />
            <el-table-column label="来源" width="90">
              <template #default="{ row }">
                <el-tag :type="sourceMap[row.source]?.type || 'info'" size="small" effect="plain">
                  {{ sourceMap[row.source]?.label || '任务' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="72" align="center">
              <template #default="{ row }">
                <el-tag :type="priorityMap[row.priority]?.type || 'info'" size="small">
                  {{ priorityMap[row.priority]?.label || '中' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="due" label="截止" width="110" />
            <el-table-column label="状态" width="88" align="center">
              <template #default="{ row }">
                <el-tag :type="TASK_STATUS_META[row.status]?.type" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center" fixed="right">
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  size="small"
                  :icon="View"
                  @click="openTaskDetail(row)"
                >
                  详情
                </el-button>
                <el-button
                  v-if="row.status !== '已完成'"
                  link
                  type="primary"
                  size="small"
                  @click="openFeedback(row)"
                >
                  提交反馈
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>
      </PageSection>
    </div>

    <TaskFeedbackDialog
      v-model="feedbackVisible"
      :task="activeTask"
      v-model:outcome="feedbackForm.outcome"
      v-model:feedback="feedbackForm.feedback"
      :submitting="feedbackSubmitting"
      :is-assigned="isAssignedFeedback"
      :source-label="feedbackSourceMeta.label"
      :source-type="feedbackSourceMeta.type"
      @submit="submitFeedback"
      @closed="closeFeedbackDialog"
    />

    <AssignedTaskDetailDrawer
      v-model="detailVisible"
      :task="detailTask"
      :feedbacks="detailFeedbacks"
      viewer-role="employee"
    />

    <EmployeeTaskDetailDrawer
      v-model="opsDetailVisible"
      :task="opsDetailTask"
    />
  </PageScroll>
</template>

<style scoped>
.task-center {
  display: grid;
  gap: 16px;
}

.metric-value.is-primary {
  color: var(--ch-primary);
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-sm);
  background: var(--ch-surface);
  color: var(--ch-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.filter-chip:hover {
  border-color: var(--ch-primary-muted);
  color: var(--ch-primary);
}

.filter-chip.is-active {
  border-color: var(--ch-primary);
  background: var(--ch-primary-soft);
  color: var(--ch-primary);
  font-weight: 600;
}

.filter-chip__count {
  min-width: 18px;
  padding: 0 5px;
  border-radius: 10px;
  background: var(--ch-surface-muted);
  font-size: 12px;
  line-height: 18px;
  text-align: center;
}

.filter-chip.is-active .filter-chip__count {
  background: var(--ch-primary-muted);
  color: #fff;
}

.task-section,
.platform-group {
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-lg);
  background: var(--ch-surface);
  overflow: hidden;
}

.task-section__head,
.platform-group__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ch-border);
  background: var(--ch-surface-muted);
}

.task-section__title,
.platform-group__title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.task-section__title strong,
.platform-group__title strong {
  font-size: 15px;
  color: var(--ch-text);
}

.platform-groups {
  display: grid;
  gap: 16px;
}

.task-table {
  border-radius: 0;
}

.task-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--ch-text);
  line-height: 1.45;
}

.task-detail {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ch-text-muted);
  line-height: 1.4;
}

.feedback-tag {
  margin-right: 6px;
}

.feedback-snippet {
  font-size: 12px;
  color: var(--ch-text-secondary);
}

.need-help-icon {
  font-size: 14px;
}

.nudge-tag {
  margin-left: 6px;
  vertical-align: middle;
}

:deep(.is-nudged-row) > td {
  background: color-mix(in srgb, var(--el-color-warning) 12%, transparent) !important;
}

:deep(.is-attention-row) > td {
  background: color-mix(in srgb, var(--el-color-warning) 7%, transparent) !important;
}
</style>
