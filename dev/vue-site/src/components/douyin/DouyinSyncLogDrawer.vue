<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, nextTick, ref, watch } from 'vue'
import {
  CircleCheck,
  CircleClose,
  Loading,
  Clock,
} from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 当前/最近一次运行 */
  run: {
    type: Object,
    default: () => ({
      title: '',
      status: 'idle', // idle | running | success | partial | failed
      startedAt: '',
      finishedAt: '',
      steps: [],
      logs: [],
    }),
  },
})

const emit = defineEmits(['update:modelValue'])

const logsEl = ref(null)

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const doneCount = computed(() =>
  (props.run.steps || []).filter((s) => s.status === 'success' || s.status === 'failed').length,
)

const successCount = computed(() =>
  (props.run.steps || []).filter((s) => s.status === 'success').length,
)

const failedCount = computed(() =>
  (props.run.steps || []).filter((s) => s.status === 'failed').length,
)

const totalCount = computed(() => (props.run.steps || []).length)

const percent = computed(() => {
  if (!totalCount.value) return props.run.status === 'running' ? 8 : 0
  const base = Math.round((doneCount.value / totalCount.value) * 100)
  if (props.run.status === 'running' && base < 100) {
    const hasRunning = (props.run.steps || []).some((s) => s.status === 'running')
    return Math.min(99, base + (hasRunning ? 8 : 0))
  }
  return props.run.status === 'running' ? Math.min(99, Math.max(base, 8)) : base
})

const progressStatus = computed(() => {
  if (props.run.status === 'failed') return 'exception'
  if (props.run.status === 'partial') return 'warning'
  if (props.run.status === 'success') return 'success'
  return undefined
})

const summaryText = computed(() => {
  if (props.run.status === 'running') {
    const cur = (props.run.steps || []).find((s) => s.status === 'running')
    return cur
      ? `正在同步：${cur.label}（${doneCount.value}/${totalCount.value}）`
      : '同步进行中…'
  }
  if (props.run.status === 'success') {
    return `全部完成（${successCount.value}/${totalCount.value}）`
  }
  if (props.run.status === 'partial') {
    return `部分完成：成功 ${successCount.value}，失败 ${failedCount.value}`
  }
  if (props.run.status === 'failed') return '同步失败，请查看步骤与明细日志'
  return '暂无进行中的任务，点击「刷新全部」或分模块同步后可在此查看进度'
})

watch(
  () => [(props.run.logs || []).length, open.value],
  async () => {
    if (!open.value) return
    await nextTick()
    const el = logsEl.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

function stepIcon(status) {
  if (status === 'success') return CircleCheck
  if (status === 'failed') return CircleClose
  if (status === 'running') return Loading
  return Clock
}

function stepTagType(status) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}

function stepTagLabel(status) {
  if (status === 'success') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '进行中'
  if (status === 'pending') return '等待'
  return status || '—'
}

function logLevelType(level) {
  if (level === 'error') return 'danger'
  if (level === 'warn') return 'warning'
  if (level === 'success') return 'success'
  return 'info'
}

function logLevelLabel(level) {
  if (level === 'error') return '错误'
  if (level === 'warn') return '警告'
  if (level === 'success') return '成功'
  return '信息'
}
</script>

<template>
  <el-drawer
    v-model="open"
    title="数据获取日志"
    size="480px"
    append-to-body
    class="douyin-sync-log-drawer"
  >
    <div class="sync-log">
      <div class="sync-log__summary">
        <div class="sync-log__summary-title">{{ run.title || '抖音数据同步' }}</div>
        <el-text size="small" type="info">{{ summaryText }}</el-text>
        <el-progress
          class="sync-log__progress"
          :percentage="percent"
          :status="progressStatus"
          :stroke-width="10"
        />
        <div class="sync-log__meta">
          <el-text size="small">
            完成度 <strong>{{ percent }}%</strong>
          </el-text>
          <el-text size="small" type="info">
            步骤 {{ doneCount }}/{{ totalCount || '—' }}
          </el-text>
          <el-text v-if="run.startedAt" size="small" type="info">
            开始 {{ formatUtc8(run.startedAt) }}
          </el-text>
          <el-text v-if="run.finishedAt" size="small" type="info">
            结束 {{ formatUtc8(run.finishedAt) }}
          </el-text>
        </div>
      </div>

      <section class="sync-log__section">
        <h5 class="sync-log__section-title">任务步骤</h5>
        <el-empty
          v-if="!(run.steps || []).length"
          :image-size="56"
          description="尚无步骤记录"
        />
        <ul v-else class="sync-log__steps">
          <li
            v-for="(step, idx) in run.steps"
            :key="step.id || idx"
            class="sync-log__step"
            :class="`is-${step.status || 'pending'}`"
          >
            <el-icon class="sync-log__step-icon" :class="`is-${step.status || 'pending'}`">
              <component :is="stepIcon(step.status)" />
            </el-icon>
            <div class="sync-log__step-body">
              <div class="sync-log__step-row">
                <strong>{{ idx + 1 }}. {{ step.label }}</strong>
                <el-tag size="small" effect="plain" :type="stepTagType(step.status)">
                  {{ stepTagLabel(step.status) }}
                </el-tag>
              </div>
              <p v-if="step.message" class="sync-log__step-msg">{{ step.message }}</p>
              <p v-if="step.error" class="sync-log__step-err">{{ step.error }}</p>
              <el-text v-if="step.updatedAt" size="small" type="info">
                {{ formatUtc8(step.updatedAt) }}
              </el-text>
            </div>
          </li>
        </ul>
      </section>

      <section class="sync-log__section">
        <h5 class="sync-log__section-title">明细日志</h5>
        <el-empty
          v-if="!(run.logs || []).length"
          :image-size="56"
          description="尚无日志"
        />
        <ul v-else ref="logsEl" class="sync-log__logs">
          <li v-for="(line, idx) in run.logs" :key="`${line.at}-${idx}`" class="sync-log__log">
            <el-text size="small" type="info" class="sync-log__log-time">{{ line.at }}</el-text>
            <el-tag size="small" effect="plain" :type="logLevelType(line.level)">
              {{ logLevelLabel(line.level) }}
            </el-tag>
            <span class="sync-log__log-text">{{ line.text }}</span>
          </li>
        </ul>
      </section>
    </div>
  </el-drawer>
</template>

<style scoped>
.sync-log {
  display: grid;
  gap: 18px;
}

.sync-log__summary {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  border-radius: 10px;
  background: linear-gradient(180deg, #f8fafc 0%, #fff 100%);
}

.sync-log__summary-title {
  font-size: 15px;
  font-weight: 600;
}

.sync-log__progress {
  margin-top: 4px;
}

.sync-log__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.sync-log__section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
}

.sync-log__steps,
.sync-log__logs {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
}

.sync-log__logs {
  max-height: 280px;
  overflow: auto;
}

.sync-log__step {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  border: 1px solid transparent;
}

.sync-log__step.is-running {
  border-color: #fbbf24;
  background: #fffbeb;
}

.sync-log__step.is-failed {
  border-color: #fca5a5;
  background: #fef2f2;
}

.sync-log__step.is-success {
  border-color: #86efac;
  background: #f0fdf4;
}

.sync-log__step-icon {
  margin-top: 2px;
  font-size: 16px;
}

.sync-log__step-icon.is-success { color: var(--el-color-success); }
.sync-log__step-icon.is-failed { color: var(--el-color-danger); }
.sync-log__step-icon.is-running {
  color: var(--el-color-warning);
  animation: spin 1s linear infinite;
}
.sync-log__step-icon.is-pending { color: var(--el-color-info); }

.sync-log__step-body {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 4px;
}

.sync-log__step-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sync-log__step-msg,
.sync-log__step-err {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.sync-log__step-err {
  color: var(--el-color-danger);
}

.sync-log__log {
  display: grid;
  grid-template-columns: 70px auto 1fr;
  gap: 8px;
  align-items: start;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  font-size: 12px;
}

.sync-log__log-time {
  font-variant-numeric: tabular-nums;
}

.sync-log__log-text {
  line-height: 1.45;
  color: var(--ch-text, var(--el-text-color-primary));
  word-break: break-word;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
