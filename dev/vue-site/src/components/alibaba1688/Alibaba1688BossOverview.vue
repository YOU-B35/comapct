<script setup>
import { computed } from 'vue'
import {
  summarize1688ByStore,
  summarize1688PurchaseOrders,
  summarize1688SupplierAlerts,
} from '@/utils/alibaba1688'
import { resolveStoreAssignee } from '@/utils/storeAssignment'
import AssigneeTag from '@/components/common/AssigneeTag.vue'
import PlatformAnalyticsCharts from '@/components/charts/PlatformAnalyticsCharts.vue'

const props = defineProps({
  purchaseOrders: { type: Array, default: () => [] },
  supplierAlerts: { type: Array, default: () => [] },
  overview: { type: Object, default: null },
  stores: { type: Array, default: () => [] },
  assigneeMap: { type: Object, default: () => ({}) },
  showStoreList: { type: Boolean, default: true },
})

const emit = defineEmits(['navigate'])

const orderSummary = computed(() => summarize1688PurchaseOrders(props.purchaseOrders))
const alertSummary = computed(() => summarize1688SupplierAlerts(props.supplierAlerts))
const storeSummaries = computed(() =>
  summarize1688ByStore(props.purchaseOrders, props.supplierAlerts, props.stores),
)

const keyMetrics = computed(() => {
  const ov = props.overview
  if (ov && typeof ov === 'object') {
    const pending = Number(ov.pendingPurchase) || 0
    const open = Number(ov.openAlerts) || 0
    const delayed = Number(ov.delayedCount) || 0
    const stockout = Number(ov.stockoutCount) || 0
    return [
      {
        label: '待跟进采购',
        value: pending,
        type: pending ? 'warning' : undefined,
        hint: '待付款 / 待发货',
      },
      {
        label: '开放预警',
        value: open,
        type: open ? 'danger' : 'success',
        hint: '供应商待处理',
      },
      {
        label: '延期未到',
        value: delayed,
        type: delayed ? 'warning' : undefined,
        hint: '预计到货已过期',
      },
      {
        label: '缺货',
        value: stockout,
        type: stockout ? 'danger' : undefined,
        hint: '状态含缺货标记',
      },
    ]
  }
  return [
    {
      label: '今日采购单',
      value: orderSummary.value.total,
      hint: orderSummary.value.totalAmountText,
    },
    {
      label: '待付款',
      value: orderSummary.value.pendingPayment,
      type: orderSummary.value.pendingPayment ? 'warning' : undefined,
      hint: '需今日完成付款',
    },
    {
      label: '待发货 / 待收货',
      value: orderSummary.value.pendingShipment + orderSummary.value.pendingReceive,
      type: orderSummary.value.pendingShipment ? 'danger' : 'primary',
      hint: `待发 ${orderSummary.value.pendingShipment} · 待收 ${orderSummary.value.pendingReceive}`,
    },
    {
      label: '供应商预警',
      value: alertSummary.value.open,
      type: alertSummary.value.high ? 'danger' : alertSummary.value.open ? 'warning' : 'success',
      hint: alertSummary.value.high ? `${alertSummary.value.high} 项高优先级` : '跟进供应商动态',
    },
  ]
})

const alertItems = computed(() => [
  { label: '待付款', count: orderSummary.value.pendingPayment, tab: 'purchase', type: 'warning' },
  { label: '待发货', count: orderSummary.value.pendingShipment, tab: 'purchase', type: 'danger' },
  { label: '供应商预警', count: alertSummary.value.open, tab: 'supplier', type: 'primary' },
])

function storeAlerts(row) {
  const items = []
  if (row.orders.pendingPayment) items.push({ text: `待付款 ${row.orders.pendingPayment}`, type: 'warning' })
  if (row.orders.pendingShipment) items.push({ text: `待发货 ${row.orders.pendingShipment}`, type: 'danger' })
  if (row.orders.pendingReceive) items.push({ text: `待收货 ${row.orders.pendingReceive}`, type: 'primary' })
  if (row.alerts.open) items.push({ text: `预警 ${row.alerts.open}`, type: 'info' })
  return items
}

const chartMetrics = computed(() => [
  { name: '采购单', value: orderSummary.value.total },
  { name: '待付款', value: orderSummary.value.pendingPayment },
  { name: '待发货', value: orderSummary.value.pendingShipment },
  { name: '供应商预警', value: alertSummary.value.open },
])

const chartStructure = computed(() =>
  alertItems.value.map((i) => ({
    name: i.label,
    value: i.count,
    tab: i.tab,
    color: i.type === 'danger' ? '#ef4444' : i.type === 'warning' ? '#f59e0b' : '#3b82f6',
  })),
)

const chartCompare = computed(() =>
  storeSummaries.value.map((row) => ({
    id: row.store.id,
    name: row.store.storeName,
    value: row.orders.total,
  })),
)
</script>

<template>
  <div class="overview">
    <div class="metrics-bar metrics-bar--4">
      <div v-for="item in keyMetrics" :key="item.label" class="metric-item">
        <div class="metric-value" :class="item.type ? `is-${item.type}` : ''">{{ item.value }}</div>
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-hint">{{ item.hint }}</div>
      </div>
    </div>

    <div class="alert-bar">
      <button
        v-for="item in alertItems.filter((i) => i.count > 0)"
        :key="item.label"
        type="button"
        class="alert-chip"
        :class="`is-${item.type}`"
        @click="emit('navigate', item.tab)"
      >
        <span class="alert-count">{{ item.count }}</span>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <PlatformAnalyticsCharts
      title="1688 数据分析"
      :metric-items="chartMetrics"
      metric-title="核心指标"
      :compare-items="chartCompare"
      compare-title="账号采购对比"
      compare-value-label="采购单"
      :structure-items="chartStructure"
      structure-title="待办结构"
      @navigate="emit('navigate', $event)"
    />

    <el-table
      v-if="showStoreList && storeSummaries.length"
      :data="storeSummaries"
      size="small"
      class="store-table"
      :show-header="storeSummaries.length > 1"
    >
      <el-table-column label="采购账号" min-width="140">
        <template #default="{ row }">
          <strong>{{ row.store.storeName }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="96">
        <template #default="{ row }">
          <AssigneeTag :name="resolveStoreAssignee(row.store.id, assigneeMap)" />
        </template>
      </el-table-column>
      <el-table-column label="采购单" width="80" align="center">
        <template #default="{ row }">{{ row.orders.total }}</template>
      </el-table-column>
      <el-table-column label="待跟进" width="80" align="center">
        <template #default="{ row }">
          <el-text :type="row.orders.pending ? 'warning' : 'info'" size="small">
            {{ row.orders.pending }}
          </el-text>
        </template>
      </el-table-column>
      <el-table-column label="采购额" width="110" align="right">
        <template #default="{ row }">{{ row.orders.totalAmountText }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="180">
        <template #default="{ row }">
          <el-space v-if="storeAlerts(row).length" wrap :size="4">
            <el-tag v-for="tag in storeAlerts(row)" :key="tag.text" :type="tag.type" size="small">
              {{ tag.text }}
            </el-tag>
          </el-space>
          <el-text v-else size="small" type="success">正常</el-text>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.overview {
  display: grid;
  gap: 16px;
}
</style>
