<script setup>
import { computed } from 'vue'
import { summarizeWalmartByStore, summarizeWalmartOrders, summarizeWalmartListings } from '@/utils/walmart'
import { resolveStoreAssignee } from '@/utils/storeAssignment'
import AssigneeTag from '@/components/common/AssigneeTag.vue'
import PlatformAnalyticsCharts from '@/components/charts/PlatformAnalyticsCharts.vue'

const props = defineProps({
  orders: { type: Array, default: () => [] },
  issues: { type: Array, default: () => [] },
  stores: { type: Array, default: () => [] },
  assigneeMap: { type: Object, default: () => ({}) },
  showStoreList: { type: Boolean, default: true },
})

const emit = defineEmits(['navigate'])

const orderSummary = computed(() => summarizeWalmartOrders(props.orders))
const issueSummary = computed(() => summarizeWalmartListings(props.issues))
const storeSummaries = computed(() =>
  summarizeWalmartByStore(props.orders, props.issues, props.stores),
)

const keyMetrics = computed(() => [
  {
    label: '今日订单',
    value: orderSummary.value.total,
    hint: orderSummary.value.totalAmountText,
  },
  {
    label: '待处理',
    value: orderSummary.value.pending,
    hint: `WFS ${orderSummary.value.wfsPending} · 自发货 ${orderSummary.value.sellerPending}`,
    type: orderSummary.value.pending ? 'warning' : undefined,
  },
  {
    label: 'Listing 问题',
    value: issueSummary.value.open,
    hint: issueSummary.value.high ? `${issueSummary.value.high} 项高优先级` : '待修复',
    type: issueSummary.value.open ? 'danger' : undefined,
  },
  {
    label: '已解决',
    value: issueSummary.value.resolved,
    hint: `共 ${issueSummary.value.total} 条记录`,
    type: 'success',
  },
])

const alertItems = computed(() => [
  { label: '待处理订单', count: orderSummary.value.pending, tab: 'orders', type: 'warning' },
  { label: 'Listing 问题', count: issueSummary.value.open, tab: 'listings', type: 'danger' },
  { label: '高优先级', count: issueSummary.value.high, tab: 'listings:high', type: 'danger' },
])

function storeAlerts(row) {
  const items = []
  if (row.orders.pending) items.push({ text: `待处理 ${row.orders.pending}`, type: 'warning' })
  if (row.listings.open) items.push({ text: `Listing ${row.listings.open}`, type: 'danger' })
  if (row.listings.high) items.push({ text: `高优 ${row.listings.high}`, type: 'danger' })
  return items
}

const chartMetrics = computed(() => [
  { name: '今日订单', value: orderSummary.value.total },
  { name: '待处理', value: orderSummary.value.pending },
  { name: 'Listing问题', value: issueSummary.value.open },
  { name: '已解决', value: issueSummary.value.resolved },
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
  <div class="wm-overview">
    <div class="metrics-bar metrics-bar--4">
      <div v-for="item in keyMetrics" :key="item.label" class="metric-item">
        <div class="metric-value" :class="item.type ? `is-${item.type}` : ''">
          {{ item.value }}
        </div>
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-hint">{{ item.hint }}</div>
      </div>
    </div>

    <div class="alert-bar">
      <button
        v-for="item in alertItems.filter((i) => i.count > 0)"
        :key="item.tab"
        type="button"
        class="alert-chip"
        :class="`is-${item.type}`"
        @click="emit('navigate', item.tab)"
      >
        <span v-if="item.count" class="alert-count">{{ item.count }}</span>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <PlatformAnalyticsCharts
      title="Walmart 数据分析"
      :metric-items="chartMetrics"
      :compare-items="chartCompare"
      compare-title="店铺订单对比"
      compare-value-label="订单"
      :structure-items="chartStructure"
      @navigate="emit('navigate', $event)"
    />

    <el-table
      v-if="showStoreList && storeSummaries.length"
      :data="storeSummaries"
      size="small"
      class="store-table"
      :show-header="storeSummaries.length > 1"
    >
      <el-table-column label="店铺" min-width="140">
        <template #default="{ row }">
          <strong>{{ row.store.storeName }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="96">
        <template #default="{ row }">
          <AssigneeTag :name="resolveStoreAssignee(row.store.id, assigneeMap)" />
        </template>
      </el-table-column>
      <el-table-column label="今日订单" width="90" align="center">
        <template #default="{ row }">{{ row.orders.total }}</template>
      </el-table-column>
      <el-table-column label="待处理" width="80" align="center">
        <template #default="{ row }">
          <el-text :type="row.orders.pending ? 'warning' : 'info'" size="small">
            {{ row.orders.pending }}
          </el-text>
        </template>
      </el-table-column>
      <el-table-column label="Listing" width="80" align="center">
        <template #default="{ row }">
          <el-text :type="row.listings.open ? 'danger' : 'info'" size="small">
            {{ row.listings.open }}
          </el-text>
        </template>
      </el-table-column>
      <el-table-column label="当日金额" width="100" align="right">
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
.wm-overview {
  display: grid;
  gap: 16px;
}
</style>
