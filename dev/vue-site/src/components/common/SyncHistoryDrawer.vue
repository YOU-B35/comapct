<script setup>
import { ref, watch } from 'vue'
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
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const error = ref('')
const rows = ref([])

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

watch(
  () => props.modelValue,
  (open) => {
    if (open) load()
  },
)

function statusLabel(s) {
  const v = String(s || '').toLowerCase()
  if (v === 'success' || v === 'partial') return v === 'partial' ? '部分成功' : '成功'
  if (['failed', 'error'].includes(v)) return '失败'
  if (['running', 'pending', 'retry_wait', 'queued'].includes(v)) return '进行中'
  return s || '—'
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
    <el-table v-loading="loading" :data="rows" size="small" empty-text="暂无同步记录">
      <el-table-column label="状态" width="88">
        <template #default="{ row }">{{ statusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column label="开始时间" min-width="140">
        <template #default="{ row }">{{ formatSyncClock(row.started_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="结束时间" min-width="140">
        <template #default="{ row }">{{ formatSyncClock(row.finished_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="耗时" width="88">
        <template #default="{ row }">{{ formatSyncDuration(row.started_at, row.finished_at) }}</template>
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
    </el-table>
  </el-drawer>
</template>
