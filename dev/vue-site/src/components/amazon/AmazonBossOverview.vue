<script setup>
import { computed } from 'vue'
import { summarizeTopProducts, summarizeOutboundOrders, acosMeta, summarizeAccountSnapshot, formatAmazonMoney } from '@/utils/amazonBoss'
import {
  summarizeAccountHealth,
  summarizeBuyerMessages,
  summarizeCases,
  summarizeCoupons,
  summarizeReviews,
  summarizeSellerNews,
  summarizeShipments,
} from '@/utils/amazon'
import { resolveStoreAssignee } from '@/utils/storeAssignment'
import AssigneeTag from '@/components/common/AssigneeTag.vue'
import PlatformAnalyticsCharts from '@/components/charts/PlatformAnalyticsCharts.vue'

const props = defineProps({
  products: { type: Array, default: () => [] },
  outboundOrders: { type: Array, default: () => [] },
  accountMetrics: { type: Array, default: () => [] },
  workflow: { type: Object, default: () => ({}) },
  stores: { type: Array, default: () => [] },
  assigneeMap: { type: Object, default: () => ({}) },
  showStoreList: { type: Boolean, default: true },
})

const emit = defineEmits(['navigate'])

const productSummary = computed(() => summarizeTopProducts(props.products, 20))
const outboundSummary = computed(() => summarizeOutboundOrders(props.outboundOrders))
const accountSnapshot = computed(() => summarizeAccountSnapshot(props.accountMetrics))

const avgAcosMeta = computed(() => acosMeta(productSummary.value.avgAcos))

const keyMetrics = computed(() => {
  const hasValidProducts = productSummary.value.top.length > 0
  const salesFromSnapshot = accountSnapshot.value.salesToday
  const salesFromProducts = productSummary.value.totalRevenueText
  const salesValue = salesFromSnapshot !== '—'
    ? salesFromSnapshot
    : (hasValidProducts ? salesFromProducts : '—')
  return [
  {
    label: '今日销售额',
    value: salesValue,
    hint: salesFromSnapshot !== '—'
      ? '卖家后台全局快照'
      : (hasValidProducts ? `TOP20 合计 · ${productSummary.value.top.length} SKU` : '请先同步 Business Report'),
  },
  {
    label: '平均 ACOS',
    value: accountSnapshot.value.adAcosSnapshot !== '—'
      ? accountSnapshot.value.adAcosSnapshot
      : (productSummary.value.avgAcos ? `${productSummary.value.avgAcos}%` : '—'),
    hint: productSummary.value.hasAdData
      ? `广告花费 ${productSummary.value.totalAdSpendText}`
      : accountSnapshot.value.adSpendToday !== '—'
        ? `广告花费 ${accountSnapshot.value.adSpendToday}`
        : '点击「Business Report 刷新」同步广告数据',
    type: avgAcosMeta.value.type,
  },
  {
    label: '广告花费',
    value: accountSnapshot.value.adSpendToday || productSummary.value.totalAdSpendText,
    hint: accountSnapshot.value.adSpendToday ? '今日 / 广告后台' : 'SKU 维度汇总',
  },
  {
    label: 'ACOS 偏高',
    value: productSummary.value.highAcosCount,
    hint: productSummary.value.dangerAcosCount
      ? `${productSummary.value.dangerAcosCount} 个过高需优化`
      : '关注广告效率',
    type: productSummary.value.highAcosCount ? 'danger' : 'success',
  },
  {
    label: '待发货订单',
    value: outboundSummary.value.actionRequired,
    hint: `FBM ${outboundSummary.value.fbmPending} · FBA ${outboundSummary.value.fbaPending}`,
    type: outboundSummary.value.actionRequired ? 'warning' : 'success',
  },
]
})

const alertItems = computed(() => [
  {
    label: 'ACOS 过高',
    count: productSummary.value.dangerAcosCount,
    tab: 'products:high-acos',
    type: 'danger',
  },
  {
    label: 'ACOS 偏高',
    count: productSummary.value.highAcosCount - productSummary.value.dangerAcosCount,
    tab: 'products',
    type: 'warning',
  },
  {
    label: '待发货',
    count: outboundSummary.value.pending,
    tab: 'outbound',
    type: 'warning',
  },
  {
    label: '待揽收',
    count: outboundSummary.value.packed,
    tab: 'outbound:packed',
    type: 'primary',
  },
  ...workflowAlerts.value,
])

const workflowAlerts = computed(() => {
  const messages = summarizeBuyerMessages(props.workflow.buyerMessages || [])
  const account = summarizeAccountHealth(props.workflow.accountMetrics || [])
  const reviews = summarizeReviews(props.workflow.reviews || [])
  const coupons = summarizeCoupons(props.workflow.coupons || [])
  const news = summarizeSellerNews(props.workflow.sellerNews || [])
  const shipments = summarizeShipments(props.workflow.shipments || [])
  const cases = summarizeCases(props.workflow.cases || [])
  return [
    { label: '待回复', count: messages.pending, tab: 'messages', type: 'warning' },
    {
      label: '账户预警',
      count: account.critical + account.warning,
      tab: 'account',
      type: 'danger',
    },
    { label: '差评', count: reviews.pending, tab: 'reviews', type: 'danger' },
    { label: '优惠券异常', count: coupons.alerts, tab: 'coupons', type: 'warning' },
    { label: '重要通知', count: news.highPriority, tab: 'news', type: 'danger' },
    { label: '缺件/无货', count: shipments.alerts, tab: 'shipments', type: 'danger' },
    { label: 'Case 新回复', count: cases.newReplies, tab: 'cases', type: 'primary' },
  ]
})

const highAcosProducts = computed(() =>
  productSummary.value.top
    .filter((p) => ['warning', 'danger'].includes(acosMeta(p.acos).level))
    .slice(0, 5),
)

const chartMetrics = computed(() => [
  { name: 'ACOS偏高', value: productSummary.value.highAcosCount },
  { name: '待发货', value: outboundSummary.value.actionRequired },
  { name: '待揽收', value: outboundSummary.value.packed },
  { name: 'TOP SKU', value: productSummary.value.top.length },
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
  productSummary.value.top.slice(0, 8).map((p) => ({
    id: p.id,
    name: p.productName || p.asin || 'SKU',
    value: Number(p.sales) || Number(p.orderedUnits) || Number(p.acos) || 0,
  })),
)
</script>

<template>
  <div class="boss-overview">
    <div class="metrics-bar amazon-metrics-bar">
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
        <span class="alert-count">{{ item.count }}</span>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <PlatformAnalyticsCharts
      title="Amazon 数据分析"
      :metric-items="chartMetrics"
      metric-title="核心指标"
      :compare-items="chartCompare"
      compare-title="TOP 产品对比"
      compare-value-label="销量/指标"
      :structure-items="chartStructure"
      structure-title="待办结构"
      @navigate="emit('navigate', $event)"
    />

    <div v-if="highAcosProducts.length" class="acos-alert-card">
      <div class="acos-alert-head">
        <strong>ACOS 需关注</strong>
        <el-button link type="primary" size="small" @click="emit('navigate', 'products:high-acos')">
          查看全部
        </el-button>
      </div>
      <div class="acos-list">
        <div v-for="item in highAcosProducts" :key="item.id" class="acos-row">
          <div class="acos-row__main">
            <span class="acos-rank">#{{ item.displayRank }}</span>
            <span class="acos-name">{{ item.productName }}</span>
          </div>
          <el-tag :type="acosMeta(item.acos).type" size="small">ACOS {{ item.acos }}%</el-tag>
        </div>
      </div>
    </div>

    <el-table
      v-if="showStoreList && stores.length > 1"
      :data="stores"
      size="small"
      class="store-table"
    >
      <el-table-column label="店铺" min-width="140">
        <template #default="{ row }">
          <strong>{{ row.storeName }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="96">
        <template #default="{ row }">
          <AssigneeTag :name="resolveStoreAssignee(row.id, assigneeMap)" />
        </template>
      </el-table-column>
      <el-table-column label="TOP SKU" width="90" align="center">
        <template #default="{ row }">
          {{ products.filter((p) => p.storeId === row.id).length }}
        </template>
      </el-table-column>
      <el-table-column label="待发货" width="80" align="center">
        <template #default="{ row }">
          <el-text
            :type="outboundOrders.filter((o) => o.storeId === row.id && ['pending', 'packed'].includes(o.status)).length ? 'warning' : 'info'"
            size="small"
          >
            {{
              outboundOrders.filter((o) => o.storeId === row.id && ['pending', 'packed'].includes(o.status)).length
            }}
          </el-text>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.boss-overview {
  display: grid;
  gap: 16px;
}

.amazon-metrics-bar {
  grid-template-columns: repeat(5, 1fr);
}

.amazon-metrics-bar .metric-value {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum';
}

@media (max-width: 960px) {
  .amazon-metrics-bar {
    grid-template-columns: repeat(2, 1fr);
  }
}

.acos-alert-card {
  padding: 14px 16px;
  border-radius: var(--ch-radius-md);
  border: 1px solid #f3d0d8;
  background: linear-gradient(180deg, #fff7f8 0%, #fff 75%);
}

.acos-alert-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.acos-list {
  display: grid;
  gap: 8px;
}

.acos-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.acos-row__main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.acos-rank {
  font-weight: 600;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.acos-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
