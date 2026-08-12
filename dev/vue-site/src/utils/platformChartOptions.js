import {
  CHART_COLORS,
  baseGrid,
  baseTooltip,
  categoryAxis,
  emptyOption,
  pieTooltip,
  valueAxis,
} from '@/utils/chartTheme'

function markEmpty(option) {
  return { ...option, __empty: true }
}

/**
 * @param {{ name: string, value: number, tab?: string, color?: string }[]} items
 */
export function buildStructurePieOption(items = []) {
  const data = items
    .filter((i) => Number(i.value) > 0)
    .map((i, idx) => ({
      name: i.name,
      value: Number(i.value) || 0,
      tab: i.tab,
      itemStyle: i.color ? { color: i.color } : { color: CHART_COLORS[idx % CHART_COLORS.length] },
    }))
  if (!data.length) return markEmpty(emptyOption('暂无结构数据'))
  return {
    tooltip: pieTooltip(),
    legend: { bottom: 0, type: 'scroll', textStyle: { fontSize: 11 } },
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

/**
 * @param {{ name: string, value: number, id?: string }[]} items
 */
export function buildHorizontalCompareOption(items = [], valueLabel = '') {
  const rows = [...items]
    .filter((i) => i.name)
    .sort((a, b) => (Number(b.value) || 0) - (Number(a.value) || 0))
  if (!rows.length) return markEmpty(emptyOption('暂无对比数据'))
  const names = rows.map((r) => r.name).reverse()
  const values = rows.map((r) => Number(r.value) || 0).reverse()
  const ids = rows.map((r) => r.id).reverse()
  return {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip(), axisPointer: { type: 'shadow' } },
    grid: baseGrid({ left: 8, right: 20 }),
    xAxis: valueAxis(valueLabel),
    yAxis: {
      ...categoryAxis(names),
      axisLabel: { color: '#64748b', fontSize: 10, width: 100, overflow: 'truncate' },
    },
    series: [
      {
        type: 'bar',
        data: values.map((v, i) => ({ value: v, id: ids[i] })),
        barMaxWidth: 18,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
      },
    ],
  }
}

/**
 * @param {{ name: string, value: number }[]} items
 */
export function buildMetricBarsOption(items = []) {
  const rows = items.filter((i) => i.name)
  if (!rows.length) return markEmpty(emptyOption('暂无指标'))
  return {
    color: CHART_COLORS,
    tooltip: baseTooltip(),
    grid: baseGrid(),
    xAxis: categoryAxis(rows.map((r) => r.name)),
    yAxis: valueAxis(),
    series: [
      {
        type: 'bar',
        data: rows.map((r) => Number(r.value) || 0),
        barMaxWidth: 36,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
}
