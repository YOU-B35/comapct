<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import {
  formatSyncClock,
  formatSyncDuration,
  formatTriggerLabel,
  formatRecordCount,
  normalizeSyncJob,
} from '@/utils/syncHistory'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  platform: { type: String, required: true },
  fetcher: { type: Function, required: true },
  /** 自动刷新间隔；<=0 表示不轮询 */
  intervalMs: { type: Number, default: 2500 },
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const error = ref('')
const rows = ref([])
const now = ref(Date.now())

async function load() {
  loading.value = true
  error.value = ''
  try {
    const list = await props.fetcher()
    rows.value = (Array.isArray(list) ? list : []).map(normalizeSyncJob)
  } catch (e) {
    error.value = e?.message || '加载失败'
    rows.value = []
  } finally {
    loading.value = false
  }
}

let pollTimer = null
let tickTimer = null

function startPolling() {
  stopPolling()
  load()
  if (props.intervalMs > 0) {
    pollTimer = window.setInterval(load, props.intervalMs)
    tickTimer = window.setInterval(() => { now.value = Date.now() }, 1000)
  }
}

function stopPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  if (tickTimer) window.clearInterval(tickTimer)
  pollTimer = null
  tickTimer = null
}

watch(() => props.modelValue, (open) => {
  if (open) startPolling()
  else stopPolling()
})

onBeforeUnmount(stopPolling)

function statusLabel(s) {
  const v = String(s || '').toLowerCase()
  if (v === 'success' || v === 'partial') return v === 'partial' ? '部分成功' : '成功'
  if (['failed', 'error'].includes(v)) return '失败'
  if (['running', 'pending', 'retry_wait', 'queued'].includes(v)) return '进行中'
  return s || '—'
}

function isRunning(s) {
  return ['running', 'pending', 'retry_wait', 'queued'].includes(String(s || '').toLowerCase())
}

function liveDuration(row) {
  if (isRunning(row.status)) {
    const start = row.started_at || row.startedAt
    if (start) {
      const t = new Date(String(start).replace(' ', 'T')).getTime()
      if (Number.isFinite(t)) {
        const sec = Math.max(0, Math.round((now.value - t) / 1000))
        return `进行中 ${sec < 60 ? `${sec}秒` : `${Math.floor(sec / 60)}分${sec % 60}秒`}`
      }
    }
  }
  return formatSyncDuration(row.started_at || row.startedAt, row.finished_at || row.finishedAt)
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="同步记录"
    size="560px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" style="margin-bottom: 12px" />
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <el-text type="info" size="small">
        最近 {{ rows.length || 0 }} 条{{ props.intervalMs > 0 ? '（自动刷新）' : '' }}
      </el-text>
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
    </div>
    <el-table v-loading="loading" :data="rows" size="small" empty-text="暂无同步记录">
      <el-table-column v-if="rows.some((r) => r.label)" prop="label" label="类型" min-width="100" />
      <el-table-column label="状态" width="88">
        <template #default="{ row }">
          <el-tag
            size="small"
            effect="plain"
            :type="row.status === 'success' || row.status === 'partial' ? 'success' : isRunning(row.status) ? 'warning' : row.status === 'failed' || row.status === 'error' ? 'danger' : 'info'"
          >
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" min-width="140">
        <template #default="{ row }">{{ formatSyncClock(row.started_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="结束时间" min-width="140">
        <template #default="{ row }">{{ formatSyncClock(row.finished_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="耗时" width="104">
        <template #default="{ row }">{{ liveDuration(row) }}</template>
      </el-table-column>
      <el-table-column label="获取条数" min-width="120">
        <template #default="{ row }">{{ formatRecordCount(row, platform) }}</template>
      </el-table-column>
      <el-table-column label="触发方式" width="80">
        <template #default="{ row }">{{ formatTriggerLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="失败原因" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.error_message || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="rows.some((r) => r.summary)" label="摘要" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.summary || '—' }}</template>
      </el-table-column>
    </el-table>
  </el-drawer>
</template>
