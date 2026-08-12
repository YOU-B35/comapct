import {
  CHART_COLORS,
  CHART_MUTED,
  baseGrid,
  baseTooltip,
  categoryAxis,
  emptyOption,
  pieTooltip,
  valueAxis,
} from '@/utils/chartTheme'
import { summarizeTemuByStore, summarizeTemuProducts } from '@/utils/temuStore'

function markEmpty(option) {
  return { ...option, __empty: true }
}

export function buildTemuSalesTrendOption(salesTrend = {}) {
  const labels = salesTrend.labels || []
  const values = salesTrend.values || []
  const estimated = salesTrend.estimated || []
  if (!labels.length) return markEmpty(emptyOption('暂无近 7 日销量'))

  const actual = values.map((v, i) => (estimated[i] ? null : v))
  const estSeries = values.map((v, i) => (estimated[i] ? v : null))

  return {
    color: [CHART_COLORS[0], CHART_MUTED],
    tooltip: {
      ...baseTooltip(),
      formatter(params) {
        const list = Array.isArray(params) ? params : [params]
        const idx = list[0]?.dataIndex ?? 0
        const label = labels[idx]
        const val = values[idx] ?? 0
        const tip = estimated[idx] ? '（估算回填）' : ''
        return `${label}<br/>销量：${val}${tip}`
      },
    },
    legend: { data: ['销量', '估算'], top: 0, textStyle: { fontSize: 11 } },
    grid: baseGrid({ top: 40 }),
    xAxis: categoryAxis(labels),
    yAxis: valueAxis(),
    series: [
      {
        name: '销量',
        type: 'bar',
        data: actual,
        barMaxWidth: 28,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '估算',
        type: 'line',
        data: estSeries,
        connectNulls: false,
        symbol: 'diamond',
        lineStyle: { type: 'dashed', color: CHART_MUTED },
        itemStyle: { color: CHART_MUTED },
      },
    ],
  }
}

export function buildTemuStoreSalesOption(products = [], stores = []) {
  const rows = summarizeTemuByStore(products, stores)
    .map((r) => ({
      storeId: r.store.id,
      name: r.store.storeName,
      value: r.summary.dailySales || 0,
      revenue: r.summary.dailyRevenue || 0,
    }))
    .sort((a, b) => b.value - a.value)
  if (!rows.length) return markEmpty(emptyOption('暂无店铺销量'))
  const names = rows.map((r) => r.name).reverse()
  const values = rows.map((r) => r.value).reverse()
  const ids = rows.map((r) => r.storeId).reverse()
  return {
    color: CHART_COLORS,
    tooltip: {
      ...baseTooltip(),
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    grid: baseGrid({ left: 16, right: 24 }),
    xAxis: valueAxis(),
    yAxis: categoryAxis(names),
    series: [
      {
        type: 'bar',
        data: values.map((v, i) => ({ value: v, storeId: ids[i] })),
        barMaxWidth: 18,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
      },
    ],
  }
}

export function buildTemuAlertStructureOption(products = []) {
  const s = summarizeTemuProducts(products)
  const data = [
    { name: '亏损', value: s.lossCount, tab: 'profit', itemStyle: { color: '#ef4444' } },
    { name: '滞销', value: s.slowCount, tab: 'slow', itemStyle: { color: '#f59e0b' } },
    { name: '爆款', value: s.hotCount, tab: 'hot', itemStyle: { color: '#10b981' } },
    { name: '待备货', value: s.restockCount, tab: 'restock', itemStyle: { color: '#3b82f6' } },
  ].filter((d) => d.value > 0)
  if (!data.length) return markEmpty(emptyOption('暂无异常结构'))
  return {
    tooltip: pieTooltip(),
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['40%', '66%'],
        center: ['50%', '46%'],
        data,
        label: { fontSize: 11 },
      },
    ],
  }
}

function topNBarOption(items, { empty = '暂无数据', valueLabel = '值' } = {}) {
  if (!items.length) return markEmpty(emptyOption(empty))
  const names = items.map((i) => i.name).reverse()
  const values = items.map((i) => i.value).reverse()
  return {
    color: CHART_COLORS,
    tooltip: baseTooltip(),
    grid: baseGrid({ left: 8, right: 20 }),
    xAxis: valueAxis(valueLabel),
    yAxis: {
      ...categoryAxis(names),
      axisLabel: {
        color: '#64748b',
        fontSize: 10,
        width: 96,
        overflow: 'truncate',
      },
    },
    series: [
      {
        type: 'bar',
        data: values.map((v, i) => ({
          value: v,
          sku: items[items.length - 1 - i]?.sku,
          id: items[items.length - 1 - i]?.id,
        })),
        barMaxWidth: 16,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
      },
    ],
  }
}

export function buildTemuLossTopOption(products = [], limit = 8) {
  const items = products
    .filter((p) => p.isLoss && p.hasCost)
    .map((p) => ({
      id: p.id || p.sku,
      sku: p.sku,
      name: p.sku || p.name || 'SKU',
      value: Math.round(Math.abs(p.unitProfit || 0) * Math.max(p.officialStock || 0, 1) * 100) / 100,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit)
  return topNBarOption(items, { empty: '暂无亏损 SKU', valueLabel: '潜在亏损' })
}

export function buildTemuSlowDistOption(products = []) {
  const buckets = [
    { name: '15–29 日', value: products.filter((p) => p.daysWithoutSale >= 15 && p.daysWithoutSale < 30).length },
    { name: '30–44 日', value: products.filter((p) => p.daysWithoutSale >= 30 && p.daysWithoutSale < 45).length },
    { name: '≥45 日', value: products.filter((p) => p.daysWithoutSale >= 45).length },
  ]
  if (!buckets.some((b) => b.value > 0)) return markEmpty(emptyOption('暂无滞销分布'))
  return {
    color: ['#fbbf24', '#f59e0b', '#ef4444'],
    tooltip: baseTooltip(),
    grid: baseGrid(),
    xAxis: categoryAxis(buckets.map((b) => b.name)),
    yAxis: valueAxis('SKU'),
    series: [
      {
        type: 'bar',
        data: buckets.map((b) => b.value),
        barMaxWidth: 36,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
}

export function buildTemuHotTopOption(products = [], limit = 8) {
  const items = products
    .filter((p) => p.isHot)
    .map((p) => ({
      id: p.id || p.sku,
      sku: p.sku,
      name: p.sku || p.name || 'SKU',
      value: Number(p.dailySales) || 0,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit)
  return topNBarOption(items, { empty: '暂无爆款', valueLabel: '日销' })
}

export function buildTemuRestockTopOption(products = [], limit = 8) {
  const rank = { critical: 3, warning: 2, watch: 1 }
  const items = products
    .filter((p) => p.restock && (p.restock.urgency === 'critical' || p.restock.urgency === 'warning'))
    .map((p) => ({
      id: p.id || p.sku,
      sku: p.sku,
      name: p.sku || p.name || 'SKU',
      value: Number(p.restock?.suggestQty) || Number(p.restock?.suggestedQty) || rank[p.restock.urgency] || 1,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit)
  return topNBarOption(items, { empty: '暂无待备货', valueLabel: '建议量' })
}
