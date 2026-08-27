<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { formatUtc8 } from '@/utils/time'
import { ElMessage } from 'element-plus'
import { fetchDouyinStores } from '@/api/platformAccounts'
import {
  crawlDouyinIssues,
  fetchTodayDouyinOrders,
  loadDouyinIssues,
  resolveDouyinIssue,
} from '@/api/domesticPlatforms'
import {
  canUseDouyinBackend,
  fetchDouyinCompass,
  fetchDouyinCompassProductRanks,
  fetchDouyinOpportunityOverview,
  fetchDouyinOpportunityProducts,
  fetchDouyinProducts,
  fetchDouyinSession,
  syncDouyinCompass,
  syncDouyinCompassProductRank,
  syncDouyinFull,
  syncDouyinOpportunity,
  syncDouyinProducts,
} from '@/api/douyinApi'
import { DOUYIN_ISSUE_TYPES } from '@/constants/douyinDemo'
import { useDomesticModule } from '@/composables/useDomesticModule'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import DomesticBossOverview from '@/components/domestic/DomesticBossOverview.vue'
import DomesticOrdersPanel from '@/components/domestic/DomesticOrdersPanel.vue'
import DomesticIssuesPanel from '@/components/domestic/DomesticIssuesPanel.vue'
import PlatformShipPushDialog from '@/components/domestic/PlatformShipPushDialog.vue'
import HelperStatusBar from '@/components/helper/HelperStatusBar.vue'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import DouyinSyncLogDrawer from '@/components/douyin/DouyinSyncLogDrawer.vue'
import SyncHistoryDrawer from '@/components/common/SyncHistoryDrawer.vue'
import { fetchPlatformSyncLogs } from '@/api/syncLogApi'
import BaseChart from '@/components/charts/BaseChart.vue'
import { FULL_SYNC_STEP_IDS, FULL_SYNC_STEP_LABELS } from '@/api/douyinFullSync'
import { canUsePlatformUserHelper } from '@/utils/opsSyncPolicy'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
import {
  buildDouyinCarrierOption,
  buildDouyinFunnelOption,
  buildDouyinTrendOption,
  pickSnapshotsByPeriod,
} from '@/utils/douyinChartOptions'
import { buildTodayHotProducts } from '@/utils/douyinTodayHotProducts'
import {
  filterNewListedProducts,
  filterTodaySalesOrders,
} from '@/utils/douyinProductListFilters'

const {
  auth,
  assigneeMap,
  activeTab,
  selectedStoreId,
  stores,
  ordersSyncedAt,
  issuesSyncedAt,
  loadingStores,
  loadingOrders,
  loadingIssues,
  issuesPanel,
  issuesFilter,
  storeNameMap,
  showStoreColumn,
  showStoreList,
  overviewStores,
  filteredOrders,
  filteredIssues,
  pendingOrderCount,
  pendingIssueCount,
  syncTodayOrders,
  syncIssues,
  handleResolveIssue,
  goToAccountBinding,
  handleOverviewNavigate: navigateOverview,
  openShipDialog,
  submitShipPush,
  shipDialogVisible,
  shipDialogOrder,
  shipDialogType,
  shipSubmitting,
  platformLabel,
  operationalDemoOnly,
  operationalHint,
} = useDomesticModule({
  platformKey: 'douyin',
  fetchStores: fetchDouyinStores,
  fetchOrders: fetchTodayDouyinOrders,
  loadIssues: loadDouyinIssues,
  crawlIssues: crawlDouyinIssues,
  resolveIssue: resolveDouyinIssue,
  issueTypeMap: DOUYIN_ISSUE_TYPES,
})

const detailTab = ref('catalog') // rank | opportunity | catalog
activeTab.value = 'products'

function handleOverviewNavigate(target) {
  // Boss 概览跳转订单/预警：进入「商品信息」大 Tab，并由 navigateOverview 设 activeTab
  if (target === 'orders' || String(target).startsWith('issues')) {
    detailTab.value = 'catalog'
  }
  navigateOverview(target)
}

function goToProductList(listTab = 'all') {
  detailTab.value = 'catalog'
  activeTab.value = 'products'
  productListTab.value = listTab === 'hot' ? 'hot' : 'all'
}

const session = ref({
  agent_online: false,
  logged_in: false,
  ready: false,
  requires_auth: true,
  message: '',
})
const sessionLoading = ref(false)
const helperOnline = ref(false)
const showHelperBar = computed(() => canUsePlatformUserHelper(auth) && !operationalDemoOnly.value)
const helperBarRef = ref(null)

function onHelperOnline(online) {
  helperOnline.value = Boolean(online)
  if (online) refreshSession()
}

function openDouyinBindCode() {
  if (helperBarRef.value?.openBindDialog) {
    helperBarRef.value.openBindDialog()
    return
  }
  ElMessage.warning('请先安装并启动 Sync Helper，再在状态栏生成绑定码')
}
const products = ref([])
const productsSyncedAt = ref('')
const loadingProducts = ref(false)
const syncingProducts = ref(false)
const compass = ref(null)
const compassSnapshots = ref([])
const compassSyncedAt = ref('')
const loadingCompass = ref(false)
const syncingCompass = ref(false)
/** 数据时段：realtime(1) | d1(20) | d7(21) | d30(23) */
const compassPeriodKey = ref('realtime')
const cockpitVizTab = ref('trend') // trend | funnel | carrier

const COMPASS_PERIOD_OPTIONS = [
  { value: 'realtime', label: '今日实时', dateType: 1 },
  { value: 'd1', label: '昨日', dateType: 20 },
  { value: 'd7', label: '近7天', dateType: 21 },
  { value: 'd30', label: '近30天', dateType: 23 },
]

const PERIOD_DATE_TYPE = { realtime: 1, d1: 20, d7: 21, d30: 23 }
const opportunityProducts = ref([])
const opportunitySyncedAt = ref('')
const opportunityCategoryName = ref('')
const opportunityCategoryKey = ref('')
const opportunityCategoryQuery = ref('')
const opportunityPool = ref('potential')
const opportunitySort = ref('MATCH_DEGREE')
const loadingOpportunity = ref(false)
const syncingOpportunity = ref(false)
const opportunityDrawer = ref(false)
const opportunityOverview = ref(null)
const loadingOverview = ref(false)
const opportunityPeriodTab = ref('d7')

const rankBoard = ref('total')
const rankDateWindow = ref('today')
const rankProducts = ref([])
const rankSyncedAt = ref('')
const rankCategoryName = ref('')
const rankReportDay = ref('')
const loadingRank = ref(false)
const syncingRank = ref(false)
const rankPeerAvailable = ref(true)
const rankHasShowCnt = ref(true)
const rankHasOrderCnt = ref(true)
const rankTrackFilter = ref('all') // all | 建议追踪 | 可观望
const rankSortByScore = ref(false)
const rankDrawerVisible = ref(false)
const rankDrawerRow = ref(null)

const rankBoardOptions = [
  { value: 'search', label: '搜索榜' },
  { value: 'product_card', label: '商品卡榜' },
  { value: 'total', label: '总榜' },
]
const rankDateWindowOptions = [
  { value: 'today', label: '今日实时' },
  { value: 'yesterday', label: '昨日' },
]

const opportunityPeriodOptions = [
  { value: 'day', label: '今日' },
  { value: 'd7', label: '7天' },
  { value: 'd30', label: '30天' },
]

function formatMetricValue(v) {
  if (v == null || v === '') return '—'
  if (typeof v === 'number' && Number.isFinite(v)) {
    if (Math.abs(v) >= 1000) return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
    return String(Number(v.toFixed(2)))
  }
  return String(v)
}

function trackTagType(label) {
  if (label === '建议追踪') return 'success'
  if (label === '可观望') return 'warning'
  if (label === '暂不建议') return 'info'
  return 'info'
}

function openRankDrawer(row) {
  rankDrawerRow.value = row
  rankDrawerVisible.value = true
}

function formatDeltaPct(v) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(1)}%`
}

function growthTone(v) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return 'muted'
  return Number(v) >= 0 ? 'up' : 'down'
}

const opportunityDetailMeta = computed(() => {
  const ov = opportunityOverview.value || {}
  const labels = Array.isArray(ov.labels) ? ov.labels : []
  const price =
    ov.priceMin == null && ov.priceMax == null
      ? '—'
      : `${ov.priceMin ?? '—'} - ${ov.priceMax ?? '—'}`
  return {
    title: ov.productName || '—',
    image: ov.mainImage || '',
    category: ov.categoryPath || ov.categoryName || '—',
    labels,
    price,
  }
})

const opportunityTrendKpis = computed(() => {
  const ov = opportunityOverview.value || {}
  const overview = ov.overview && typeof ov.overview === 'object' ? ov.overview : {}
  const fromList = overview.from_list && typeof overview.from_list === 'object' ? overview.from_list : {}
  const ind = fromList.clue_indicator && typeof fromList.clue_indicator === 'object' ? fromList.clue_indicator : {}
  const card =
    fromList.query_clue_card_info && typeof fromList.query_clue_card_info === 'object'
      ? fromList.query_clue_card_info
      : {}
  const tab = opportunityPeriodTab.value

  if (tab === 'day') {
    return [
      { label: '搜索热度', value: formatMetricValue(ov.searchPopularity ?? card.search_popularity), trend: null },
      {
        label: '成交单量',
        value: formatMetricValue(ov.payOrderCntRange || ov.payOrderCnt || ind.pay_order_cnt_range || ind.pay_order_cnt),
        trend: null,
      },
      { label: '搜索指数', value: formatMetricValue(ov.searchHeat ?? ind.search_heat), trend: null },
      { label: '竞争指数', value: formatMetricValue(ov.demandSupplyRate ?? ind.demand_supply_rate ?? card.demand_supply_rate), trend: null },
      { label: '成交金额', value: formatMetricValue(ov.payAmtRange || ind.pay_amount_ind_range), trend: null },
    ]
  }
  if (tab === 'd7') {
    return [
      { label: '7日销量', value: formatMetricValue(ov.sevenDaySales ?? ind.seven_day_sales), trend: null },
      {
        label: '搜索指数',
        value: formatMetricValue(ov.searchPvRange || ind.search_pv_cnt_range || ind.demand_heat_range),
        trend: ov.searchPv30dRate ?? ind.search_pv_cnt_30d_rate,
      },
      {
        label: '竞争指数',
        value: formatMetricValue(ov.demandSupplyRate ?? ind.demand_supply_rate),
        trend: ind.demand_supply_rate_30d_rate,
      },
      {
        label: '成交金额',
        value: formatMetricValue(ov.payAmtRange || ind.pay_amount_ind_range),
        trend: ov.payGrowthRate ?? ind.pay_amount_ind_30d_rate,
      },
      {
        label: '商品供给',
        value: formatMetricValue(ind.online_prod_cnt_range || ind.online_prod_cnt),
        trend: ind.online_prod_cnt_30d_rate,
      },
    ]
  }
  return [
    {
      label: '搜索指数',
      value: formatMetricValue(ov.searchPvRange || ind.search_pv_cnt_range || ind.demand_heat_range),
      trend: ov.searchPv30dRate ?? ind.search_pv_cnt_30d_rate,
    },
    {
      label: '竞争指数',
      value: formatMetricValue(ov.demandSupplyRate ?? ind.demand_supply_rate),
      trend: ind.demand_supply_rate_30d_rate,
    },
    {
      label: '成交金额',
      value: formatMetricValue(ov.payAmtRange || ind.pay_amount_ind_range),
      trend: ov.payGrowthRate ?? ind.pay_amount_ind_30d_rate,
    },
    {
      label: '商品供给',
      value: formatMetricValue(ind.online_prod_cnt_range || ind.online_prod_cnt),
      trend: ind.online_prod_cnt_30d_rate,
    },
    {
      label: '店铺供给',
      value: formatMetricValue(ind.online_shop_cnt_range || ind.online_shop_cnt),
      trend: ind.online_shop_cnt_30d_rate,
    },
  ]
})

const opportunityAnalysisItems = computed(() => {
  const ov = opportunityOverview.value || {}
  const overview = ov.overview && typeof ov.overview === 'object' ? ov.overview : {}
  const fromList = overview.from_list && typeof overview.from_list === 'object' ? overview.from_list : {}
  const profits = Array.isArray(fromList.profit_info_list) ? fromList.profit_info_list : []
  const labels = Array.isArray(fromList.clue_label_list) ? fromList.clue_label_list : []
  const items = []
  for (const p of profits) {
    if (!p || typeof p !== 'object') continue
    const name = p.profit_name || p.name
    if (!name) continue
    items.push({
      tag: '商机中心推荐',
      text: String(p.profit_desc || p.desc || p.profit_content || name),
    })
  }
  for (const lab of labels) {
    if (!lab || typeof lab !== 'object') continue
    const name = lab.label_name || lab.name
    if (!name) continue
    items.push({
      tag: String(name),
      text: String(lab.label_desc || lab.desc || '').trim() || String(name),
    })
  }
  if (!items.length && Array.isArray(ov.labels) && ov.labels.length) {
    for (const name of ov.labels) {
      items.push({ tag: '标签', text: String(name) })
    }
  }
  return items.slice(0, 6)
})

const opportunityPoolOptions = [
  { value: 'potential', label: '跟潜力爆品' },
  { value: 'hot_words', label: '追抖音热词' },
]
const opportunitySortOptions = [
  { value: 'MATCH_DEGREE', label: '为你推荐' },
  { value: 'TRADING_AMOUNT', label: '成交高' },
  { value: 'PAY_AMOUNT_RATE', label: '增速快' },
  { value: 'DEMAND_SUPPLY_RATE', label: '竞争小' },
]

const useBackend = () => canUseDouyinBackend(auth)

const HOT_PRODUCT_SALES_MIN = 10
const productListTab = ref('all')

const filteredProducts = computed(() => {
  const list = products.value || []
  if (!selectedStoreId.value || selectedStoreId.value === 'all') return list
  return list.filter((p) => p.storeId === selectedStoreId.value)
})

/** 数据分析：销量 ≥ 10 列入爆款（累计销量，与「今日爆款」无关） */
const hotProducts = computed(() =>
  filteredProducts.value
    .filter((p) => Number(p.sales) >= HOT_PRODUCT_SALES_MIN)
    .slice()
    .sort((a, b) => Number(b.sales || 0) - Number(a.sales || 0)),
)

/** 近 24h 有效订单销量 ≥ 10 → 今日爆款 */
const todayHotProducts = computed(() =>
  buildTodayHotProducts(filteredOrders.value || [], filteredProducts.value || [], {
    minQty: HOT_PRODUCT_SALES_MIN,
  }),
)

/** 自然日今日有效销售订单（不含关闭/取消） */
const todaySalesOrders = computed(() => filterTodaySalesOrders(filteredOrders.value || []))

/** 近 3 个自然日内上架的新品 */
const newListedProducts = computed(() =>
  filterNewListedProducts(filteredProducts.value || [], { days: 3 }),
)

const showProductTable = computed(() => productListTab.value !== 'todayOrders')

const productListSource = computed(() => {
  if (productListTab.value === 'hot') return hotProducts.value
  if (productListTab.value === 'todayHot') return todayHotProducts.value
  if (productListTab.value === 'newSales') return newListedProducts.value
  return filteredProducts.value
})

const {
  keyword: productKeyword,
  page: productPage,
  pageSize: productPageSize,
  total: productTotal,
  paged: pagedProducts,
} = useFuzzySearchPagination(productListSource, {
  pageSize: 10,
  fields: ['productName', 'productId', 'articleNo', 'category'],
})

const {
  keyword: opportunityKeyword,
  page: opportunityPage,
  pageSize: opportunityPageSize,
  total: opportunityTotal,
  paged: pagedOpportunity,
} = useFuzzySearchPagination(opportunityProducts, {
  pageSize: 10,
  fields: ['productName', 'categoryPath', 'searchPvRange', 'payAmtRange'],
})

const filteredRankProducts = computed(() => {
  let rows = rankProducts.value || []
  if (rankTrackFilter.value && rankTrackFilter.value !== 'all') {
    rows = rows.filter((r) => r.trackLabel === rankTrackFilter.value)
  }
  if (rankSortByScore.value) {
    rows = [...rows].sort((a, b) => (b.trackScore ?? -1) - (a.trackScore ?? -1))
  }
  return rows
})

const rankMetricHint = computed(() => {
  const missing = []
  if (!rankHasShowCnt.value) missing.push('曝光数')
  if (!rankHasOrderCnt.value) missing.push('商品订单成交数')
  if (!missing.length) return ''
  return `当前窗口仍缺：${missing.join('、')}。同步时会用榜单「查看详情」竞品概览接口补齐 Top50；若仍为空可能是查看额度用尽或接口无权限。`
})

const {
  keyword: rankKeyword,
  page: rankPage,
  pageSize: rankPageSize,
  total: rankTotal,
  paged: pagedRankProducts,
} = useFuzzySearchPagination(filteredRankProducts, {
  pageSize: 10,
  fields: ['productName', 'productId', 'shopName', 'categoryPath'],
})

const compassPeriodLabel = computed(() => {
  const opt = COMPASS_PERIOD_OPTIONS.find((o) => o.value === compassPeriodKey.value)
  return opt?.label || '今日实时'
})

/** 当前时段对应的罗盘 snapshot（随时段 Tab 切换；找不到则空态，禁止回退到其它时段造成「图不变」） */
const selectedCompassSnapshot = computed(() => {
  const dt = PERIOD_DATE_TYPE[compassPeriodKey.value] ?? 1
  const list = compassSnapshots.value || []
  const hit = list.find((s) => Number(s.dateType) === dt)
  if (hit) return hit
  if (compassPeriodKey.value === 'realtime') {
    return list.find((s) => Number(s.dateType) === 1) || compass.value || null
  }
  return null
})

const compassKpis = computed(() => {
  const s = selectedCompassSnapshot.value || {}
  const money = (v) => (v == null || v === '' ? '—' : `¥${Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
  const numFmt = (v) => (v == null || v === '' ? '—' : Number(v).toLocaleString('zh-CN'))
  const peers = pickSnapshotsByPeriod(compassSnapshots.value, compassPeriodKey.value)
  const peer = peers.length >= 2 ? peers[1].snapshot : null
  const peerLabel = peers.length >= 2 ? peers[1].label : ''

  function deltaText(cur, base) {
    const a = Number(cur)
    const b = Number(base)
    if (!Number.isFinite(a) || !Number.isFinite(b) || b === 0) return ''
    const pct = ((a - b) / Math.abs(b)) * 100
    const sign = pct > 0 ? '+' : ''
    return `较${peerLabel} ${sign}${pct.toFixed(1)}%`
  }
  function deltaClass(cur, base) {
    const a = Number(cur)
    const b = Number(base)
    if (!Number.isFinite(a) || !Number.isFinite(b) || b === 0) return ''
    return a >= b ? 'is-up' : 'is-down'
  }

  return [
    {
      label: '用户支付金额',
      value: money(s.payAmt),
      primary: true,
      delta: deltaText(s.payAmt, peer?.payAmt),
      deltaClass: deltaClass(s.payAmt, peer?.payAmt),
    },
    {
      label: '成交订单数',
      value: numFmt(s.payCnt),
      primary: true,
      delta: deltaText(s.payCnt, peer?.payCnt),
      deltaClass: deltaClass(s.payCnt, peer?.payCnt),
    },
    {
      label: '成交人数',
      value: numFmt(s.payUcnt),
      primary: true,
      delta: deltaText(s.payUcnt, peer?.payUcnt),
      deltaClass: deltaClass(s.payUcnt, peer?.payUcnt),
    },
    {
      label: '客单价',
      value: money(s.perUsrPayAmt),
      primary: true,
      delta: deltaText(s.perUsrPayAmt, peer?.perUsrPayAmt),
      deltaClass: deltaClass(s.perUsrPayAmt, peer?.perUsrPayAmt),
    },
  ]
})

const compassHeroKpis = computed(() => compassKpis.value.filter((k) => k.primary))

const compassSideMetrics = computed(() => {
  const s = selectedCompassSnapshot.value || {}
  const periodLabel = compassPeriodLabel.value
  const money = (v) => (v == null || v === '' ? '—' : `¥${Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
  const numFmt = (v) => (v == null || v === '' ? '—' : Number(v).toLocaleString('zh-CN'))
  const pct = (v) => {
    const n = Number(v)
    if (!Number.isFinite(n)) return '—'
    const shown = n > 0 && n <= 1 ? n * 100 : n
    return `${shown.toFixed(1)}%`
  }
  const rate = (a, b) => {
    const x = Number(a)
    const y = Number(b)
    if (!Number.isFinite(x) || !Number.isFinite(y) || y <= 0) return '—'
    return `${((x / y) * 100).toFixed(1)}%`
  }

  if (cockpitVizTab.value === 'funnel') {
    const show = s.productShowCnt ?? s.productShowUcnt
    const click = s.productClickCnt ?? s.productClickUcnt
    const deal = s.payUcnt ?? s.payCnt
    return [
      { label: '曝光→点击', value: s.showClickRate != null ? pct(s.showClickRate) : rate(click, show), sub: periodLabel },
      { label: '点击→成交', value: s.clickPayRate != null ? pct(s.clickPayRate) : rate(deal, click), sub: periodLabel },
      { label: '曝光', value: numFmt(show), sub: periodLabel },
      { label: '成交', value: numFmt(deal), sub: periodLabel },
    ]
  }
  if (cockpitVizTab.value === 'carrier') {
    const list = Array.isArray(s.carriers) ? s.carriers : []
    const cards = list.slice(0, 3).map((c) => {
      const pay = c.pay_amt ?? c.payAmt
      const ratio = Number(c.ratio)
      return {
        label: c.name || '载体',
        value: pay == null || pay === '' ? '—' : money(pay),
        sub: Number.isFinite(ratio) ? `${ratio.toFixed(1)}%` : periodLabel,
      }
    })
    cards.push({
      label: '合计',
      value: money(s.payAmt),
      sub: periodLabel,
    })
    return cards
  }

  const peers = pickSnapshotsByPeriod(compassSnapshots.value, compassPeriodKey.value)
  // 成交趋势：旁侧卡仍读当前时段；折线图横轴承担时段对比
  const compareSub = peers.length > 1
    ? `折线对比 ${peers.map((p) => p.label).join(' / ')}`
    : periodLabel
  return [
    { label: '支付金额', value: money(s.payAmt), sub: compareSub },
    { label: '成交订单', value: numFmt(s.payCnt), sub: compareSub },
    { label: '点击成交率', value: s.clickPayRate != null ? pct(s.clickPayRate) : '—', sub: periodLabel },
    { label: '退款率', value: s.refundRate != null ? pct(s.refundRate) : '—', sub: periodLabel },
  ]
})

const compassExpParts = computed(() => {
  // 体验分取实时 snapshot（与时段无关）
  const realtime = (compassSnapshots.value || []).find((s) => Number(s.dateType) === 1)
  const s = realtime || compass.value
  if (!s) return []
  return [
    { label: '商品', value: s.expProduct },
    { label: '服务', value: s.expService },
    { label: '物流', value: s.expLogistics },
  ]
})

const compassExpScore = computed(() => {
  const realtime = (compassSnapshots.value || []).find((s) => Number(s.dateType) === 1)
  const s = realtime || compass.value
  return s?.expScore ?? '—'
})

const douyinTrendOption = computed(() =>
  buildDouyinTrendOption(compassSnapshots.value, compassPeriodKey.value),
)
const douyinFunnelOption = computed(() =>
  buildDouyinFunnelOption(compassSnapshots.value, compassPeriodKey.value),
)
const douyinCarrierOption = computed(() =>
  buildDouyinCarrierOption(compassSnapshots.value, compassPeriodKey.value),
)

/** 图表 Tab 切换时换 option；时段切换时对比集一并重算 */
const douyinActiveChartOption = computed(() => {
  if (cockpitVizTab.value === 'funnel') return douyinFunnelOption.value
  if (cockpitVizTab.value === 'carrier') return douyinCarrierOption.value
  return douyinTrendOption.value
})

const hasCompassData = computed(() =>
  Boolean(compass.value || (compassSnapshots.value && compassSnapshots.value.length)),
)

const opsOverviewCards = computed(() => ({
  orderTotal: (filteredOrders.value || []).length,
  orderPending: pendingOrderCount.value || 0,
  issueOpen: pendingIssueCount.value || 0,
  storeCount: (overviewStores.value || []).length || (stores.value || []).length || 0,
}))

async function loadCompass() {
  if (!useBackend()) {
    compass.value = null
    compassSnapshots.value = []
    compassSyncedAt.value = ''
    return
  }
  loadingCompass.value = true
  try {
    const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
    const data = await fetchDouyinCompass({ storeId, all: true })
    const snapshots = Array.isArray(data?.snapshots) ? data.snapshots : []
    compassSnapshots.value = snapshots
    compass.value = snapshots.find((s) => Number(s.dateType) === 1) || snapshots[0] || data?.snapshot || null
    compassSyncedAt.value = data?.synced_at || compass.value?.syncedAt || ''
  } catch (err) {
    compass.value = null
    compassSnapshots.value = []
    ElMessage.error(err?.message || '加载罗盘失败')
  } finally {
    loadingCompass.value = false
  }
}

async function handleSyncCompass() {
  if (!useBackend()) return
  syncingCompass.value = true
  try {
    await runLoggedModuleSync({
      id: 'compass',
      label: '数据罗盘',
      runner: async () => {
        const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
        const res = await syncDouyinCompass({ force: true, storeId })
        const snapshots = Array.isArray(res?.data?.snapshots) ? res.data.snapshots : []
        compassSnapshots.value = snapshots
        compass.value = res?.data?.snapshot || snapshots.find((s) => Number(s.dateType) === 1) || null
        compassSyncedAt.value = res?.data?.syncedAt || ''
        await refreshSession()
        return { message: res?.message || '已同步抖店罗盘' }
      },
    })
    ElMessage.success(syncRun.value.steps?.[0]?.message || '已同步抖店罗盘')
  } catch (err) {
    ElMessage.error(err?.message || '同步罗盘失败')
  } finally {
    syncingCompass.value = false
  }
}

async function loadOpportunity() {
  if (!useBackend()) {
    opportunityProducts.value = []
    opportunitySyncedAt.value = ''
    opportunityCategoryName.value = ''
    opportunityCategoryKey.value = ''
    return
  }
  loadingOpportunity.value = true
  try {
    const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
    const data = await fetchDouyinOpportunityProducts({
      storeId,
      pool: opportunityPool.value,
      sortField: opportunitySort.value,
    })
    opportunityProducts.value = Array.isArray(data?.items) ? data.items : []
    opportunitySyncedAt.value = data?.synced_at || ''
    opportunityCategoryName.value = data?.category_name || ''
    opportunityCategoryKey.value = data?.category_key || ''
  } catch (err) {
    opportunityProducts.value = []
    ElMessage.error(err?.message || '加载商机列表失败')
  } finally {
    loadingOpportunity.value = false
  }
}

async function handleSyncOpportunity() {
  if (!useBackend()) return
  syncingOpportunity.value = true
  try {
    await runLoggedModuleSync({
      id: 'opportunity',
      label: '商机中心',
      runner: async () => {
        const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
        const res = await syncDouyinOpportunity({
          force: true,
          storeId,
          categoryQuery: opportunityCategoryQuery.value?.trim() || null,
          pool: opportunityPool.value,
          sortField: opportunitySort.value,
        })
        opportunityProducts.value = res?.data?.products || []
        opportunitySyncedAt.value = res?.data?.syncedAt || ''
        opportunityCategoryName.value = res?.data?.categoryName || ''
        opportunityCategoryKey.value = res?.data?.categoryKey || ''
        await refreshSession()
        return { message: res?.message || '已同步商机中心' }
      },
    })
    ElMessage.success(syncRun.value.steps?.[0]?.message || '已同步商机中心')
  } catch (err) {
    ElMessage.error(err?.message || '同步商机中心失败')
  } finally {
    syncingOpportunity.value = false
  }
}

async function loadRankList() {
  if (!useBackend() || operationalDemoOnly.value) {
    rankProducts.value = []
    rankSyncedAt.value = ''
    rankCategoryName.value = ''
    rankReportDay.value = ''
    rankPeerAvailable.value = true
    rankHasShowCnt.value = true
    rankHasOrderCnt.value = true
    return
  }
  loadingRank.value = true
  try {
    const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
    const data = await fetchDouyinCompassProductRanks({
      storeId,
      board: rankBoard.value,
      dateWindow: rankDateWindow.value,
    })
    rankProducts.value = Array.isArray(data?.items) ? data.items : []
    rankSyncedAt.value = data?.synced_at || ''
    rankCategoryName.value = data?.category_name || ''
    rankReportDay.value = data?.report_day || ''
    rankPeerAvailable.value = data?.peer_available !== false
    rankHasShowCnt.value = Boolean(data?.has_show_cnt)
    rankHasOrderCnt.value = Boolean(data?.has_order_cnt)
  } catch (err) {
    rankProducts.value = []
    ElMessage.error(err?.message || '加载罗盘商品榜失败')
  } finally {
    loadingRank.value = false
  }
}

async function handleSyncRank() {
  if (!useBackend()) return
  syncingRank.value = true
  try {
    await runLoggedModuleSync({
      id: 'compass_product_rank',
      label: '罗盘商品榜',
      runner: async () => {
        const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
        const res = await syncDouyinCompassProductRank({
          force: true,
          storeId,
          board: rankBoard.value,
          dateWindow: rankDateWindow.value,
        })
        rankProducts.value = res?.data?.items || []
        rankSyncedAt.value = res?.data?.syncedAt || ''
        rankCategoryName.value = res?.data?.categoryName || ''
        rankReportDay.value = res?.data?.reportDay || ''
        rankPeerAvailable.value = res?.data?.peer_available !== false
        await refreshSession()
        await loadRankList()
        return { message: res?.message || '已同步罗盘商品榜' }
      },
    })
    ElMessage.success(syncRun.value.steps?.[0]?.message || '已同步罗盘商品榜')
  } catch (err) {
    ElMessage.error(err?.message || '同步罗盘商品榜失败')
  } finally {
    syncingRank.value = false
  }
}

function formatGrowth(v) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  const pct = (n * 100).toFixed(2)
  return `${n >= 0 ? '↑' : '↓'} ${Math.abs(Number(pct))}%`
}

async function openOpportunityOverview(row) {
  if (!row?.id) return
  opportunityDrawer.value = true
  opportunityOverview.value = null
  opportunityPeriodTab.value = 'd7'
  loadingOverview.value = true
  try {
    opportunityOverview.value = await fetchDouyinOpportunityOverview(row.id)
  } catch (err) {
    ElMessage.error(err?.message || '加载数据概述失败')
  } finally {
    loadingOverview.value = false
  }
}

async function refreshSession() {
  if (!useBackend()) return
  sessionLoading.value = true
  try {
    session.value = await fetchDouyinSession()
  } catch (err) {
    session.value = {
      agent_online: false,
      logged_in: false,
      ready: false,
      requires_auth: true,
      message: err?.message || '无法获取抖音登录状态',
    }
  } finally {
    sessionLoading.value = false
  }
}

async function loadProducts() {
  if (!useBackend()) {
    products.value = []
    productsSyncedAt.value = ''
    return
  }
  loadingProducts.value = true
  try {
    const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
    const data = await fetchDouyinProducts({ storeId })
    products.value = Array.isArray(data?.items) ? data.items : []
    productsSyncedAt.value = data?.synced_at || ''
  } catch (err) {
    products.value = []
    ElMessage.error(err?.message || '加载商品失败')
  } finally {
    loadingProducts.value = false
  }
}

async function handleSyncProducts() {
  if (!useBackend()) return
  syncingProducts.value = true
  try {
    await runLoggedModuleSync({
      id: 'products',
      label: '商品',
      runner: async () => {
        const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
        const res = await syncDouyinProducts({ force: true, storeId })
        products.value = res?.data?.products || []
        productsSyncedAt.value = res?.data?.syncedAt || ''
        await refreshSession()
        return { message: res?.message || `已同步商品 ${products.value.length} 条` }
      },
    })
    ElMessage.success(syncRun.value.steps?.[0]?.message || '已同步商品')
  } catch (err) {
    ElMessage.error(err?.message || '同步商品失败')
  } finally {
    syncingProducts.value = false
  }
}

async function handleSyncOrdersLogged() {
  try {
    await runLoggedModuleSync({
      id: 'orders',
      label: '近24小时订单',
      runner: async () => {
        await syncTodayOrders(true)
        return { message: '已同步近24小时订单' }
      },
    })
  } catch {
    // toast handled inside syncTodayOrders / runLoggedModuleSync
  }
}

async function handleSyncIssuesLogged() {
  try {
    await runLoggedModuleSync({
      id: 'issues',
      label: '内容预警',
      runner: async () => {
        await syncIssues(true)
        return { message: '已同步内容预警' }
      },
    })
  } catch {
    // toast handled inside syncIssues
  }
}

const fullSyncing = ref(false)
const fullSyncProgress = ref(null) // { index, total, label, status }
const advancedSyncOpen = ref([])
const syncLogOpen = ref(false)
const syncHistoryOpen = ref(false)
const syncRun = ref({
  title: '',
  status: 'idle',
  startedAt: '',
  finishedAt: '',
  steps: [],
  logs: [],
})

const syncRunDoneCount = computed(() =>
  (syncRun.value.steps || []).filter((s) => s.status === 'success' || s.status === 'failed').length,
)
const syncRunTotalCount = computed(() => (syncRun.value.steps || []).length)

function syncClock() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function pushSyncLog(text, level = 'info') {
  const logs = [...(syncRun.value.logs || [])]
  logs.push({ at: syncClock(), text, level })
  if (logs.length > 200) logs.splice(0, logs.length - 200)
  syncRun.value = { ...syncRun.value, logs }
}

function beginSyncRun({ title, steps }) {
  syncRun.value = {
    title,
    status: 'running',
    startedAt: syncClock(),
    finishedAt: '',
    steps: (steps || []).map((s) => ({
      id: s.id,
      label: s.label,
      status: 'pending',
      message: '',
      error: '',
      updatedAt: '',
    })),
    logs: [],
  }
  syncLogOpen.value = true
  pushSyncLog(`开始：${title}`)
}

function patchSyncStep(stepId, patch) {
  const steps = (syncRun.value.steps || []).map((s) =>
    s.id === stepId
      ? { ...s, ...patch, updatedAt: syncClock() }
      : s,
  )
  syncRun.value = { ...syncRun.value, steps }
}

function finishSyncRun(status, message) {
  const level = status === 'success' ? 'success' : status === 'partial' ? 'warn' : 'error'
  pushSyncLog(message || (status === 'success' ? '同步完成' : '同步结束'), level)
  syncRun.value = {
    ...syncRun.value,
    status,
    finishedAt: syncClock(),
  }
}

async function runLoggedModuleSync({ id, label, runner }) {
  if (fullSyncing.value) {
    ElMessage.warning('全量同步进行中，请稍候')
    return
  }
  beginSyncRun({
    title: `同步${label}`,
    steps: [{ id, label }],
  })
  patchSyncStep(id, { status: 'running' })
  pushSyncLog(`开始同步「${label}」…`)
  try {
    const res = await runner()
    const msg = res?.message || `${label}同步完成`
    patchSyncStep(id, { status: 'success', message: msg, error: '' })
    finishSyncRun('success', msg)
    return res
  } catch (err) {
    const error = err?.message || `${label}同步失败`
    patchSyncStep(id, { status: 'failed', error })
    finishSyncRun('failed', error)
    throw err
  }
}

async function handleFullSync() {
  if (fullSyncing.value) return
  if (!session.value?.agent_online) {
    ElMessage.warning('本机同步助手未在线，请先启动 CrossHub-Sync-Helper')
    return
  }
  fullSyncing.value = true
  fullSyncProgress.value = null
  beginSyncRun({
    title: '刷新全部（全量同步）',
    steps: FULL_SYNC_STEP_IDS.map((id) => ({
      id,
      label: FULL_SYNC_STEP_LABELS[id] || id,
    })),
  })
  const storeId = selectedStoreId.value === 'all' ? null : selectedStoreId.value
  try {
    const out = await syncDouyinFull({
      force: true,
      storeId,
      pool: opportunityPool.value,
      sortField: opportunitySort.value,
      categoryQuery: opportunityCategoryQuery.value?.trim() || null,
      board: rankBoard.value,
      dateWindow: rankDateWindow.value,
      onProgress: (p) => {
        fullSyncProgress.value = p
        if (p?.status === 'running') {
          patchSyncStep(p.stepId, { status: 'running', message: '', error: '' })
          pushSyncLog(`开始同步「${p.label}」（${p.index + 1}/${p.total}）`)
        } else if (p?.status === 'success') {
          const msg = p.message || '完成'
          patchSyncStep(p.stepId, {
            status: 'success',
            message: msg,
            error: '',
          })
          pushSyncLog(`「${p.label}」同步成功：${msg}`, 'success')
        } else if (p?.status === 'failed') {
          patchSyncStep(p.stepId, {
            status: 'failed',
            message: p.message || '',
            error: p.error || '失败',
          })
          pushSyncLog(`「${p.label}」同步失败：${p.error || '未知错误'}`, 'error')
        }
      },
    })
    pushSyncLog('正在刷新页面数据…')
    await Promise.allSettled([
      loadCompass(),
      loadRankList(),
      loadOpportunity(),
      loadProducts(),
      syncTodayOrders(false),
      syncIssues(false),
    ])
    finishSyncRun(out.partial ? 'partial' : 'success', out.message)
    if (out.partial) ElMessage.warning(out.message)
    else ElMessage.success(out.message)
  } catch (e) {
    const msg = e?.message || '全量同步失败'
    finishSyncRun('failed', msg)
    ElMessage.error(msg)
  } finally {
    fullSyncing.value = false
  }
}

watch(selectedStoreId, () => {
  loadProducts()
  loadCompass()
  loadOpportunity()
  loadRankList()
})

watch(operationalDemoOnly, (demoOnly) => {
  if (demoOnly && detailTab.value !== 'catalog') {
    detailTab.value = 'catalog'
  }
}, { immediate: true })

watch([opportunityPool, opportunitySort], () => {
  loadOpportunity()
})

watch([rankBoard, rankDateWindow], () => {
  loadRankList()
})

onMounted(() => {
  refreshSession()
  loadProducts()
  loadCompass()
  loadOpportunity()
  loadRankList()
})
</script>

<template>
  <PageScroll>
    <template #header>
      <div class="douyin-top">
        <PageHeader
          compact
          title="抖音运营"
          :description="auth.isBoss ? '' : `${auth.employee.name}`"
        >
          <template v-if="stores.length" #actions>
            <el-radio-group v-model="selectedStoreId" size="small" class="douyin-store-switch">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button v-for="store in stores" :key="store.id" :value="store.id">
                {{ store.storeName }}
              </el-radio-button>
            </el-radio-group>
          </template>
        </PageHeader>
      </div>
    </template>

    <HelperStatusBar
      v-if="showHelperBar"
      ref="helperBarRef"
      platform="douyin"
      :store-id="selectedStoreId"
      @update:online="onHelperOnline"
    />

    <PageSection v-if="!loadingStores && !stores.length" flush>
      <el-empty
        description="暂无可见的抖音店铺"
        :image-size="96"
      >
        <el-text type="info" size="small">
          {{
            auth.isBoss
              ? '请先在「账户绑定」中绑定抖音店铺；本机可先下载并绑定 Sync Helper'
              : '请联系企业管理员分配负责店铺；本机可先下载并绑定 Sync Helper'
          }}
        </el-text>
        <div class="douyin-empty-actions">
          <el-button v-if="showHelperBar" type="primary" plain @click="openDouyinBindCode">
            生成绑定码
          </el-button>
          <el-button v-if="auth.isBoss" type="primary" @click="goToAccountBinding">
            前往账户绑定
          </el-button>
        </div>
      </el-empty>
    </PageSection>

    <template v-else-if="stores.length">
      <el-alert
        v-if="operationalDemoOnly && operationalHint"
        :title="operationalHint"
        type="info"
        show-icon
        :closable="false"
        class="operational-hint"
      />

      <div v-if="!operationalDemoOnly" class="douyin-sync-bar">
        <div class="douyin-sync-bar__main">
          <el-button
            v-if="showHelperBar"
            type="primary"
            size="small"
            plain
            @click="openDouyinBindCode"
          >
            生成绑定码
          </el-button>
          <el-button
            type="primary"
            size="small"
            :loading="fullSyncing"
            :disabled="!session.agent_online || fullSyncing"
            @click="handleFullSync"
          >
            刷新全部
          </el-button>
          <button
            v-if="syncRun.status === 'running'"
            type="button"
            class="full-sync-progress is-clickable"
            @click="syncLogOpen = true"
          >
            <template v-if="fullSyncProgress">
              {{ fullSyncProgress.index + 1 }}/{{ fullSyncProgress.total }}
              {{ fullSyncProgress.label }}…
            </template>
            <template v-else>
              {{ syncRunDoneCount }}/{{ syncRunTotalCount || '—' }} 同步中…
            </template>
          </button>
          <el-button size="small" @click="syncLogOpen = true">
            数据日志
            <el-tag
              v-if="syncRun.status === 'running'"
              size="small"
              type="warning"
              effect="plain"
              style="margin-left: 6px"
            >
              {{ syncRunDoneCount }}/{{ syncRunTotalCount || '—' }}
            </el-tag>
            <el-tag
              v-else-if="syncRun.status === 'partial' || syncRun.status === 'failed'"
              size="small"
              :type="syncRun.status === 'failed' ? 'danger' : 'warning'"
              effect="plain"
              style="margin-left: 6px"
            >
              {{ syncRun.status === 'failed' ? '失败' : '部分完成' }}
            </el-tag>
            <el-tag
              v-else-if="syncRun.status === 'success'"
              size="small"
              type="success"
              effect="plain"
              style="margin-left: 6px"
            >
              {{ syncRunDoneCount }}/{{ syncRunTotalCount || '完成' }}
            </el-tag>
          </el-button>
          <el-button size="small" @click="syncHistoryOpen = true">历史记录</el-button>
        </div>
        <el-collapse v-model="advancedSyncOpen" class="advanced-sync">
          <el-collapse-item title="高级同步" name="1">
            <div class="session-actions">
              <el-button
                plain
                size="small"
                :loading="syncingProducts"
                :disabled="!session.agent_online"
                @click="handleSyncProducts"
              >
                同步商品
              </el-button>
              <el-button
                plain
                size="small"
                :loading="loadingOrders"
                :disabled="!session.agent_online"
                @click="handleSyncOrdersLogged"
              >
                同步近24小时订单
              </el-button>
              <el-button
                plain
                size="small"
                :loading="syncingCompass"
                :disabled="!session.agent_online"
                @click="handleSyncCompass"
              >
                同步罗盘（全时段）
              </el-button>
              <el-button
                plain
                size="small"
                :loading="syncingRank"
                :disabled="!session.agent_online"
                @click="handleSyncRank"
              >
                同步商品榜
              </el-button>
              <el-button
                plain
                size="small"
                :loading="syncingOpportunity"
                :disabled="!session.agent_online"
                @click="handleSyncOpportunity"
              >
                同步商机当前榜
              </el-button>
              <el-button
                plain
                size="small"
                :loading="loadingIssues"
                :disabled="!session.agent_online"
                @click="handleSyncIssuesLogged"
              >
                同步内容预警
              </el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <PageSection
        v-if="!operationalDemoOnly || auth.isBoss"
        title="经营驾驶舱"
      >
        <div v-loading="loadingCompass || syncingCompass" class="cockpit">
          <template v-if="!operationalDemoOnly">
            <div class="period-bar">
              <span class="period-bar__label">数据时段</span>
              <div class="seg" role="tablist" aria-label="数据时段">
                <button
                  v-for="opt in COMPASS_PERIOD_OPTIONS"
                  :key="opt.value"
                  type="button"
                  role="tab"
                  :aria-selected="compassPeriodKey === opt.value"
                  :class="{ 'is-active': compassPeriodKey === opt.value }"
                  @click="compassPeriodKey = opt.value"
                >
                  {{ opt.label }}
                </button>
              </div>
              <span class="period-bar__note">
                当前：{{ compassPeriodLabel }}<template v-if="compassSyncedAt"> · 同步 {{ formatUtc8(compassSyncedAt) }}</template>
              </span>
            </div>

            <div class="cockpit-hero">
              <div class="cockpit-exp" :class="{ 'is-empty': compassExpScore === '—' }">
                <div class="cockpit-exp__score">
                  <span class="cockpit-exp__score-label">体验分</span>
                  <span class="cockpit-exp__score-value">
                    {{ compassExpScore }}<em v-if="compassExpScore !== '—'">/100</em>
                  </span>
                </div>
                <div class="cockpit-exp__parts">
                  <div v-for="part in compassExpParts" :key="part.label" class="cockpit-exp__part">
                    <span class="cockpit-exp__part-label">{{ part.label }}</span>
                    <span class="cockpit-exp__part-value">{{ part.value ?? '—' }}</span>
                  </div>
                </div>
              </div>
              <div class="cockpit-hero-kpis">
                <div v-for="item in compassHeroKpis" :key="item.label" class="cockpit-hero-kpi">
                  <div class="cockpit-hero-kpi__value">{{ item.value }}</div>
                  <div class="cockpit-hero-kpi__label">{{ item.label }}</div>
                  <div
                    v-if="item.delta"
                    class="cockpit-hero-kpi__delta"
                    :class="item.deltaClass"
                  >
                    {{ item.delta }}
                  </div>
                </div>
                <button
                  type="button"
                  class="cockpit-hero-kpi cockpit-hero-kpi--action"
                  @click="goToProductList('all')"
                >
                  <div class="cockpit-hero-kpi__value">{{ filteredProducts.length }}</div>
                  <div class="cockpit-hero-kpi__label">商品总数</div>
                </button>
                <button
                  type="button"
                  class="cockpit-hero-kpi cockpit-hero-kpi--action is-hot"
                  @click="goToProductList('hot')"
                >
                  <div class="cockpit-hero-kpi__value">{{ hotProducts.length }}</div>
                  <div class="cockpit-hero-kpi__label">爆款（销量≥{{ HOT_PRODUCT_SALES_MIN }}）</div>
                </button>
              </div>
            </div>

            <div class="viz-panel">
              <div class="viz-panel__head">
                <h5 class="viz-panel__title">经营总览图</h5>
                <span class="viz-panel__period-tag">{{ compassPeriodLabel }}</span>
                <div class="viz-tabs">
                  <button
                    type="button"
                    :class="{ 'is-active': cockpitVizTab === 'trend' }"
                    @click="cockpitVizTab = 'trend'"
                  >
                    成交趋势
                  </button>
                  <button
                    type="button"
                    :class="{ 'is-active': cockpitVizTab === 'funnel' }"
                    @click="cockpitVizTab = 'funnel'"
                  >
                    转化漏斗
                  </button>
                  <button
                    type="button"
                    :class="{ 'is-active': cockpitVizTab === 'carrier' }"
                    @click="cockpitVizTab = 'carrier'"
                  >
                    载体结构
                  </button>
                </div>
              </div>
              <div class="viz-panel__body">
                <div class="viz-layout">
                  <div class="viz-layout__chart">
                    <BaseChart
                      :key="`${compassPeriodKey}-${cockpitVizTab}`"
                      :option="douyinActiveChartOption"
                      :height="280"
                      empty-text="暂无数据"
                    />
                  </div>
                  <div class="metric-cards">
                    <div
                      v-for="item in compassSideMetrics"
                      :key="`${cockpitVizTab}-${item.label}`"
                      class="metric-card"
                    >
                      <div class="metric-card__label">{{ item.label }}</div>
                      <div class="metric-card__value">{{ item.value }}</div>
                      <div v-if="item.sub" class="metric-card__sub">{{ item.sub }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <section class="cockpit-card cockpit-card--ops">
            <header class="cockpit-card__head">
              <h5 class="cockpit-card__title">运营概览</h5>
              <el-text size="small" type="info">近24小时</el-text>
            </header>
            <div class="ops-row">
              <button type="button" class="ops-stat" @click="handleOverviewNavigate('orders')">
                <strong>{{ opsOverviewCards.orderTotal }}</strong>
                <span>近24h 订单</span>
              </button>
              <button
                type="button"
                class="ops-stat"
                :class="{ 'is-warn': opsOverviewCards.orderPending > 0 }"
                @click="handleOverviewNavigate('orders')"
              >
                <strong>{{ opsOverviewCards.orderPending }}</strong>
                <span>待发货</span>
              </button>
              <button
                type="button"
                class="ops-stat"
                :class="{ 'is-danger': opsOverviewCards.issueOpen > 0 }"
                @click="handleOverviewNavigate('issues')"
              >
                <strong>{{ opsOverviewCards.issueOpen }}</strong>
                <span>内容预警</span>
              </button>
              <div class="ops-stat">
                <strong>{{ opsOverviewCards.storeCount }}</strong>
                <span>负责店铺</span>
              </div>
            </div>
            <DomesticBossOverview
              v-if="auth.isBoss"
              compact
              hide-metrics
              :orders="filteredOrders"
              :issues="filteredIssues"
              :stores="overviewStores"
              :assignee-map="assigneeMap"
              :show-store-list="showStoreList"
              issues-label="内容预警"
              @navigate="handleOverviewNavigate"
            />
          </section>

          <el-empty
            v-if="!operationalDemoOnly && !loadingCompass && !syncingCompass && !hasCompassData && !auth.isBoss"
            description="暂无罗盘数据"
          />
        </div>
      </PageSection>

      <PageSection title="经营明细">
        <el-tabs v-model="detailTab" class="detail-tabs">
          <el-tab-pane v-if="!operationalDemoOnly" label="商品榜" name="rank">
        <div class="detail-toolbar">
          <div class="detail-toolbar__filters">
            <el-radio-group v-model="rankBoard" size="small">
              <el-radio-button
                v-for="opt in rankBoardOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
            <el-radio-group v-model="rankDateWindow" size="small">
              <el-radio-button
                v-for="opt in rankDateWindowOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
            <el-radio-group v-model="rankTrackFilter" size="small">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="建议追踪">建议追踪</el-radio-button>
              <el-radio-button value="可观望">可观望</el-radio-button>
            </el-radio-group>
            <el-switch
              v-model="rankSortByScore"
              inline-prompt
              active-text="按综合分"
              inactive-text="按榜排名"
            />
            <el-input
              v-if="rankProducts.length"
              v-model="rankKeyword"
              clearable
              size="small"
              placeholder="搜索商品 / 店铺 / 类目"
              class="detail-toolbar__search"
            />
          </div>
          <div class="detail-toolbar__actions">
            <el-button
              type="primary"
              size="small"
              :loading="syncingRank || loadingRank"
              :disabled="!session.agent_online"
              @click="handleSyncRank"
            >
              同步商品榜
            </el-button>
            <el-text
              v-if="rankCategoryName || rankSyncedAt || rankProducts.length"
              size="small"
              type="info"
              class="detail-toolbar__meta"
            >
              <template v-if="rankCategoryName">
                {{ rankCategoryName }}{{ rankReportDay ? ` · ${rankReportDay}` : '' }}
              </template>
              <template v-if="rankSyncedAt">
                <template v-if="rankCategoryName"> · </template>同步 {{ formatUtc8(rankSyncedAt) }}
              </template>
              <template v-if="rankProducts.length">
                <template v-if="rankCategoryName || rankSyncedAt"> · </template>{{ rankProducts.length }} 条
              </template>
            </el-text>
          </div>
        </div>
        <el-alert
          v-if="rankProducts.length && rankPeerAvailable === false"
          type="warning"
          show-icon
          :closable="false"
          title="需同时具备昨日与今日数据后，方可查看追踪分析"
          style="margin-top: 8px"
        />
        <el-alert
          v-if="rankProducts.length && rankDateWindow === 'yesterday' && (!rankHasShowCnt || !rankHasOrderCnt) && rankMetricHint"
          type="info"
          show-icon
          :closable="false"
          style="margin-top: 8px"
          :title="rankMetricHint"
        />
        <TableQueryBar
          v-if="rankProducts.length"
          v-model:keyword="rankKeyword"
          v-model:page="rankPage"
          v-model:page-size="rankPageSize"
          :total="rankTotal"
          placeholder="搜索商品 / 店铺 / 类目"
          :show-sizes="false"
          :show-search="false"
        >
          <el-table
            v-loading="loadingRank || syncingRank"
            :data="pagedRankProducts"
            size="small"
            stripe
            row-key="id"
            @row-click="openRankDrawer"
          >
            <el-table-column prop="rankNo" label="#" width="56" align="center" fixed />
            <el-table-column label="商品" min-width="220" fixed>
              <template #default="{ row }">
                <div class="opp-product-cell">
                  <el-image
                    v-if="row.mainImage"
                    :src="row.mainImage"
                    fit="cover"
                    class="product-thumb"
                    :preview-src-list="[row.mainImage]"
                    preview-teleported
                  />
                  <div class="opp-product-cell__meta">
                    <div class="opp-product-cell__title">{{ row.productName || '—' }}</div>
                    <div class="opp-product-cell__sub">{{ row.productId || '' }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="排名变化" width="88" align="center">
              <template #default="{ row }">
                <span v-if="row.trackLabel === '数据不足' || (row.rankDelta == null && !row.isNewEntry)">—</span>
                <span v-else-if="row.isNewEntry" class="rank-delta is-new">新进</span>
                <span v-else-if="row.rankDelta > 0" class="rank-delta is-up">↑{{ row.rankDelta }}</span>
                <span v-else-if="row.rankDelta < 0" class="rank-delta is-down">↓{{ Math.abs(row.rankDelta) }}</span>
                <span v-else class="rank-delta">持平</span>
              </template>
            </el-table-column>
            <el-table-column label="追踪建议" width="110" align="center">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="trackTagType(row.trackLabel)"
                  style="cursor: pointer"
                  @click.stop="openRankDrawer(row)"
                >{{ row.trackLabel || '—' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="综合分" width="72" align="center">
              <template #default="{ row }">{{ row.trackScore == null ? '—' : row.trackScore }}</template>
            </el-table-column>
            <el-table-column prop="shopName" label="店铺" min-width="120" show-overflow-tooltip />
            <el-table-column label="用户支付金额" width="120" align="right">
              <template #default="{ row }">{{ formatMetricValue(row.payAmt) }}</template>
            </el-table-column>
            <el-table-column label="点击次数" width="100" align="right">
              <template #default="{ row }">{{ formatMetricValue(row.clickCnt) }}</template>
            </el-table-column>
            <el-table-column label="成交件数" width="100" align="right">
              <template #default="{ row }">{{ formatMetricValue(row.payCnt) }}</template>
            </el-table-column>
            <el-table-column label="点击成交转化率" width="120" align="right">
              <template #default="{ row }">
                {{ row.clickPayCvr == null || row.clickPayCvr === ''
                  ? '—'
                  : `${Number(row.clickPayCvr).toFixed(2)}%` }}
              </template>
            </el-table-column>
            <el-table-column label="商品曝光数" width="110" align="right" v-if="rankHasShowCnt">
              <template #default="{ row }">{{ formatMetricValue(row.showCnt) }}</template>
            </el-table-column>
            <el-table-column label="商品订单成交数" width="130" align="right" v-if="rankHasOrderCnt">
              <template #default="{ row }">{{ formatMetricValue(row.orderCnt) }}</template>
            </el-table-column>
            <el-table-column label="商品成交件数" width="120" align="right">
              <template #default="{ row }">{{ formatMetricValue(row.dealCnt ?? row.payCnt) }}</template>
            </el-table-column>
          </el-table>
        </TableQueryBar>
        <el-empty
          v-if="!loadingRank && !syncingRank && !rankProducts.length"
          description="暂无商品榜数据"
        />
        <el-drawer
          v-model="rankDrawerVisible"
          size="420px"
          :title="rankDrawerRow?.productName || '追踪分析'"
        >
          <template v-if="rankDrawerRow">
            <div class="opp-product-cell" style="margin-bottom: 12px">
              <el-image
                v-if="rankDrawerRow.mainImage"
                :src="rankDrawerRow.mainImage"
                class="product-thumb"
                fit="cover"
              />
              <div class="opp-product-cell__meta">
                <div class="opp-product-cell__title">{{ rankDrawerRow.productName }}</div>
                <div class="opp-product-cell__sub">{{ rankDrawerRow.shopName }} · {{ rankDrawerRow.productId }}</div>
              </div>
            </div>

            <div class="drawer-block">
              <h5 class="drawer-block__title">对照指标</h5>
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="排名">{{ rankDrawerRow.rankNo }} / 对照 {{ rankDrawerRow.peerRankNo ?? '—' }}</el-descriptions-item>
                <el-descriptions-item label="支付金额">{{ formatMetricValue(rankDrawerRow.payAmt) }} / {{ formatMetricValue(rankDrawerRow.peerMetrics?.payAmt) }}</el-descriptions-item>
                <el-descriptions-item label="点击">{{ formatMetricValue(rankDrawerRow.clickCnt) }} / {{ formatMetricValue(rankDrawerRow.peerMetrics?.clickCnt) }}</el-descriptions-item>
                <el-descriptions-item label="成交件数">{{ formatMetricValue(rankDrawerRow.payCnt) }} / {{ formatMetricValue(rankDrawerRow.peerMetrics?.payCnt) }}</el-descriptions-item>
                <el-descriptions-item label="转化率">{{ rankDrawerRow.clickPayCvr ?? '—' }} / {{ rankDrawerRow.peerMetrics?.clickPayCvr ?? '—' }}</el-descriptions-item>
                <el-descriptions-item v-if="rankDrawerRow.showCnt != null || rankHasShowCnt" label="曝光">{{ formatMetricValue(rankDrawerRow.showCnt) }} / {{ formatMetricValue(rankDrawerRow.peerMetrics?.showCnt) }}</el-descriptions-item>
                <el-descriptions-item label="订单成交">{{ formatMetricValue(rankDrawerRow.orderCnt) }} / {{ formatMetricValue(rankDrawerRow.peerMetrics?.orderCnt ?? rankDrawerRow.peerMetrics?.payCnt ?? rankDrawerRow.peerMetrics?.dealCnt) }}</el-descriptions-item>
                <el-descriptions-item label="成交额变化">{{ formatDeltaPct(rankDrawerRow.payAmtDeltaPct) }}</el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="drawer-block">
              <h5 class="drawer-block__title">追踪分析</h5>
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="综合分">{{ rankDrawerRow.trackScore ?? '—' }} · {{ rankDrawerRow.trackLabel || '—' }}</el-descriptions-item>
              </el-descriptions>
              <ul v-if="rankDrawerRow.trackReasons?.length" class="drawer-reasons">
                <li v-for="(r, i) in rankDrawerRow.trackReasons" :key="i">{{ r }}</li>
              </ul>
            </div>

            <div v-if="rankDrawerRow.watchHint || rankDrawerRow.followHint" class="drawer-block">
              <h5 class="drawer-block__title">行动建议</h5>
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item v-if="rankDrawerRow.watchHint" label="盯梢">{{ rankDrawerRow.watchHint }}</el-descriptions-item>
                <el-descriptions-item v-if="rankDrawerRow.followHint" label="跟卖">{{ rankDrawerRow.followHint }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </template>
        </el-drawer>
          </el-tab-pane>

          <el-tab-pane v-if="!operationalDemoOnly" label="商机中心" name="opportunity">
        <div class="detail-toolbar">
          <div class="detail-toolbar__filters">
            <el-radio-group v-model="opportunityPool" size="small">
              <el-radio-button
                v-for="opt in opportunityPoolOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
            <el-radio-group v-model="opportunitySort" size="small">
              <el-radio-button
                v-for="opt in opportunitySortOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
            <el-input
              v-model="opportunityCategoryQuery"
              clearable
              size="small"
              placeholder="类目搜索"
              class="detail-toolbar__search"
              @keyup.enter="handleSyncOpportunity"
            />
            <el-input
              v-if="opportunityProducts.length"
              v-model="opportunityKeyword"
              clearable
              size="small"
              placeholder="搜索标题 / 类目 / 搜索次数 / 成交金额"
              class="detail-toolbar__search detail-toolbar__search--wide"
            />
          </div>
          <div class="detail-toolbar__actions">
            <el-button
              type="primary"
              size="small"
              :loading="syncingOpportunity || loadingOpportunity"
              :disabled="!session.agent_online"
              @click="handleSyncOpportunity"
            >
              同步当前榜
            </el-button>
            <el-text
              v-if="opportunityCategoryName || opportunitySyncedAt || opportunityProducts.length"
              size="small"
              type="info"
              class="detail-toolbar__meta"
            >
              <template v-if="opportunityCategoryName">{{ opportunityCategoryName }}</template>
              <template v-if="opportunitySyncedAt">
                <template v-if="opportunityCategoryName"> · </template>同步 {{ formatUtc8(opportunitySyncedAt) }}
              </template>
              <template v-if="opportunityProducts.length">
                <template v-if="opportunityCategoryName || opportunitySyncedAt"> · </template>{{ opportunityProducts.length }} 条
              </template>
            </el-text>
          </div>
        </div>
        <TableQueryBar
          v-if="opportunityProducts.length"
          v-model:keyword="opportunityKeyword"
          v-model:page="opportunityPage"
          v-model:page-size="opportunityPageSize"
          :total="opportunityTotal"
          placeholder="搜索标题 / 类目 / 搜索次数 / 成交金额"
          :show-sizes="false"
          :show-search="false"
        >
          <el-table
            v-loading="loadingOpportunity || syncingOpportunity"
            :data="pagedOpportunity"
            size="small"
            stripe
            highlight-current-row
            class="opp-table"
            @row-click="openOpportunityOverview"
          >
            <el-table-column prop="rankNo" label="#" width="56" align="center" fixed />
            <el-table-column label="主图" width="72" align="center" fixed>
              <template #default="{ row }">
                <el-image
                  v-if="row.mainImage"
                  :src="row.mainImage"
                  fit="cover"
                  class="product-thumb"
                  :preview-src-list="[row.mainImage]"
                  preview-teleported
                  @click.stop
                />
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column prop="productName" label="标题" min-width="180" show-overflow-tooltip fixed />
            <el-table-column label="当日·搜索热度" width="120" align="right">
              <template #default="{ row }">{{ row.searchPopularity ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="当日·成交单量" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.payOrderCntRange || (row.payOrderCnt == null ? '—' : row.payOrderCnt) }}
              </template>
            </el-table-column>
            <el-table-column label="近7天·销量" width="110" align="right">
              <template #default="{ row }">{{ row.sevenDaySales ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="近30天·搜索次数" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.searchPvRange || '—' }}</template>
            </el-table-column>
            <el-table-column label="近30天·搜索增速" width="120" align="right">
              <template #default="{ row }">{{ formatGrowth(row.searchPv30dRate) }}</template>
            </el-table-column>
            <el-table-column label="近30天·成交金额" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.payAmtRange || '—' }}</template>
            </el-table-column>
            <el-table-column label="近30天·成交增速" width="120" align="right">
              <template #default="{ row }">{{ formatGrowth(row.payGrowthRate) }}</template>
            </el-table-column>
            <el-table-column label="供需比" width="100" align="right">
              <template #default="{ row }">
                {{ row.demandSupplyRate == null ? '—' : Number(row.demandSupplyRate).toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="categoryPath" label="类目" min-width="140" show-overflow-tooltip />
            <el-table-column label="标签" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                {{ Array.isArray(row.labels) && row.labels.length ? row.labels.join(' / ') : '—' }}
              </template>
            </el-table-column>
          </el-table>
        </TableQueryBar>
        <el-empty
          v-if="!loadingOpportunity && !syncingOpportunity && !opportunityProducts.length"
          description="暂无商机数据"
        />
        <el-drawer
          v-model="opportunityDrawer"
          title="商品详情"
          size="560px"
          destroy-on-close
          class="opp-detail-drawer"
        >
          <div v-loading="loadingOverview" class="opp-overview">
            <template v-if="opportunityOverview">
              <div class="opp-detail-head">
                <el-image
                  v-if="opportunityDetailMeta.image"
                  :src="opportunityDetailMeta.image"
                  fit="cover"
                  class="opp-detail-head__img"
                  :preview-src-list="[opportunityDetailMeta.image]"
                  preview-teleported
                />
                <div class="opp-detail-head__body">
                  <div class="opp-detail-head__title">{{ opportunityDetailMeta.title }}</div>
                  <div class="opp-detail-head__meta">{{ opportunityDetailMeta.category }}</div>
                  <div class="opp-detail-head__tags">
                    <el-tag
                      v-for="lab in opportunityDetailMeta.labels.slice(0, 4)"
                      :key="lab"
                      size="small"
                      effect="plain"
                      type="warning"
                    >
                      {{ lab }}
                    </el-tag>
                    <el-tag size="small" effect="plain">售价 {{ opportunityDetailMeta.price }}</el-tag>
                  </div>
                </div>
              </div>

              <div class="opp-trend">
                <div class="opp-trend__bar">
                  <span class="opp-trend__title">趋势概览</span>
                  <el-radio-group v-model="opportunityPeriodTab" size="small">
                    <el-radio-button
                      v-for="opt in opportunityPeriodOptions"
                      :key="opt.value"
                      :value="opt.value"
                    >
                      {{ opt.label }}
                    </el-radio-button>
                  </el-radio-group>
                </div>
                <div class="opp-trend__kpis">
                  <div v-for="kpi in opportunityTrendKpis" :key="kpi.label" class="opp-trend-kpi">
                    <div class="opp-trend-kpi__label">{{ kpi.label }}</div>
                    <div class="opp-trend-kpi__value">{{ kpi.value }}</div>
                    <div
                      class="opp-trend-kpi__trend"
                      :class="`is-${growthTone(kpi.trend)}`"
                    >
                      {{ kpi.trend == null || kpi.trend === '' ? '—' : formatGrowth(kpi.trend) }}
                    </div>
                  </div>
                </div>
              </div>

              <div class="opp-analysis">
                <div class="opp-analysis__title">商机详细分析</div>
                <div
                  v-for="(item, idx) in opportunityAnalysisItems"
                  :key="`${item.tag}-${idx}`"
                  class="opp-analysis__item"
                >
                  <el-tag size="small" type="danger" effect="plain">{{ item.tag }}</el-tag>
                  <span class="opp-analysis__text">{{ item.text }}</span>
                </div>
              </div>
            </template>
            <el-empty v-else-if="!loadingOverview" description="暂无概述" />
          </div>
        </el-drawer>
          </el-tab-pane>

          <el-tab-pane label="商品信息" name="catalog">
        <el-tabs v-model="activeTab" class="catalog-sub-tabs">
          <el-tab-pane name="products" label="商品">
            <div class="tab-panel">
              <div class="detail-toolbar">
                <div class="detail-toolbar__filters">
                  <el-radio-group v-model="productListTab" size="small">
                    <el-radio-button value="all">全部商品</el-radio-button>
                    <el-radio-button value="hot">
                      爆款商品
                      <el-badge
                        v-if="hotProducts.length"
                        :value="hotProducts.length"
                        type="danger"
                        class="product-list-tabs__badge"
                      />
                    </el-radio-button>
                    <el-radio-button value="todayHot">
                      今日爆款
                      <el-badge
                        v-if="todayHotProducts.length"
                        :value="todayHotProducts.length"
                        type="danger"
                        class="product-list-tabs__badge"
                      />
                    </el-radio-button>
                    <el-radio-button value="todayOrders">
                      今日销售订单
                      <el-badge
                        v-if="todaySalesOrders.length"
                        :value="todaySalesOrders.length"
                        type="success"
                        class="product-list-tabs__badge"
                      />
                    </el-radio-button>
                    <el-radio-button value="newSales">
                      新品销售
                      <el-badge
                        v-if="newListedProducts.length"
                        :value="newListedProducts.length"
                        type="info"
                        class="product-list-tabs__badge"
                      />
                    </el-radio-button>
                  </el-radio-group>
                  <el-input
                    v-if="showProductTable && productListSource.length"
                    v-model="productKeyword"
                    clearable
                    size="small"
                    placeholder="搜索标题 / ID / 货号 / 类目"
                    class="detail-toolbar__search"
                  />
                </div>
                <div class="detail-toolbar__actions">
                  <template v-if="productListTab !== 'todayOrders'">
                    <el-button
                      type="primary"
                      size="small"
                      :loading="syncingProducts || loadingProducts"
                      :disabled="!session.agent_online"
                      @click="handleSyncProducts"
                    >
                      同步商品
                    </el-button>
                    <el-text v-if="productsSyncedAt" size="small" type="info" class="detail-toolbar__meta">
                      同步 {{ formatUtc8(productsSyncedAt) }}
                    </el-text>
                  </template>
                </div>
              </div>

              <DomesticOrdersPanel
                v-if="productListTab === 'todayOrders'"
                :orders="todaySalesOrders"
                :synced-at="ordersSyncedAt"
                :loading="loadingOrders"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                :show-header="false"
                :show-mini-stats="false"
                show-channel-column
                action-label="同步订单"
                amount-label="今日金额"
                @refresh="handleSyncOrdersLogged"
                @ship-push="openShipDialog($event, 'push')"
                @ship-urge="openShipDialog($event, 'urge')"
              />

              <TableQueryBar
                v-if="showProductTable && productListSource.length"
                v-model:keyword="productKeyword"
                v-model:page="productPage"
                v-model:page-size="productPageSize"
                :total="productTotal"
                placeholder="搜索标题 / ID / 货号 / 类目"
                :show-sizes="false"
                :show-search="false"
              >
                <el-table :data="pagedProducts" size="small" stripe v-loading="loadingProducts || syncingProducts">
                  <el-table-column label="商品图片" width="72" align="center">
                    <template #default="{ row }">
                      <el-image
                        v-if="row.mainImage"
                        :src="row.mainImage"
                        fit="cover"
                        class="product-thumb"
                        :preview-src-list="[row.mainImage]"
                        preview-teleported
                      />
                      <span v-else>—</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="productName" label="标题" min-width="180" show-overflow-tooltip />
                  <el-table-column prop="productId" label="ID" min-width="140" show-overflow-tooltip />
                  <el-table-column v-if="showStoreColumn" label="店铺" width="120">
                    <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="状态" width="90">
                    <template #default="{ row }">{{ row.statusLabel || row.status || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="价格" width="90" align="right">
                    <template #default="{ row }">{{ row.price == null ? '—' : row.price }}</template>
                  </el-table-column>
                  <el-table-column label="库存" width="80" align="right">
                    <template #default="{ row }">{{ row.stock == null ? '—' : row.stock }}</template>
                  </el-table-column>
                  <el-table-column
                    :label="productListTab === 'todayHot' ? '近24h销量' : '销量'"
                    width="100"
                    align="right"
                    sortable
                  >
                    <template #default="{ row }">
                      <template v-if="productListTab === 'todayHot'">
                        <el-tag type="danger" size="small" effect="plain">
                          {{ row.todaySales ?? '—' }}
                        </el-tag>
                      </template>
                      <template v-else>
                        <el-tag
                          v-if="Number(row.sales) >= HOT_PRODUCT_SALES_MIN"
                          type="danger"
                          size="small"
                          effect="plain"
                        >
                          {{ row.sales }}
                        </el-tag>
                        <span v-else>{{ row.sales == null ? '—' : row.sales }}</span>
                      </template>
                    </template>
                  </el-table-column>
                  <el-table-column prop="articleNo" label="货号" min-width="100" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.articleNo || '—' }}</template>
                  </el-table-column>
                  <el-table-column prop="category" label="类目" min-width="140" show-overflow-tooltip />
                  <el-table-column label="质量分" width="80" align="right">
                    <template #default="{ row }">{{ row.qualityScore == null ? '—' : row.qualityScore }}</template>
                  </el-table-column>
                  <el-table-column prop="publishedAt" label="上架时间" min-width="150" show-overflow-tooltip>
                    <template #default="{ row }">{{ formatUtc8(row.publishedAt) }}</template>
                  </el-table-column>
                  <el-table-column label="好评率" width="90" align="right">
                    <template #default="{ row }">
                      {{ row.goodRate == null ? '—' : `${row.goodRate}%` }}
                    </template>
                  </el-table-column>
                </el-table>
              </TableQueryBar>
              <el-empty
                v-if="
                  showProductTable
                    && !loadingProducts
                    && !syncingProducts
                    && !(productListTab === 'todayHot' && loadingOrders)
                    && !productListSource.length
                "
                :description="
                  productListTab === 'hot'
                    ? `暂无爆款（销量 ≥ ${HOT_PRODUCT_SALES_MIN}）`
                    : productListTab === 'todayHot'
                      ? `暂无今日爆款（近24h 有效销量 ≥ ${HOT_PRODUCT_SALES_MIN}）`
                      : productListTab === 'newSales'
                        ? '暂无近3天上架的新品'
                        : '暂无商品'
                "
              />
            </div>
          </el-tab-pane>

          <el-tab-pane name="orders">
            <template #label>
              <span>近24小时订单</span>
              <el-badge v-if="pendingOrderCount" :value="pendingOrderCount" class="tab-badge" />
            </template>
            <div class="tab-panel">
              <DomesticOrdersPanel
                :orders="filteredOrders"
                :synced-at="ordersSyncedAt"
                :loading="loadingOrders"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                :show-header="false"
                :show-mini-stats="false"
                show-channel-column
                action-label="同步近24小时订单"
                amount-label="近24小时金额"
                @refresh="handleSyncOrdersLogged"
                @ship-push="openShipDialog($event, 'push')"
                @ship-urge="openShipDialog($event, 'urge')"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane name="issues">
            <template #label>
              <span>内容预警</span>
              <el-badge v-if="pendingIssueCount" :value="pendingIssueCount" class="tab-badge" />
            </template>
            <div class="tab-panel">
              <DomesticIssuesPanel
                ref="issuesPanel"
                :issues="filteredIssues"
                :synced-at="issuesSyncedAt"
                :loading="loadingIssues"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                :initial-filter="issuesFilter"
                :show-header="false"
                @refresh="handleSyncIssuesLogged"
                @resolve="handleResolveIssue"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
          </el-tab-pane>
        </el-tabs>
      </PageSection>

      <PlatformShipPushDialog
        v-model="shipDialogVisible"
        :order="shipDialogOrder"
        platform-key="douyin"
        :platform-label="platformLabel"
        :store-name="shipDialogOrder ? storeNameMap[shipDialogOrder.storeId] : ''"
        :request-type="shipDialogType"
        :submitting="shipSubmitting"
        @submit="submitShipPush"
      />

      <DouyinSyncLogDrawer v-model="syncLogOpen" :run="syncRun" />
      <SyncHistoryDrawer
        v-model="syncHistoryOpen"
        platform="douyin"
        :fetcher="() => fetchPlatformSyncLogs({ platform: 'douyin' })"
      />
    </template>
  </PageScroll>
</template>

<style scoped>
.douyin-top :deep(.page-header) {
  margin-bottom: 0;
}

.douyin-store-switch {
  max-width: min(100%, 560px);
  flex-wrap: wrap;
}

.douyin-empty-actions {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.douyin-sync-bar {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  border-radius: 8px;
  background: var(--ch-surface, var(--el-fill-color-blank));
}

.douyin-sync-bar__main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
}

.session-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 4px 0 0;
  align-items: center;
}

.full-sync-progress {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.full-sync-progress.is-clickable {
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  color: var(--el-color-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.full-sync-progress.is-clickable:hover {
  color: var(--el-color-primary-light-3);
}

.advanced-sync {
  margin: 0 0 8px;
}

.advanced-sync :deep(.el-collapse-item__header) {
  height: auto;
  line-height: 1.4;
  padding: 8px 0;
  font-size: 13px;
}

.advanced-sync :deep(.el-collapse-item__content) {
  padding-bottom: 4px;
}

.advanced-sync .session-actions {
  margin: 0;
}

.cockpit {
  display: grid;
  gap: 14px;
  min-height: 120px;
}

.period-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding: 10px 12px;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  border-radius: var(--ch-radius-md, 10px);
  background: var(--ch-surface-muted, var(--el-fill-color-lighter));
}

.period-bar__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ch-text-secondary, var(--el-text-color-regular));
}

.period-bar__note {
  margin-left: auto;
  font-size: 12px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.seg {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
}

.seg button {
  border: none;
  background: transparent;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--ch-text-secondary, var(--el-text-color-regular));
  cursor: pointer;
  line-height: 1.4;
}

.seg button.is-active {
  background: var(--ch-primary-soft, #edf2ff);
  color: var(--ch-primary, #1f4fd6);
  font-weight: 600;
}

.cockpit-hero {
  display: grid;
  grid-template-columns: minmax(200px, 240px) 1fr;
  gap: 12px;
  align-items: stretch;
}

.cockpit-exp {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  border-radius: var(--ch-radius-md, 10px);
  background: linear-gradient(165deg, #f7f9fc 0%, #fff 55%);
}

.cockpit-exp.is-empty {
  opacity: 0.72;
}

.cockpit-exp__score {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cockpit-exp__score-label {
  font-size: 12px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.cockpit-exp__score-value {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--ch-text, var(--el-text-color-primary));
  letter-spacing: -0.03em;
}

.cockpit-exp__score-value em {
  font-style: normal;
  font-size: 13px;
  font-weight: 500;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
  margin-left: 4px;
}

.cockpit-exp__parts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.cockpit-exp__part {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--ch-border, var(--el-border-color-extra-light));
}

.cockpit-exp__part-label {
  font-size: 11px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.cockpit-exp__part-value {
  font-size: 14px;
  font-weight: 600;
}

.cockpit-hero-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.cockpit-hero-kpi {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 14px 14px 12px;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  border-radius: var(--ch-radius-md, 10px);
  background: var(--ch-surface, #fff);
  text-align: left;
}

.cockpit-hero-kpi--action {
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.cockpit-hero-kpi--action:hover {
  border-color: var(--ch-primary-muted, #93c5fd);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.06);
}

.cockpit-hero-kpi--action.is-hot .cockpit-hero-kpi__value {
  color: var(--ch-error, #c81e45);
}

.cockpit-hero-kpi__value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: var(--ch-text, var(--el-text-color-primary));
}

.cockpit-hero-kpi__label {
  font-size: 12px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.cockpit-hero-kpi__delta {
  font-size: 11px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.cockpit-hero-kpi__delta.is-up {
  color: var(--ch-success, #0d8f66);
}

.cockpit-hero-kpi__delta.is-down {
  color: var(--ch-error, #c81e45);
}

.viz-panel {
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  border-radius: var(--ch-radius-md, 10px);
  background: var(--ch-surface, #fff);
  overflow: hidden;
}

.viz-panel__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--ch-border, var(--el-border-color-lighter));
  background: var(--ch-surface-muted, var(--el-fill-color-lighter));
}

.viz-panel__title {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}

.viz-panel__period-tag {
  font-size: 12px;
  color: var(--ch-primary, #1f4fd6);
  background: var(--ch-primary-soft, #edf2ff);
  border: 1px solid var(--ch-primary-muted, #c5d4f7);
  border-radius: 999px;
  padding: 2px 10px;
}

.viz-tabs {
  display: inline-flex;
  margin-left: auto;
  padding: 2px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
}

.viz-tabs button {
  border: none;
  background: transparent;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--ch-text-secondary, var(--el-text-color-regular));
  cursor: pointer;
}

.viz-tabs button.is-active {
  background: var(--ch-primary-soft, #edf2ff);
  color: var(--ch-primary, #1f4fd6);
  font-weight: 600;
}

.viz-panel__body {
  padding: 12px;
  min-height: 300px;
}

.viz-layout {
  display: grid;
  grid-template-columns: 1fr minmax(260px, 320px);
  gap: 12px;
  align-items: stretch;
}

.viz-layout__chart {
  min-width: 0;
}

.metric-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  align-content: start;
}

.metric-card {
  padding: 12px;
  border-radius: var(--ch-radius-sm, 8px);
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  background: var(--ch-surface-muted, var(--el-fill-color-lighter));
}

.metric-card__label {
  font-size: 12px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
  margin-bottom: 4px;
}

.metric-card__value {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.metric-card__sub {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.ops-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.ops-stat {
  display: block;
  width: 100%;
  padding: 12px 14px;
  border-radius: var(--ch-radius-sm, 8px);
  background: var(--ch-surface-muted, var(--el-fill-color-lighter));
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  text-align: left;
  cursor: default;
  color: inherit;
  font: inherit;
}

button.ops-stat {
  cursor: pointer;
  transition: border-color 0.15s ease;
}

button.ops-stat:hover {
  border-color: var(--ch-primary-muted, #c5d4f7);
}

.ops-stat strong {
  display: block;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.ops-stat span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

.ops-stat.is-warn strong {
  color: var(--ch-warning, #c47a06);
}

.ops-stat.is-danger strong {
  color: var(--ch-error, #c81e45);
}

.cockpit-card {
  padding: 12px 14px 14px;
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  border-radius: var(--ch-radius-md, 10px);
  background: var(--ch-surface, #fff);
}

.cockpit-card--ops {
  padding-top: 12px;
}

.cockpit-card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.cockpit-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ch-text, var(--el-text-color-primary));
}

@media (max-width: 1100px) {
  .cockpit-hero,
  .viz-layout {
    grid-template-columns: 1fr;
  }

  .cockpit-hero-kpis,
  .ops-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .viz-tabs,
  .period-bar__note {
    margin-left: 0;
  }
}

@media (max-width: 640px) {
  .cockpit-hero-kpis,
  .metric-cards,
  .ops-row {
    grid-template-columns: 1fr 1fr;
  }
}

.detail-tabs {
  margin-top: 4px;
}

.detail-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px 16px;
  margin-bottom: 12px;
}

.detail-toolbar__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 8px 10px;
  flex: 1;
  min-width: 0;
}

.detail-toolbar__search {
  width: min(220px, 100%);
}

.detail-toolbar__search--wide {
  width: min(280px, 100%);
}

.detail-toolbar__actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.detail-toolbar__meta {
  text-align: right;
  line-height: 1.3;
}

.catalog-sub-tabs {
  margin-top: 8px;
}

.tab-panel {
  padding: 16px 0 4px;
}

.tab-badge {
  margin-left: 6px;
  vertical-align: middle;
}

.tab-badge :deep(.el-badge__content) {
  position: relative;
  transform: none;
  vertical-align: middle;
}

.product-list-tabs {
  margin-bottom: 12px;
}

.product-list-tabs__badge {
  margin-left: 6px;
  vertical-align: middle;
}

.product-hot-hint {
  margin-bottom: 12px;
}

.opp-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 8px 0 12px;
}

.opp-table {
  cursor: pointer;
}

.opp-overview__title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 6px;
}

.opp-overview__meta {
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
}

.opp-overview__desc {
  margin-bottom: 12px;
}

.opp-overview__json {
  max-height: 420px;
  overflow: auto;
  padding: 10px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.opp-detail-head {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.opp-detail-head__img {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  flex-shrink: 0;
}

.opp-detail-head__body {
  min-width: 0;
  flex: 1;
}

.opp-detail-head__title {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.35;
}

.opp-detail-head__meta {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.opp-detail-head__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.opp-trend {
  margin-bottom: 18px;
}

.opp-trend__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.opp-trend__title {
  font-weight: 600;
}

.opp-trend__kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.opp-trend-kpi {
  padding: 10px 8px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  text-align: center;
}

.opp-trend-kpi__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.opp-trend-kpi__value {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 650;
  line-height: 1.25;
  word-break: break-all;
}

.opp-trend-kpi__trend {
  margin-top: 6px;
  font-size: 12px;
}

.opp-trend-kpi__trend.is-up {
  color: var(--el-color-success);
}

.opp-trend-kpi__trend.is-down {
  color: var(--el-color-danger);
}

.opp-trend-kpi__trend.is-muted {
  color: var(--el-text-color-secondary);
}

.opp-analysis__title {
  font-weight: 600;
  margin-bottom: 10px;
}

.opp-analysis__item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}

.opp-analysis__text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
}

@media (max-width: 640px) {
  .opp-trend__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.product-thumb {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  flex-shrink: 0;
}

.opp-product-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.opp-product-cell__meta {
  min-width: 0;
  flex: 1;
}

.opp-product-cell__title {
  font-size: 13px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.opp-product-cell__sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-block {
  margin-bottom: 14px;
  padding: 12px;
  border-radius: var(--ch-radius-md, 10px);
  border: 1px solid var(--ch-border, var(--el-border-color-lighter));
  background: var(--ch-surface-muted, var(--el-fill-color-lighter));
}

.drawer-block__title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 650;
}

.drawer-reasons {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--ch-text-secondary, var(--el-text-color-regular));
}

.drawer-reasons li + li {
  margin-top: 4px;
}

.rank-delta.is-up {
  color: var(--el-color-success);
}

.rank-delta.is-down {
  color: var(--el-color-danger);
}

.rank-delta.is-new {
  color: var(--el-color-primary);
}
</style>
