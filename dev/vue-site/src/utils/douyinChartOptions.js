/**
 * Douyin cockpit charts (preview v4 aligned):
 * - trend: dual-axis line across compare periods (时段对比)
 * - funnel / carrier: selected-period funnel / donut
 */
import {
  baseGrid,
  baseTooltip,
  categoryAxis,
  emptyOption,
  pieTooltip,
  valueAxis,
} from './chartTheme.js'

const BLUE_RAMP = ['#1f4fd6', '#4d73e0', '#7a97e8', '#a7bbef']
const PERIOD_META = [
  { key: 'realtime', dateType: 1, label: '今日实时' },
  { key: 'd1', dateType: 20, label: '昨日' },
  { key: 'd7', dateType: 21, label: '近7天' },
  { key: 'd30', dateType: 23, label: '近30天' },
]

function markEmpty(option) {
  return { ...option, __empty: true }
}

function num(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/**
 * 按当前选中时段决定折线对比集：
 * - 今日实时 / 昨日 → 今日 vs 昨日
 * - 近7天 → 今日 + 昨日 + 近7天
 * - 近30天 → 四档全对比
 */
export function resolveComparePeriods(periodKey = 'realtime') {
  if (periodKey === 'd30') return PERIOD_META.slice()
  if (periodKey === 'd7') return PERIOD_META.filter((p) => p.key !== 'd30')
  return PERIOD_META.filter((p) => p.key === 'realtime' || p.key === 'd1')
}

export function pickSnapshotsByPeriod(snapshots = [], periodKey = 'realtime') {
  const list = Array.isArray(snapshots) ? snapshots : []
  return resolveComparePeriods(periodKey)
    .map((meta) => {
      const snapshot = list.find((s) => Number(s.dateType) === meta.dateType) || null
      return { ...meta, snapshot }
    })
    .filter((row) => row.snapshot)
}

export function pickSelectedSnapshot(snapshots = [], periodKey = 'realtime') {
  const list = Array.isArray(snapshots) ? snapshots : []
  const meta = PERIOD_META.find((p) => p.key === periodKey) || PERIOD_META[0]
  return list.find((s) => Number(s.dateType) === meta.dateType) || null
}

function funnelStages(snapshot) {
  const show = num(snapshot?.productShowCnt) ?? num(snapshot?.productShowUcnt)
  const click = num(snapshot?.productClickCnt) ?? num(snapshot?.productClickUcnt)
  const deal = num(snapshot?.payUcnt) ?? num(snapshot?.payCnt)
  const data = []
  if (show != null && show > 0) data.push({ name: '曝光', value: show })
  if (click != null && click > 0) data.push({ name: '点击', value: click })
  if (deal != null && deal > 0) data.push({ name: '成交', value: deal })
  return data
}

/**
 * 成交趋势：双轴折线，横轴为对比时段（体现时段对比）
 * 当前选中时段的数据点加大，便于对照旁侧指标
 * @param {unknown[]} snapshots
 * @param {string} periodKey
 */
export function buildDouyinTrendOption(snapshots, periodKey = 'realtime') {
  const rows = pickSnapshotsByPeriod(snapshots, periodKey)
  if (!rows.length) return markEmpty(emptyOption('暂无数据'))

  const categories = rows.map((r) => r.label)
  const point = (value, row) => ({
    value,
    symbolSize: row.key === periodKey ? 10 : 6,
  })
  const pay = rows.map((r) => point(num(r.snapshot?.payAmt), r))
  const orders = rows.map((r) => point(num(r.snapshot?.payCnt), r))
  const hasAny = pay.some((p) => p.value != null) || orders.some((p) => p.value != null)
  if (!hasAny) return markEmpty(emptyOption('暂无数据'))

  return {
    color: ['#1f4fd6', '#6a7689'],
    tooltip: {
      ...baseTooltip(),
      trigger: 'axis',
    },
    legend: {
      data: ['支付金额', '成交订单'],
      top: 4,
      right: 8,
      textStyle: { color: '#6a7689', fontSize: 12 },
    },
    grid: baseGrid({ left: 52, right: 40, top: 40, bottom: 28 }),
    xAxis: {
      ...categoryAxis(categories),
      boundaryGap: false,
    },
    yAxis: [
      {
        ...valueAxis(),
        splitLine: { lineStyle: { color: '#f0f2f5' } },
      },
      {
        ...valueAxis(),
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '支付金额',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: pay,
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(31,79,214,0.18)' },
              { offset: 1, color: 'rgba(31,79,214,0.01)' },
            ],
          },
        },
      },
      {
        name: '成交订单',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        symbol: 'circle',
        symbolSize: 6,
        data: orders,
      },
    ],
  }
}

/**
 * 转化漏斗：仅当前选中时段
 * @param {unknown[]} snapshots
 * @param {string} periodKey
 */
export function buildDouyinFunnelOption(snapshots, periodKey = 'realtime') {
  const snapshot = pickSelectedSnapshot(snapshots, periodKey)
  if (!snapshot) return markEmpty(emptyOption('暂无数据'))

  const data = funnelStages(snapshot)
  if (data.length < 2) return markEmpty(emptyOption('暂无数据'))

  return {
    color: BLUE_RAMP,
    tooltip: { trigger: 'item', formatter: '{b}<br/>{c}' },
    series: [
      {
        type: 'funnel',
        left: '6%',
        width: '72%',
        top: 20,
        bottom: 12,
        minSize: '18%',
        maxSize: '100%',
        sort: 'descending',
        gap: 4,
        label: {
          show: true,
          position: 'inside',
          formatter: '{b}\n{c}',
          color: '#fff',
          fontWeight: 600,
          fontSize: 12,
        },
        itemStyle: { borderColor: '#fff', borderWidth: 1 },
        data,
      },
    ],
  }
}

/**
 * 载体结构：仅当前选中时段环图
 * @param {unknown[]} snapshots
 * @param {string} periodKey
 */
export function buildDouyinCarrierOption(snapshots, periodKey = 'realtime') {
  const snapshot = pickSelectedSnapshot(snapshots, periodKey)
  if (!snapshot) return markEmpty(emptyOption('暂无数据'))

  const carriers = Array.isArray(snapshot.carriers) ? snapshot.carriers : []
  const data = carriers
    .map((c) => {
      const value = num(c.pay_amt) ?? num(c.payAmt) ?? num(c.ratio)
      return { name: c.name || '其他', value: value == null ? 0 : value }
    })
    .filter((d) => d.value > 0)
  if (!data.length) return markEmpty(emptyOption('暂无数据'))

  return {
    color: ['#1f4fd6', '#5b7fd4', '#8fa8e0', '#a7bbef'],
    tooltip: pieTooltip(),
    legend: { bottom: 4, textStyle: { color: '#6a7689', fontSize: 12 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '46%'],
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{d}%', color: '#3d4a5c', fontSize: 11 },
        data,
      },
    ],
  }
}
