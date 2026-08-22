<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, Right, UserFilled } from '@element-plus/icons-vue'

const props = defineProps({
  report: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const router = useRouter()

const stats = computed(() => props.report?.stats || {})
const platforms = computed(() => props.report?.platformSnapshots || [])
const employees = computed(() => props.report?.employeeFollowUps || [])
const feedbacks = computed(() => props.report?.feedbacks || [])

const alertLevelType = {
  danger: 'danger',
  warning: 'warning',
  success: 'success',
}

function goPlatform(route) {
  if (route) router.push(route)
}
</script>

<template>
  <div v-loading="loading" class="daily-report">
    <header class="daily-report__head">
      <div>
        <h3 class="daily-report__title">今日运营日报</h3>
        <p class="daily-report__sub">
          {{ report?.date || '—' }}
          <span v-if="report?.syncedAt"> · 数据同步 {{ formatUtc8(report.syncedAt) }}</span>
        </p>
      </div>
      <el-tag type="info" effect="plain" size="small">每日汇总</el-tag>
    </header>

    <div class="metrics-bar metrics-bar--4">
      <div class="metric-item">
        <div class="metric-value" :class="stats.totalIssues ? 'is-danger' : 'is-success'">
          {{ stats.totalIssues ?? 0 }}
        </div>
        <div class="metric-label">待跟进问题</div>
        <div class="metric-hint">{{ stats.platformCount ?? 0 }} 个平台</div>
      </div>
      <div class="metric-item">
        <div class="metric-value" :class="stats.taskCompletionRate >= 60 ? 'is-success' : 'is-warning'">
          {{ stats.taskCompletionRate ?? 0 }}<small>%</small>
        </div>
        <div class="metric-label">任务完成率</div>
        <div class="metric-hint">{{ stats.tasksCompleted }}/{{ stats.tasksTotal }} 已完成</div>
      </div>
      <div class="metric-item">
        <div class="metric-value is-primary">{{ stats.feedbackCount ?? 0 }}</div>
        <div class="metric-label">运营反馈</div>
        <div class="metric-hint">今日已提交</div>
      </div>
      <div class="metric-item">
        <div class="metric-value" :class="stats.feedbackNeedHelp ? 'is-warning' : ''">
          {{ stats.feedbackNeedHelp ?? 0 }}
        </div>
        <div class="metric-label">需协助</div>
        <div class="metric-hint">待管理员跟进</div>
      </div>
    </div>

    <section class="report-section">
      <h4 class="report-section__title">各平台运营情况</h4>
      <div v-if="platforms.length" class="platform-grid">
        <article
          v-for="item in platforms"
          :key="item.id"
          class="platform-card"
          @click="goPlatform(item.route)"
        >
          <div class="platform-card__top">
            <strong>{{ item.name }}</strong>
            <el-tag :type="alertLevelType[item.alertLevel]" size="small" effect="plain">
              {{ item.issueCount ? `${item.issueCount} 待跟进` : '正常' }}
            </el-tag>
          </div>
          <div class="platform-card__owner">负责人 · {{ item.owner }}</div>
          <p class="platform-card__summary">{{ item.summary }}</p>
          <div class="platform-card__metrics">
            <span>{{ item.revenueText }}</span>
            <span class="dot">·</span>
            <span>{{ item.orders }} 单</span>
          </div>
        </article>
      </div>
      <el-empty v-else description="暂无平台运营数据" :image-size="64" />
    </section>

    <section class="report-section">
      <h4 class="report-section__title">员工跟进概况</h4>
      <el-table v-if="employees.length" :data="employees" size="small" stripe>
        <el-table-column label="员工" width="100">
          <template #default="{ row }">
            <div class="emp-cell">
              <el-icon><UserFilled /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="岗位" width="120" show-overflow-tooltip />
        <el-table-column label="任务完成" min-width="140">
          <template #default="{ row }">
            <el-progress :percentage="row.completionRate" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column label="预警待办" width="90" align="center">
          <template #default="{ row }">
            <el-text :type="row.issuePending ? 'danger' : 'info'" size="small">
              {{ row.issuePending }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column label="今日反馈" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.feedbackToday ? 'success' : 'info'" size="small" effect="plain">
              {{ row.feedbackToday }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近反馈" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-text v-if="row.latestFeedback" size="small">{{ row.latestFeedback }}</el-text>
            <el-text v-else size="small" type="info">暂无</el-text>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="report-section">
      <div class="report-section__head">
        <h4 class="report-section__title">
          <el-icon><ChatDotRound /></el-icon>
          运营问题反馈
        </h4>
        <el-text size="small" type="info">员工处理任务时提交的说明与进展</el-text>
      </div>

      <el-empty v-if="!feedbacks.length" description="今日暂无运营反馈" :image-size="64" />

      <div v-else class="feedback-list">
        <article v-for="item in feedbacks" :key="item.id" class="feedback-item">
          <div class="feedback-item__head">
            <div class="feedback-item__who">
              <strong>{{ item.employeeName }}</strong>
              <span class="feedback-item__role">{{ item.employeeRole }}</span>
            </div>
            <div class="feedback-item__meta">
              <el-tag :type="item.outcomeMeta?.type || 'info'" size="small" effect="plain">
                {{ item.outcomeLabel }}
              </el-tag>
              <el-tag size="small" effect="plain">{{ item.platform }}</el-tag>
              <span class="feedback-item__time">{{ formatUtc8(item.submittedAt) }}</span>
            </div>
          </div>
          <h5 class="feedback-item__task">{{ item.taskTitle }}</h5>
          <p v-if="item.storeName" class="feedback-item__store">{{ item.storeName }}</p>
          <p class="feedback-item__text">{{ item.feedback || '（无详细说明）' }}</p>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.daily-report {
  display: grid;
  gap: 20px;
  padding: 16px 20px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-lg);
  background: var(--ch-surface);
}

.daily-report__head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
}

.daily-report__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ch-text);
}

.daily-report__sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ch-text-muted);
}

.report-section {
  display: grid;
  gap: 12px;
}

.report-section__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  justify-content: space-between;
}

.report-section__title {
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ch-text);
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.platform-card {
  padding: 14px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-md);
  background: var(--ch-surface-muted);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.platform-card:hover {
  border-color: var(--ch-primary-muted);
  box-shadow: var(--ch-shadow-xs);
}

.platform-card__top {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.platform-card__owner {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ch-text-muted);
}

.platform-card__summary {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ch-text-secondary);
}

.platform-card__metrics {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ch-text-muted);
}

.platform-card__metrics .dot {
  margin: 0 4px;
}

.emp-cell {
  display: flex;
  gap: 6px;
  align-items: center;
}

.feedback-list {
  display: grid;
  gap: 12px;
}

.feedback-item {
  padding: 14px 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-md);
  background: var(--ch-surface-muted);
}

.feedback-item__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.feedback-item__who {
  display: flex;
  gap: 8px;
  align-items: center;
}

.feedback-item__role {
  font-size: 12px;
  color: var(--ch-text-muted);
}

.feedback-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.feedback-item__time {
  font-size: 12px;
  color: var(--ch-text-muted);
}

.feedback-item__task {
  margin: 10px 0 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ch-text);
}

.feedback-item__store {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ch-text-muted);
}

.feedback-item__text {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--ch-text-secondary);
}
</style>
