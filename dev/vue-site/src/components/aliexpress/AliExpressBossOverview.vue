<script setup>
import { computed } from 'vue'
import { summarizeAliExpressByStore, summarizeAliExpressOrders, summarizeAliExpressProducts, summarizeAliExpressViolations } from '@/utils/aliexpress'
import { resolveStoreAssignee } from '@/utils/storeAssignment'
import AssigneeTag from '@/components/common/AssigneeTag.vue'
import PlatformAnalyticsCharts from '@/components/charts/PlatformAnalyticsCharts.vue'

const props = defineProps({
  orders: { type: Array, default: () => [] },
  violations: { type: Array, default: () => [] },
  products: { type: Array, default: () => [] },
  stores: { type: Array, default: () => [] },
  assigneeMap: { type: Object, default: () => ({}) },
  showStoreList: { type: Boolean, default: true },
})

const emit = defineEmits(['navigate'])

const orderSummary = computed(() => summarizeAliExpressOrders(props.orders))
const violationSummary = computed(() => summarizeAliExpressViolations(props.violations))
const productSummary = computed(() => summarizeAliExpressProducts(props.products))
const storeSummaries = computed(() =>
  summarizeAliExpressByStore(props.orders, props.violations, props.products, props.stores),
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
    hint: `JIT ${orderSummary.value.jitPending} · 仓发 ${orderSummary.value.warehousePending}`,
    type: orderSummary.value.pending ? 'warning' : undefined,
  },
  {
    label: '违规待确认',
    value: violationSummary.value.pending,
    hint: violationSummary.value.totalFineText,
    type: violationSummary.value.pending ? 'danger' : undefined,
  },
  {
    label: '运营健康度',
    value: violationSummary.value.healthScore,
    hint: violationSummary.value.healthLabel,
    suffix: '分',
    type: violationSummary.value.healthType,
  },
])

const alertItems = computed(() => [
  { label: '待处理订单', count: orderSummary.value.pending, tab: 'orders', type: 'warning' },
  { label: '违规待确认', count: violationSummary.value.pending, tab: 'violations', type: 'danger' },
  { label: '申诉跟进', count: violationSummary.value.appealPending, tab: 'violations:pending', type: 'primary' },
  { label: '爆款 SKU', count: productSummary.value.hotCount, tab: 'hot', type: 'success' },
])

function storeAlerts(row) {
  const items = []
  if (row.orders.pending) items.push({ text: `待处理 ${row.orders.pending}`, type: 'warning' })
  if (row.violations.pending) items.push({ text: `违规 ${row.violations.pending}`, type: 'danger' })
  if (row.violations.appealPending) items.push({ text: `申诉中 ${row.violations.appealPending}`, type: 'primary' })
  if (row.products.hotCount) items.push({ text: `爆款 ${row.products.hotCount}`, type: 'success' })
  return items
}

const chartMetrics = computed(() => [
  { name: '今日订单', value: orderSummary.value.total },
  { name: '待处理', value: orderSummary.value.pending },
  { name: '违规待确认', value: violationSummary.value.pending },
  { name: '健康度', value: violationSummary.value.healthScore },
])

const chartStructure = computed(() =>
  alertItems.value.map((i) => ({
    name: i.label,
    value: i.count,
    tab: i.tab,
    color: i.type === 'danger' ? '#ef4444' : i.type === 'warning' ? '#f59e0b' : i.type === 'success' ? '#10b981' : '#3b82f6',
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
  <div class="ae-overview">
    <div class="metrics-bar metrics-bar--4">
      <div v-for="item in keyMetrics" :key="item.label" class="metric-item">
        <div class="metric-value" :class="item.type ? `is-${item.type}` : ''">
          {{ item.value }}<small v-if="item.suffix">{{ item.suffix }}</small>
        </div>
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-hint">{{ item.hint }}</div>
      </div>
    </div>

    <div class="alert-bar">
      <button
        v-for="item in alertItems.filter((i) => i.count > 0 || i.tab === 'hot')"
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
      title="AliExpress 数据分析"
      :metric-items="chartMetrics"
      metric-title="核心指标"
      :compare-items="chartCompare"
      compare-title="店铺订单对比"
      compare-value-label="订单"
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
      <el-table-column label="违规" width="70" align="center">
        <template #default="{ row }">
          <el-text :type="row.violations.pending ? 'danger' : 'info'" size="small">
            {{ row.violations.pending }}
          </el-text>
        </template>
      </el-table-column>
      <el-table-column label="罚款" width="100" align="right">
        <template #default="{ row }">{{ row.violations.totalFineText }}</template>
      </el-table-column>
      <el-table-column label="SKU" prop="products.skuCount" width="70" align="center" />
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
.ae-overview {
  display: grid;
  gap: 16px;
}
</style>
