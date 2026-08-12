<script setup>
import { computed } from 'vue'
import { summarizeTemuByStore, summarizeTemuProducts } from '@/utils/temuStore'
import { formatMoney } from '@/utils/format'
import { resolveStoreAssignee } from '@/utils/storeAssignment'
import AssigneeTag from '@/components/common/AssigneeTag.vue'
import TemuAnalyticsCharts from '@/components/temu/TemuAnalyticsCharts.vue'

const props = defineProps({
  products: { type: Array, required: true },
  stores: { type: Array, default: () => [] },
  assigneeMap: { type: Object, default: () => ({}) },
  showStoreList: { type: Boolean, default: true },
  storeName: { type: String, default: '' },
  salesTrend: { type: Object, default: () => ({ labels: [], values: [] }) },
})

const emit = defineEmits(['navigate', 'select-store'])

const overall = computed(() => summarizeTemuProducts(props.products))

const storeSummaries = computed(() => summarizeTemuByStore(props.products, props.stores))

const keyMetrics = computed(() => [
  {
    label: '今日销量',
    value: overall.value.dailySales,
    hint: overall.value.dailyRevenueText,
  },
  {
    label: '官方仓库存',
    value: overall.value.officialStock,
    hint: '件',
  },
  {
    label: '在线产品',
    value: overall.value.onlineCount,
    hint: overall.value.onlineHint,
  },
])

const alertItems = computed(() => [
  { label: '亏损', count: overall.value.lossCount, tab: 'profit', type: 'danger' },
  { label: '滞销', count: overall.value.slowCount, tab: 'slow', type: 'warning' },
  { label: '爆款', count: overall.value.hotCount, tab: 'hot', type: 'success' },
  { label: '待备货', count: overall.value.restockCount, tab: 'restock', type: 'primary' },
])

function storeAlerts(summary) {
  const items = []
  if (summary.lossCount) items.push({ text: `亏损 ${summary.lossCount}`, type: 'danger' })
  if (summary.slowCount) items.push({ text: `滞销 ${summary.slowCount}`, type: 'warning' })
  if (summary.hotCount) items.push({ text: `爆款 ${summary.hotCount}`, type: 'success' })
  if (summary.restockCount) items.push({ text: `待备货 ${summary.restockCount}`, type: 'info' })
  return items
}
</script>

<template>
  <div class="boss-overview">
    <div class="metrics-bar metrics-bar--3">
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
        v-for="item in alertItems"
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

    <TemuAnalyticsCharts
      :products="products"
      :stores="stores"
      :sales-trend="salesTrend"
      :store-name="storeName"
      @navigate="emit('navigate', $event)"
      @select-store="emit('select-store', $event)"
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
      <el-table-column label="在线" prop="summary.onlineCount" width="72" align="center" />
      <el-table-column label="SKU" prop="summary.skuCount" width="72" align="center" />
      <el-table-column label="日销" prop="summary.dailySales" width="72" align="center" />
      <el-table-column label="日销额" width="100" align="right">
        <template #default="{ row }">
          {{ formatMoney(row.summary.dailyRevenue) }}
        </template>
      </el-table-column>
      <el-table-column label="异常" min-width="160">
        <template #default="{ row }">
          <el-space v-if="storeAlerts(row.summary).length" wrap :size="4">
            <el-tag
              v-for="tag in storeAlerts(row.summary)"
              :key="tag.text"
              :type="tag.type"
              size="small"
            >
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
.boss-overview {
  display: grid;
  gap: 16px;
}
</style>
