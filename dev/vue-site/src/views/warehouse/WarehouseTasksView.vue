<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Right } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { fetchWarehouseAssignedTasks, syncAssignedTaskFeedback } from '@/api/assignedTasks'
import { submitTaskFeedback } from '@/api/opsFeedback'
import { calcTaskStats } from '@/utils/operations'
import { TASK_STATUS_META } from '@/constants/operations'
import { OUTCOME_OPTIONS } from '@/constants/opsFeedbackDemo'
import { formatWarehouseScopeText } from '@/utils/warehouseScope'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const tasks = ref([])
const activeFilter = ref('all')
const feedbackVisible = ref(false)
const feedbackSubmitting = ref(false)
const activeTask = ref(null)
const feedbackForm = reactive({
  outcome: 'resolved',
  feedback: '',
})

const priorityMap = {
  high: { label: '高', type: 'danger' },
  medium: { label: '中', type: 'warning' },
  low: { label: '低', type: 'info' },
}

const scopeText = computed(() => formatWarehouseScopeText(auth.assignedWarehouseLabels))
const stats = computed(() => calcTaskStats(tasks.value))

const visibleTasks = computed(() => {
  if (activeFilter.value === 'all') {
    return tasks.value
  }
  if (activeFilter.value === 'active') {
    return tasks.value.filter((item) => item.status !== '已完成')
  }
  return tasks.value.filter((item) => item.status === activeFilter.value)
})

const filterOptions = computed(() => [
  { value: 'all', label: '全部', count: tasks.value.length },
  { value: 'active', label: '待完成', count: tasks.value.filter((t) => t.status !== '已完成').length },
  { value: '进行中', label: '进行中', count: tasks.value.filter((t) => t.status === '进行中').length },
  { value: '已完成', label: '已完成', count: tasks.value.filter((t) => t.status === '已完成').length },
])

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await fetchWarehouseAssignedTasks(auth)
  } catch {
    tasks.value = []
  } finally {
    loading.value = false
  }
}

function openFeedback(task) {
  activeTask.value = task
  feedbackForm.outcome = 'resolved'
  feedbackForm.feedback = ''
  feedbackVisible.value = true
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
      employeeId: auth.warehouse.id,
      employeeName: auth.warehouse.name,
      employeeRole: auth.warehouse.role,
      platform: activeTask.value.platform,
      platformKey: activeTask.value.platformKey,
      taskTitle: activeTask.value.title,
      category: activeTask.value.category,
      storeName: activeTask.value.storeName,
      outcome: feedbackForm.outcome,
      feedback: feedbackForm.feedback,
    }, auth)

    await syncAssignedTaskFeedback(activeTask.value.id, {
      outcome: feedbackForm.outcome,
      feedback: feedbackForm.feedback,
      assigneeName: auth.warehouse.name,
    }, auth)

    ElMessage.success('反馈已提交，管理员可在任务分配详情中查看')
    feedbackVisible.value = false
    await loadTasks()
  } catch (err) {
    ElMessage.error(err.message || '提交失败')
  } finally {
    feedbackSubmitting.value = false
  }
}

function goOrders() {
  router.push('/warehouse/pending-review')
}

onMounted(loadTasks)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="任务中心"
        eyebrow="仓储"
        :description="`${auth.warehouse.name} · ${auth.warehouse.role}${scopeText ? ` · 负责 ${scopeText}` : ''}`"
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
            <div class="metric-value">{{ stats.total }}</div>
            <div class="metric-label">分配任务</div>
          </div>
          <div class="metric-item">
            <div class="metric-value is-warning">{{ stats.pending + stats.inProgress }}</div>
            <div class="metric-label">待完成</div>
          </div>
          <div class="metric-item">
            <div class="metric-value is-danger">{{ stats.overdue }}</div>
            <div class="metric-label">已逾期</div>
          </div>
          <div class="metric-item">
            <div class="metric-value is-success">{{ stats.completionRate }}<small>%</small></div>
            <div class="metric-label">完成率</div>
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
          v-if="!loading && !visibleTasks.length"
          description="暂无管理员分配的仓库任务"
          :image-size="88"
        />

        <div v-else class="task-panel">
          <header class="task-panel__head">
            <strong>管理员分配</strong>
            <el-button link type="primary" :icon="Right" @click="goOrders">去处理出库单</el-button>
          </header>

          <el-table :data="visibleTasks" size="small" stripe class="task-table">
            <el-table-column label="任务" min-width="240">
              <template #default="{ row }">
                <div class="task-title">{{ row.title }}</div>
                <div v-if="row.detail" class="task-detail">{{ row.detail }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="storeName" label="关联仓库" width="130" show-overflow-tooltip />
            <el-table-column prop="category" label="类型" width="80" />
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
            <el-table-column label="操作" width="120" align="center" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status !== '已完成'"
                  link
                  type="primary"
                  size="small"
                  @click="openFeedback(row)"
                >
                  提交反馈
                </el-button>
                <el-text v-else type="success" size="small">已完成</el-text>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </PageSection>
    </div>

    <el-dialog
      v-model="feedbackVisible"
      title="提交处理反馈"
      width="480px"
      destroy-on-close
      @closed="activeTask = null"
    >
      <template v-if="activeTask">
        <div class="feedback-task-summary">
          <el-tag size="small" effect="plain">{{ activeTask.category }}</el-tag>
          <strong>{{ activeTask.title }}</strong>
          <p v-if="activeTask.detail">{{ activeTask.detail }}</p>
        </div>

        <el-form label-width="80px" class="feedback-form">
          <el-form-item label="处理结果" required>
            <el-radio-group v-model="feedbackForm.outcome">
              <el-radio v-for="item in OUTCOME_OPTIONS" :key="item.value" :value="item.value">
                {{ item.label }}
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="处理说明" required>
            <el-input
              v-model="feedbackForm.feedback"
              type="textarea"
              :rows="4"
              placeholder="说明处理措施、进展或需要协助的原因"
            />
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <el-button @click="feedbackVisible = false">取消</el-button>
        <el-button type="primary" :loading="feedbackSubmitting" @click="submitFeedback">
          提交反馈
        </el-button>
      </template>
    </el-dialog>
  </PageScroll>
</template>

<style scoped>
.task-center {
  display: grid;
  gap: 16px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
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

.task-panel {
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-lg);
  background: var(--ch-surface);
  overflow: hidden;
}

.task-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ch-border);
  background: var(--ch-surface-muted);
}

.task-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--ch-text);
}

.task-detail {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ch-text-muted);
}

.feedback-task-summary {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: var(--ch-radius-md);
  background: var(--ch-surface-muted);
}

.feedback-task-summary p {
  margin: 0;
  font-size: 12px;
  color: var(--ch-text-muted);
}
</style>
