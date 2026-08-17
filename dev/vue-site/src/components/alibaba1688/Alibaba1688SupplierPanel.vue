<script setup>
import { computed, ref } from 'vue'
import { summarize1688SupplierAlerts } from '@/utils/alibaba1688'
import Alibaba1688PanelHeader from '@/components/alibaba1688/Alibaba1688PanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

import { formatMoneyDecimal } from '@/utils/format'

const props = defineProps({
  alerts: { type: Array, default: () => [] },
  ranking: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

defineEmits(['refresh'])

const filterStatus = ref('open')

const summary = computed(() => summarize1688SupplierAlerts(props.alerts))

const filterOptions = computed(() => [
  { label: summary.value.open ? `待处理 (${summary.value.open})` : '待处理', value: 'open' },
  { label: '全部', value: 'all' },
  { label: '到货延期', value: 'delay' },
  { label: '缺货', value: 'stockout' },
  { label: '涨价预警', value: 'price_increase' },
  { label: '交期延误', value: 'delivery_delay' },
  { label: '起订量变更', value: 'moq_change' },
])

function onTimeRateText(rate) {
  const n = Number(rate)
  if (!Number.isFinite(n)) return '—'
  return `${Math.round(n * 1000) / 10}%`
}

const filteredAlerts = computed(() => {
  if (filterStatus.value === 'open') return props.alerts.filter((a) => a.isOpen)
  if (filterStatus.value === 'all') return props.alerts
  return props.alerts.filter((a) => a.type === filterStatus.value)
})

function severityType(severity) {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'info'
}
</script>

<template>
  <div class="panel">
    <Alibaba1688PanelHeader
      title="供应商跟进"
      description="复购排行（90 日）+ 延期/缺货等供应商预警"
      :synced-at="syncedAt"
      action-label="刷新预警"
      :loading="loading"
      @action="$emit('refresh')"
    />

    <div class="mini-stats">
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.open }}</span>
        <span class="mini-stat__label">待处理</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value is-danger">{{ summary.high }}</span>
        <span class="mini-stat__label">高优先级</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.total }}</span>
        <span class="mini-stat__label">预警总数</span>
      </div>
    </div>

    <div v-if="ranking.length" class="ranking-block">
      <div class="ranking-title">复购供应商排行（90 日）</div>
      <el-table :data="ranking" stripe size="small" class="data-table">
        <el-table-column prop="supplierName" label="供应商" min-width="160" show-overflow-tooltip />
        <el-table-column prop="orderCount" label="单量" width="90" align="center" />
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }">{{ formatMoneyDecimal(row.totalAmount) }}</template>
        </el-table-column>
        <el-table-column label="准时率" width="100" align="center">
          <template #default="{ row }">{{ onTimeRateText(row.onTimeRate) }}</template>
        </el-table-column>
      </el-table>
    </div>

    <el-segmented v-model="filterStatus" :options="filterOptions" />

    <el-table :data="filteredAlerts" stripe size="small" v-loading="loading" class="data-table">
      <el-table-column prop="typeLabel" label="类型" width="110" fixed />
      <el-table-column
        v-if="showStoreColumn"
        label="采购账号"
        min-width="130"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <AssigneeTableColumn />
      <el-table-column prop="supplierName" label="供应商" min-width="150" show-overflow-tooltip />
      <el-table-column prop="productName" label="关联商品" min-width="140" show-overflow-tooltip />
      <el-table-column label="详情" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.detail || row.message || '—' }}</template>
      </el-table-column>
      <el-table-column label="优先级" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="severityType(row.severity)" size="small">
            {{ row.severity === 'high' ? '高' : row.severity === 'medium' ? '中' : '低' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="reportedAt" label="上报时间" width="160" />
      <el-table-column label="状态" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-tag :type="row.isOpen ? 'warning' : 'success'" size="small">
            {{ row.isOpen ? '待处理' : '已关闭' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !filteredAlerts.length" description="暂无供应商预警" :image-size="72" />
  </div>
</template>

<style scoped>
.panel { display: grid; gap: 16px; }

.mini-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.mini-stat {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.mini-stat__value { font-size: 18px; font-weight: 700; }
.mini-stat__value.is-danger { color: var(--el-color-danger); }
.mini-stat__label { font-size: 13px; color: var(--el-text-color-secondary); }

.data-table { border-radius: 8px; }

@media (max-width: 768px) {
  .mini-stats { grid-template-columns: 1fr; }
}
</style>
