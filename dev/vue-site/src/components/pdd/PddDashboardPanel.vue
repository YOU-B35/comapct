<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useEcharts } from '@/composables/useEcharts'
import { formatMoney } from '@/utils/format'
import {
  fetchPddOrderOverview,
  fetchPddOrderSummary,
  fetchPddOrderTrend,
} from '@/api/pddApi'

const props = defineProps({
  backendReady: { type: Boolean, default: false },
  stores: { type: Array, default: () => [] },
  selectedStoreId: { type: String, default: 'all' },
  syncing: { type: Boolean, default: false },
})

const emit = defineEmits(['sync'])

const PRESETS = [
  { key: 'today', label: '今日' },
  { key: 'yesterday', label: '昨日' },
  { key: 'd7', label: '近7日' },
  { key: 'd30', label: '近30日' },
  { key: 'd90', label: '近90日' },
  { key: 'custom', label: '自定义' },
]

const preset = ref('today')
const customRange = ref([])
const loading = ref(false)
const summary = ref(null)
const trend = ref([])
const overview = ref(null)
const trendEl = ref(null)

function setPreset(key) {
  if (!PRESETS.some((p) => p.key === key)) return
  preset.value = key
  void load()
}

function dateText(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function rangeOf() {
  if (preset.value === 'custom') {
    if (customRange.value?.length === 2) {
      return [customRange.value[0], customRange.value[1]]
    }
    return [dateText(0), dateText(0)]
  }
  if (preset.value === 'yesterday') return [dateText(-1), dateText(-1)]
  if (preset.value === 'd7') return [dateText(-6), dateText(0)]
  if (preset.value === 'd30') return [dateText(-29), dateText(0)]
  if (preset.value === 'd90') return [dateText(-89), dateText(0)]
  return [dateText(0), dateText(0)]
}

async function load() {
  if (!props.backendReady || !props.stores.length) {
    summary.value = null
    trend.value = []
    overview.value = null
    return
  }
  loading.value = true
  try {
    const [start, end] = rangeOf()
    if (props.selectedStoreId === 'all') {
      overview.value = await fetchPddOrderOverview({ startDate: start, endDate: end })
    } else {
      overview.value = null
    }
    const [summaryRes, trendRes] = await Promise.all([
      fetchPddOrderSummary({ startDate: start, endDate: end, storeId: props.selectedStoreId }),
      fetchPddOrderTrend({ startDate: start, endDate: end, storeId: props.selectedStoreId }),
    ])
    summary.value = summaryRes || null
    trend.value = Array.isArray(trendRes) ? trendRes : []
  } catch (error) {
    summary.value = null
    trend.value = []
    overview.value = null
    ElMessage.error(error?.message || '加载拼多多经营驾驶舱失败')
  } finally {
    loading.value = false
  }
}

const metrics = computed(() => {
  const s = summary.value || {}
  return [
    { label: '净销售额', value: formatMoney(Number(s.net_sales) || 0), hint: '支付销售额 - 退款' },
    { label: '支付销售额', value: formatMoney(Number(s.paid_sales) || 0), hint: '已支付订单实付合计' },
    { label: '支付订单数', value: Number(s.paid_order_count) || 0, hint: '已支付去重订单' },
    { label: '退款金额', value: formatMoney(Number(s.refund_amount) || 0), hint: '退款发生日合计' },
    { label: '退款订单数', value: Number(s.refund_order_count) || 0, hint: '发生退款的订单' },
    { label: '客单价', value: formatMoney(Number(s.average_order_value) || 0), hint: '支付销售额 / 订单数' },
    { label: '销售件数', value: Number(s.sold_quantity) || 0, hint: '已支付订单商品件数' },
    { label: '销售商品数', value: Number(s.sold_product_count) || 0, hint: '去重商品数' },
  ]
})

const overviewStores = computed(() => {
  const list = Array.isArray(overview.value?.stores) ? overview.value.stores : []
  return list.map((row) => {
    const store = props.stores.find((s) => s.id === row.store_id)
    return {
      storeId: row.store_id,
      storeName: store?.storeName || row.store_id,
      paidSales: Number(row.paid_sales) || 0,
      refundAmount: Number(row.refund_amount) || 0,
      netSales: Number(row.net_sales) || 0,
      paidOrderCount: Number(row.paid_order_count) || 0,
      refundOrderCount: Number(row.refund_order_count) || 0,
      averageOrderValue: Number(row.average_order_value) || 0,
      soldQuantity: Number(row.sold_quantity) || 0,
      soldProductCount: Number(row.sold_product_count) || 0,
    }
  })
})

const overviewTotals = computed(() => ({
  paidSales: Number(overview.value?.total_paid_sales) || 0,
  refundAmount: Number(overview.value?.total_refund_amount) || 0,
  netSales: Number(overview.value?.total_net_sales) || 0,
  paidOrderCount: Number(overview.value?.total_paid_order_count) || 0,
  refundOrderCount: Number(overview.value?.total_refund_order_count) || 0,
  storeCount: Number(overview.value?.store_count) || 0,
}))

const trendOption = computed(() => ({
  color: ['#1f4fd6', '#10b981', '#f59e0b'],
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(255,255,255,0.96)',
    borderColor: '#e5e7eb',
    textStyle: { color: '#1f2937' },
    axisPointer: { type: 'line', lineStyle: { color: '#d1d5db', type: 'dashed' } },
    formatter(params) {
      if (!Array.isArray(params)) return ''
      const first = params[0]
      const lines = [`<b>${first.axisValueLabel}</b>`]
      for (const p of params) {
        const value = Number(p.value) || 0
        const text = p.seriesName === '订单数'
          ? `${value} 单`
          : '¥' + value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
        lines.push(`${p.marker}${p.seriesName}：${text}`)
      }
      return lines.join('<br/>')
    },
  },
  legend: {
    data: ['支付销售额', '净销售额', '订单数'],
    top: 4,
    right: 8,
    itemWidth: 16,
    itemHeight: 8,
    textStyle: { color: '#6b7280', fontSize: 12 },
  },
  grid: { left: 10, right: 12, top: 34, bottom: 4, containLabel: true },
  xAxis: {
    type: 'category',
    boundaryGap: true,
    data: trend.value.map((d) => String(d.date || '').slice(5)),
    axisLine: { lineStyle: { color: '#e5e7eb' } },
    axisTick: { show: false },
    axisLabel: { color: '#9ca3af', fontSize: 11 },
  },
  yAxis: [
    {
      type: 'value',
      splitLine: { lineStyle: { color: '#f3f4f6' } },
      axisLabel: {
        color: '#9ca3af',
        fontSize: 11,
        formatter(value) {
          if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(1)}万`
          return value
        },
      },
    },
    {
      type: 'value',
      splitLine: { show: false },
      axisLabel: { color: '#9ca3af', fontSize: 11 },
    },
  ],
  series: [
    {
      name: '支付销售额',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { width: 2.5 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(31,79,214,0.18)' },
            { offset: 1, color: 'rgba(31,79,214,0.02)' },
          ],
        },
      },
      data: trend.value.map((d) => Number(d.paid_sales) || 0),
    },
    {
      name: '净销售额',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { width: 2.5 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(16,185,129,0.16)' },
            { offset: 1, color: 'rgba(16,185,129,0.02)' },
          ],
        },
      },
      data: trend.value.map((d) => Number(d.net_sales) || 0),
    },
    {
      name: '订单数',
      type: 'bar',
      yAxisIndex: 1,
      barMaxWidth: 14,
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      data: trend.value.map((d) => Number(d.paid_order_count) || 0),
    },
  ],
}))

useEcharts(trendEl, trendOption)

watch(() => [props.backendReady, props.stores.length, props.selectedStoreId, preset.value], () => void load())
watch(customRange, () => {
  if (preset.value === 'custom') void load()
})

onMounted(() => void load())

defineExpose({ load, setPreset })
</script>

<template>
  <div class="pdd-dashboard">
    <div class="toolbar">
      <el-radio-group v-model="preset" size="small">
        <el-radio-button v-for="p in PRESETS" :key="p.key" :value="p.key">{{ p.label }}</el-radio-button>
      </el-radio-group>
      <el-date-picker
        v-if="preset === 'custom'"
        v-model="customRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        size="small"
      />
      <div class="toolbar-actions">
        <el-button size="small" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" size="small" :loading="syncing" @click="emit('sync')">同步订单</el-button>
      </div>
    </div>

    <div v-loading="loading" class="metric-grid">
      <div v-for="m in metrics" :key="m.label" class="metric-card">
        <div class="metric-label">{{ m.label }}</div>
        <div class="metric-value">{{ m.value }}</div>
        <div class="metric-hint">{{ m.hint }}</div>
      </div>
    </div>

    <el-card v-if="selectedStoreId === 'all' && overviewStores.length" shadow="never" class="store-overview-card">
      <template #header>店铺经营总览（{{ overviewTotals.storeCount }} 家店铺）</template>
      <el-table :data="overviewStores" size="small" stripe>
        <el-table-column prop="storeName" label="店铺" min-width="140" show-overflow-tooltip />
        <el-table-column label="净销售额" align="right">
          <template #default="{ row }">{{ formatMoney(row.netSales) }}</template>
        </el-table-column>
        <el-table-column label="支付销售额" align="right">
          <template #default="{ row }">{{ formatMoney(row.paidSales) }}</template>
        </el-table-column>
        <el-table-column label="退款金额" align="right">
          <template #default="{ row }">{{ formatMoney(row.refundAmount) }}</template>
        </el-table-column>
        <el-table-column prop="paidOrderCount" label="支付订单" align="right" />
        <el-table-column prop="refundOrderCount" label="退款订单" align="right" />
        <el-table-column label="客单价" align="right">
          <template #default="{ row }">{{ formatMoney(row.averageOrderValue) }}</template>
        </el-table-column>
        <el-table-column prop="soldQuantity" label="销售件数" align="right" />
      </el-table>
      <div class="store-total-row">
        合计：净销售额 {{ formatMoney(overviewTotals.netSales) }}· 支付销售额 {{ formatMoney(overviewTotals.paidSales) }}· 退款 {{ formatMoney(overviewTotals.refundAmount) }}· 支付订单 {{ overviewTotals.paidOrderCount }}单 · 退款订单 {{ overviewTotals.refundOrderCount }}单
      </div>
    </el-card>

    <el-card shadow="never" class="trend-card">
      <template #header>销售额 / 订单趋势</template>
      <div ref="trendEl" class="trend-chart" />
    </el-card>
  </div>
</template>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 16px; }
.toolbar-actions { display: flex; gap: 8px; margin-left: auto; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.metric-card { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 14px; }
.metric-label { color: var(--el-text-color-secondary); font-size: 13px; }
.metric-value { font-size: 22px; font-weight: 600; margin: 6px 0; }
.metric-hint { color: var(--el-text-color-placeholder); font-size: 12px; }
.trend-card { margin-top: 16px; }
.trend-chart { height: 320px; }
.store-overview-card { margin-top: 16px; }
.store-total-row { margin-top: 10px; color: var(--el-text-color-secondary); font-size: 13px; text-align: right; }
</style>
