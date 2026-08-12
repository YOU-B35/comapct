<script setup>
import { computed } from 'vue'
import { summarizeDtcBySite, summarizeDtcProducts } from '@/utils/dtc'
import { resolveStoreAssignee } from '@/utils/storeAssignment'
import AssigneeTag from '@/components/common/AssigneeTag.vue'
import PlatformAnalyticsCharts from '@/components/charts/PlatformAnalyticsCharts.vue'

const props = defineProps({
  products: { type: Array, required: true },
  sites: { type: Array, default: () => [] },
  assigneeMap: { type: Object, default: () => ({}) },
  showSiteList: { type: Boolean, default: true },
})

const emit = defineEmits(['navigate'])

const overall = computed(() => summarizeDtcProducts(props.products))
const siteSummaries = computed(() => summarizeDtcBySite(props.products, props.sites))

const keyMetrics = computed(() => [
  { label: '今日订单', value: overall.value.dailyOrders, hint: overall.value.dailyRevenueText },
  { label: '今日访客', value: overall.value.dailyViews, hint: `转化 ${overall.value.avgConversion}%` },
  { label: '在售 SKU', value: overall.value.skuCount, hint: props.sites.length > 1 ? `${props.sites.length} 个店铺` : '全站合计' },
  { label: '健康度', value: overall.value.healthScore, hint: overall.value.healthLabel, suffix: '分', type: overall.value.healthType },
])

const alertItems = computed(() => [
  { label: '低库存', count: overall.value.lowStock, tab: 'products', type: 'danger' },
  { label: '滞销', count: overall.value.slowMoving, tab: 'products', type: 'warning' },
  { label: '爆款', count: overall.value.hotProducts, tab: 'products', type: 'success' },
  { label: '营销活动', count: 0, tab: 'campaigns', type: 'primary', hideCount: true },
])

const chartMetrics = computed(() => [
  { name: '今日订单', value: overall.value.dailyOrders },
  { name: '今日访客', value: overall.value.dailyViews },
  { name: '在售 SKU', value: overall.value.skuCount },
  { name: '健康度', value: overall.value.healthScore },
])

const chartStructure = computed(() =>
  alertItems.value
    .filter((i) => !i.hideCount)
    .map((i) => ({
      name: i.label,
      value: i.count,
      tab: i.tab,
      color:
        i.type === 'danger' ? '#ef4444'
          : i.type === 'warning' ? '#f59e0b'
            : i.type === 'success' ? '#10b981'
              : '#3b82f6',
    })),
)

const chartCompare = computed(() =>
  siteSummaries.value.map((row) => ({
    id: row.site.id,
    name: row.site.name,
    value: row.summary.dailyOrders,
  })),
)
</script>

<template>
  <div class="dtc-overview">
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
        v-for="item in alertItems.filter((i) => !i.hideCount || i.count || i.tab === 'campaigns')"
        :key="item.tab"
        type="button"
        class="alert-chip"
        :class="`is-${item.type}`"
        @click="emit('navigate', item.tab)"
      >
        <span v-if="!item.hideCount" class="alert-count">{{ item.count }}</span>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <PlatformAnalyticsCharts
      title="独立站数据分析"
      :metric-items="chartMetrics"
      metric-title="核心指标"
      :compare-items="chartCompare"
      compare-title="站点订单对比"
      compare-value-label="订单"
      :structure-items="chartStructure"
      structure-title="待办结构"
      @navigate="emit('navigate', $event)"
    />

    <el-table
      v-if="showSiteList && siteSummaries.length"
      :data="siteSummaries"
      size="small"
      class="site-table"
      :show-header="siteSummaries.length > 1"
    >
      <el-table-column label="店铺" min-width="140">
        <template #default="{ row }">
          <strong>{{ row.site.name }}</strong>
          <el-text size="small" type="info" tag="p">{{ row.site.domain }}</el-text>
        </template>
      </el-table-column>
      <el-table-column label="平台" width="90">
        <template #default="{ row }">{{ row.site.platform }}</template>
      </el-table-column>
      <el-table-column label="负责人" width="96">
        <template #default="{ row }">
          <AssigneeTag :name="resolveStoreAssignee(row.site.id, assigneeMap)" />
        </template>
      </el-table-column>
      <el-table-column label="健康度" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.summary.healthType" size="small" effect="plain" round>
            {{ row.summary.healthScore }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="日订单" prop="summary.dailyOrders" width="80" align="center" />
      <el-table-column label="日访客" prop="summary.dailyViews" width="90" align="center" />
      <el-table-column label="日销额" width="100" align="right">
        <template #default="{ row }">{{ row.summary.dailyRevenueText }}</template>
      </el-table-column>
      <el-table-column label="SKU" prop="summary.skuCount" width="70" align="center" />
    </el-table>
  </div>
</template>

<style scoped>
.dtc-overview {
  display: grid;
  gap: 16px;
}
</style>
