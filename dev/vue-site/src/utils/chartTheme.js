/** Shared ECharts theme tokens for ops analytics. */

export const CHART_COLORS = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
]

export const CHART_MUTED = '#94a3b8'

export function baseTextStyle() {
  return {
    color: '#64748b',
    fontSize: 12,
  }
}

export function baseTooltip() {
  return {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.88)',
    borderWidth: 0,
    textStyle: { color: '#f8fafc', fontSize: 12 },
    padding: [8, 12],
  }
}

export function baseGrid(extra = {}) {
  return {
    left: 48,
    right: 16,
    top: 36,
    bottom: 28,
    containLabel: true,
    ...extra,
  }
}

export function categoryAxis(data) {
  return {
    type: 'category',
    data,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#e2e8f0' } },
    axisLabel: { color: '#64748b', fontSize: 11 },
  }
}

export function valueAxis(name = '') {
  return {
    type: 'value',
    name,
    nameTextStyle: { color: '#94a3b8', fontSize: 11 },
    splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    axisLabel: { color: '#64748b', fontSize: 11 },
  }
}

export function pieTooltip() {
  return {
    trigger: 'item',
    backgroundColor: 'rgba(15, 23, 42, 0.88)',
    borderWidth: 0,
    textStyle: { color: '#f8fafc', fontSize: 12 },
    formatter: '{b}: {c} ({d}%)',
  }
}

export function emptyOption(message = '暂无数据') {
  return {
    title: {
      text: message,
      left: 'center',
      top: 'middle',
      textStyle: { color: '#94a3b8', fontSize: 13, fontWeight: 400 },
    },
  }
}
