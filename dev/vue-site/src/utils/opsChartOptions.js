import {
  CHART_COLORS,
  baseGrid,
  baseTooltip,
  categoryAxis,
  emptyOption,
  pieTooltip,
  valueAxis,
} from '@/utils/chartTheme'
import { calcTaskStats } from '@/utils/operations'

function markEmpty(option) {
  return { ...option, __empty: true }
}

export function buildPlatformRevenueOption(platformSales = []) {
  const rows = platformSales.filter((r) => r.name)
  if (!rows.length) return markEmpty(emptyOption('暂无平台销售数据'))
  const names = rows.map((r) => r.name)
  const revenues = rows.map((r) => ({
    value: Number(r.revenue) || 0,
    platformId: r.id,
  }))
  const orders = rows.map((r) => ({
    value: Number(r.orders) || 0,
    platformId: r.id,
  }))
  return {
    color: CHART_COLORS,
    tooltip: baseTooltip(),
    legend: { data: ['销售额', '订单/销量'], top: 0, textStyle: { fontSize: 11 } },
    grid: baseGrid({ top: 40 }),
    xAxis: categoryAxis(names),
    yAxis: [valueAxis('额'), { ...valueAxis('量'), splitLine: { show: false } }],
    series: [
      {
        name: '销售额',
        type: 'bar',
        data: revenues,
        barMaxWidth: 36,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '订单/销量',
        type: 'line',
        yAxisIndex: 1,
        data: orders,
        smooth: true,
        symbolSize: 6,
      },
    ],
  }
}

export function buildPlatformAlertsOption(platformSales = [], overview = null) {
  const rows = (platformSales || []).map((row) => {
    const platform = overview?.platforms?.find((p) => p.id === row.id)
    return {
      id: row.id,
      name: row.name,
      value: Number(platform?.issueCount ?? row.alerts ?? 0) || 0,
    }
  }).filter((r) => r.value > 0)
  if (!rows.length) {
    return {
      color: CHART_COLORS,
      tooltip: pieTooltip(),
      series: [
        {
          type: 'pie',
          radius: ['48%', '70%'],
          data: [{ name: '无待跟进', value: 1, itemStyle: { color: '#10b981' } }],
          label: { formatter: '运行正常' },
        },
      ],
    }
  }
  return {
    color: CHART_COLORS,
    tooltip: pieTooltip(),
    legend: { bottom: 0, type: 'scroll', textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '46%'],
        data: rows.map((r) => ({ name: r.name, value: r.value, platformId: r.id })),
        label: { fontSize: 11 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.15)' } },
      },
    ],
  }
}

export function buildTaskStatusOption(tasks = []) {
  const stats = calcTaskStats(tasks)
  const data = [
    { name: '待处理', value: stats.pending, itemStyle: { color: '#f59e0b' } },
    { name: '进行中', value: stats.inProgress, itemStyle: { color: '#3b82f6' } },
    { name: '已完成', value: stats.completed, itemStyle: { color: '#10b981' } },
    { name: '已逾期', value: stats.overdue, itemStyle: { color: '#ef4444' } },
  ].filter((d) => d.value > 0)
  if (!data.length) return markEmpty(emptyOption('暂无任务数据'))
  return {
    tooltip: pieTooltip(),
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '46%'],
        data,
        label: { formatter: '{b}\n{c}', fontSize: 11 },
      },
    ],
  }
}
