import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDouyinCarrierOption,
  buildDouyinFunnelOption,
  buildDouyinTrendOption,
  pickSelectedSnapshot,
  pickSnapshotsByPeriod,
  resolveComparePeriods,
} from './douyinChartOptions.js'

const snaps = [
  {
    dateType: 1,
    payAmt: 100,
    payCnt: 10,
    payUcnt: 8,
    productShowCnt: 1000,
    productClickCnt: 200,
    carriers: [{ name: '短视频', pay_amt: 70 }],
  },
  {
    dateType: 20,
    payAmt: 300,
    payCnt: 40,
    payUcnt: 30,
    productShowCnt: 4000,
    productClickCnt: 800,
    carriers: [{ name: '短视频', pay_amt: 200 }, { name: '直播', payAmt: 100 }],
  },
  {
    dateType: 21,
    payAmt: 2000,
    payCnt: 300,
    payUcnt: 250,
    productShowCnt: 20000,
    productClickCnt: 4000,
    carriers: [{ name: '短视频', pay_amt: 1200 }],
  },
  {
    dateType: 23,
    payAmt: 8000,
    payCnt: 1200,
    payUcnt: 1000,
    productShowCnt: 80000,
    productClickCnt: 16000,
    carriers: [{ name: '短视频', pay_amt: 5000 }],
  },
]

test('compare set: realtime uses today + yesterday', () => {
  const keys = resolveComparePeriods('realtime').map((p) => p.key)
  assert.deepEqual(keys, ['realtime', 'd1'])
})

test('compare set: d7 includes three periods', () => {
  const keys = resolveComparePeriods('d7').map((p) => p.key)
  assert.deepEqual(keys, ['realtime', 'd1', 'd7'])
})

test('pickSnapshotsByPeriod filters missing', () => {
  const rows = pickSnapshotsByPeriod(snaps.slice(0, 2), 'd7')
  assert.equal(rows.length, 2)
})

test('pickSelectedSnapshot returns current period only', () => {
  const s = pickSelectedSnapshot(snaps, 'd7')
  assert.equal(Number(s.dateType), 21)
  assert.equal(pickSelectedSnapshot(snaps, 'd30').dateType, 23)
  assert.equal(pickSelectedSnapshot([], 'realtime'), null)
})

test('trend empty without snapshots', () => {
  const opt = buildDouyinTrendOption([], 'realtime')
  assert.equal(opt.__empty, true)
})

test('trend is dual-axis line comparing periods on x-axis', () => {
  const opt = buildDouyinTrendOption(snaps, 'realtime')
  assert.equal(opt.__empty, undefined)
  assert.deepEqual(opt.xAxis.data, ['今日实时', '昨日'])
  assert.equal(opt.series.length, 2)
  assert.equal(opt.series[0].type, 'line')
  assert.equal(opt.series[0].name, '支付金额')
  assert.equal(opt.series[1].type, 'line')
  assert.equal(opt.series[1].name, '成交订单')
  assert.equal(opt.series[1].yAxisIndex, 1)
  assert.equal(opt.series[0].data[0].value, 100)
  assert.equal(opt.series[0].data[0].symbolSize, 10)
  assert.equal(opt.series[0].data[1].value, 300)
  assert.equal(opt.series[0].data[1].symbolSize, 6)
  assert.equal(opt.series[1].data[0].value, 10)
  assert.equal(opt.series[1].data[1].value, 40)
})

test('trend d30 includes four period categories', () => {
  const opt = buildDouyinTrendOption(snaps, 'd30')
  assert.deepEqual(opt.xAxis.data, ['今日实时', '昨日', '近7天', '近30天'])
  assert.deepEqual(
    opt.series[0].data.map((d) => d.value),
    [100, 300, 2000, 8000],
  )
  assert.equal(opt.series[0].data[3].symbolSize, 10)
})

test('funnel always uses selected period funnel chart', () => {
  const opt = buildDouyinFunnelOption(snaps, 'd7')
  assert.equal(opt.series[0].type, 'funnel')
  assert.deepEqual(
    opt.series[0].data.map((d) => d.name),
    ['曝光', '点击', '成交'],
  )
  assert.deepEqual(
    opt.series[0].data.map((d) => d.value),
    [20000, 4000, 250],
  )
})

test('funnel empty when selected period missing', () => {
  const opt = buildDouyinFunnelOption(snaps.slice(0, 1), 'd30')
  assert.equal(opt.__empty, true)
})

test('carrier always pie for selected period', () => {
  const opt = buildDouyinCarrierOption(snaps, 'd1')
  assert.equal(opt.series[0].type, 'pie')
  assert.equal(opt.series[0].data.length, 2)
  assert.equal(opt.series[0].data[0].name, '短视频')
  assert.equal(opt.series[0].data[0].value, 200)
})
