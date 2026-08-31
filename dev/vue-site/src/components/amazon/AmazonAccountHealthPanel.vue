<script setup>
import { computed, ref } from 'vue'
import { ACCOUNT_METRIC_STATUS } from '@/constants/amazonDaily'
import { summarizeAccountHealth } from '@/utils/amazon'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  metrics: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['refresh', 'open-history'])


const filter = ref('alert')

const summary = computed(() => summarizeAccountHealth(props.metrics))

const filtered = computed(() => {
  if (filter.value === 'all') return props.metrics
  if (filter.value === 'alert') {
    return props.metrics.filter((m) => m.status === 'critical' || m.status === 'warning')
  }
  return props.metrics.filter((m) => m.status === filter.value)
})

function statusMeta(row) {
  return ACCOUNT_METRIC_STATUS[row.status] || ACCOUNT_METRIC_STATUS.normal
}

function trendIcon(trend) {
  if (trend === 'up') return '↑'
  if (trend === 'down') return '↓'
  return '→'
}
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="账户状况"
      description="每日反映账户健康；爆红指标需优先处理，避免限流或封号风险"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      @open-history="$emit('open-history')"
    >
      <template #actions>
        <el-button size="small" :loading="loading" @click="emit('refresh')">刷新数据</el-button>
      </template>
    </AmazonPanelHeader>

    <div class="mini-stats">
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.critical }}</span>
        <span class="mini-stat__label">爆红</span>
      </div>
      <div class="mini-stat is-warning">
        <span class="mini-stat__value">{{ summary.warning }}</span>
        <span class="mini-stat__label">预警</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.normal }}</span>
        <span class="mini-stat__label">正常</span>
      </div>
    </div>

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="alert">待关注 ({{ summary.critical + summary.warning }})</el-radio-button>
        <el-radio-button value="critical">{{ summary.critical ? `爆红 (${summary.critical})` : '爆红' }}</el-radio-button>
        <el-radio-button value="warning">{{ summary.warning ? `预警 (${summary.warning})` : '预警' }}</el-radio-button>
        <el-radio-button value="all">全部指标</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="filtered" stripe size="small" v-loading="loading">
      <el-table-column prop="label" label="指标" min-width="140" />
      <el-table-column
        v-if="showStoreColumn"
        label="店铺"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <AssigneeTableColumn />
      <el-table-column label="当前值" width="110">
        <template #default="{ row }">
          <el-text :type="statusMeta(row).type" tag="strong">{{ row.value }}</el-text>
          <span class="trend">{{ trendIcon(row.trend) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="threshold" label="标准" width="100" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row).type" size="small">{{ statusMeta(row).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="note" label="处理建议" min-width="220" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<style scoped>
.amz-panel { display: grid; gap: 16px; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 14px; }
.mini-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.mini-stat {
  display: grid; gap: 4px; padding: 12px 14px;
  border-radius: 8px; background: var(--el-fill-color-lighter);
}
.mini-stat.is-danger .mini-stat__value { color: var(--el-color-danger); }
.mini-stat.is-warning .mini-stat__value { color: var(--el-color-warning); }
.mini-stat__value { font-size: 18px; font-weight: 700; }
.mini-stat__label { font-size: 13px; color: var(--el-text-color-secondary); }
.trend { margin-left: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
</style>
