import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { scopeStores } from '@/utils/scope'
import { useStoreAssignees } from '@/composables/useStoreAssignees'
import { enrichDomesticIssue } from '@/utils/domesticPlatform'
import { domesticPlatformLabel } from '@/constants/platforms'
import { isPlatformOperationalDemoOnly, platformOperationalHint } from '@/utils/platformOperationalMode'
import { pushPlatformOrderToWarehouse, enrichOrdersWithWarehouseFeedback } from '@/api/platformShipRequests'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import DomesticBossOverview from '@/components/domestic/DomesticBossOverview.vue'
import DomesticOrdersPanel from '@/components/domestic/DomesticOrdersPanel.vue'
import DomesticIssuesPanel from '@/components/domestic/DomesticIssuesPanel.vue'
import PlatformShipPushDialog from '@/components/domestic/PlatformShipPushDialog.vue'

export function useDomesticModule(config) {
  const auth = useAuthStore()
  const { assigneeMap, loadAssignees, enrichItems } = useStoreAssignees()
  const router = useRouter()

  const activeTab = ref('orders')
  const selectedStoreId = ref('all')
  const stores = ref([])
  const todayOrders = ref([])
  const issues = ref([])
  const ordersSyncedAt = ref('')
  const issuesSyncedAt = ref('')
  const loadingStores = ref(false)
  const loadingOrders = ref(false)
  const loadingIssues = ref(false)
  const issuesPanel = ref(null)
  const issuesFilter = ref('all')
  const shipDialogVisible = ref(false)
  const shipDialogOrder = ref(null)
  const shipDialogType = ref('push')
  const shipSubmitting = ref(false)

  const platformKey = config.platformKey || ''
  const platformLabel = computed(() => domesticPlatformLabel(platformKey) || platformKey)
  const operationalDemoOnly = computed(() => isPlatformOperationalDemoOnly(platformKey))
  const operationalHint = computed(() => platformOperationalHint(platformKey))

  const storeNameMap = computed(() =>
    Object.fromEntries(stores.value.map((store) => [store.id, store.storeName])),
  )

  const enrichedOrders = computed(() => enrichItems(todayOrders.value))
  const enrichedIssues = computed(() =>
    enrichItems(issues.value.map((issue) => enrichDomesticIssue(issue, config.issueTypeMap))),
  )

  const showStoreColumn = computed(() => selectedStoreId.value === 'all')
  const showStoreList = computed(() => selectedStoreId.value === 'all' && stores.value.length > 0)

  const overviewStores = computed(() => {
    if (selectedStoreId.value === 'all') return stores.value
    return stores.value.filter((store) => store.id === selectedStoreId.value)
  })

  const filteredOrders = computed(() => {
    if (selectedStoreId.value === 'all') return enrichedOrders.value
    return enrichedOrders.value.filter((order) => order.storeId === selectedStoreId.value)
  })

  const filteredIssues = computed(() => {
    if (selectedStoreId.value === 'all') return enrichedIssues.value
    return enrichedIssues.value.filter((item) => item.storeId === selectedStoreId.value)
  })

  const pendingOrderCount = computed(() =>
    filteredOrders.value.filter((order) => ['待处理', '待发货'].includes(order.status)).length,
  )

  const pendingIssueCount = computed(() =>
    filteredIssues.value.filter((item) => !item.resolved).length,
  )

  async function syncTodayOrders(refresh = false) {
    if (operationalDemoOnly.value || !stores.value.length) {
      todayOrders.value = []
      ordersSyncedAt.value = ''
      return
    }

    loadingOrders.value = true
    try {
      const res = await config.fetchOrders(stores.value, { refresh })
      todayOrders.value = await enrichOrdersWithWarehouseFeedback(res.data.orders || [], auth)
      ordersSyncedAt.value = res.data.syncedAt
      if (refresh) ElMessage.success(res.message || '已刷新订单')
    } catch (err) {
      ElMessage.error(err.message || '订单抓取失败')
    } finally {
      loadingOrders.value = false
    }
  }

  async function syncIssues(refresh = false) {
    if (operationalDemoOnly.value || !stores.value.length) {
      issues.value = []
      issuesSyncedAt.value = ''
      return
    }

    loadingIssues.value = true
    try {
      const res = refresh
        ? await config.crawlIssues(stores.value, { refresh: true })
        : await config.loadIssues(stores.value)
      issues.value = res.data.issues
      issuesSyncedAt.value = res.data.syncedAt
      if (refresh) ElMessage.success(res.message || '已刷新运营预警')
    } catch (err) {
      ElMessage.error(err.message || '预警抓取失败')
    } finally {
      loadingIssues.value = false
    }
  }

  async function handleResolveIssue(payload) {
    try {
      const res = await config.resolveIssue(payload.id, payload)
      const index = issues.value.findIndex((item) => item.id === payload.id)
      if (index !== -1) issues.value[index] = res.data
      ElMessage.success('已标记为已解决')
    } catch (err) {
      ElMessage.error(err.message || '操作失败')
    } finally {
      issuesPanel.value?.finishResolve?.()
    }
  }

  async function loadModule() {
    loadingStores.value = true
    try {
      const res = await config.fetchStores()
      stores.value = scopeStores(res.data || [], auth)
      if (stores.value.length) {
        await Promise.all([syncTodayOrders(false), syncIssues(false)])
      } else {
        todayOrders.value = []
        issues.value = []
        ordersSyncedAt.value = ''
        issuesSyncedAt.value = ''
      }
    } catch {
      stores.value = []
      todayOrders.value = []
      issues.value = []
      ordersSyncedAt.value = ''
      issuesSyncedAt.value = ''
    } finally {
      loadingStores.value = false
    }
  }

  function goToAccountBinding() {
    router.push(auth.isBoss ? '/boss/accounts' : '/employee/dashboard')
  }

  function handleOverviewNavigate(target) {
    if (target.startsWith('issues')) {
      activeTab.value = 'issues'
      const filter = target === 'issues:high' ? 'high' : 'open'
      issuesFilter.value = filter
      issuesPanel.value?.setFilter?.(filter)
      return
    }
    activeTab.value = target
  }

  function openShipDialog(order, type) {
    shipDialogOrder.value = order
    shipDialogType.value = type
    shipDialogVisible.value = true
  }

  async function submitShipPush({ warehouseId, type, remark }) {
    if (!shipDialogOrder.value || !platformKey) return
    shipSubmitting.value = true
    try {
      const res = await pushPlatformOrderToWarehouse(auth, {
        platformKey,
        order: shipDialogOrder.value,
        storeName: storeNameMap.value[shipDialogOrder.value.storeId] || '',
        warehouseId,
        type,
        remark,
      })
      const updated = res.data?.platformOrder
      if (updated) {
        const index = todayOrders.value.findIndex((item) => item.id === updated.id)
        if (index !== -1) todayOrders.value[index] = updated
      }
      ElMessage.success(res.message)
      shipDialogVisible.value = false
    } catch (err) {
      ElMessage.error(err.message || '操作失败')
    } finally {
      shipSubmitting.value = false
    }
  }

  watch(stores, (list) => {
    if (selectedStoreId.value === 'all') return
    if (!list.some((store) => store.id === selectedStoreId.value)) {
      selectedStoreId.value = 'all'
    }
  })

  onMounted(async () => {
    await loadAssignees()
    await loadModule()
  })
  onActivated(loadModule)

  return {
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
    handleOverviewNavigate,
    openShipDialog,
    submitShipPush,
    shipDialogVisible,
    shipDialogOrder,
    shipDialogType,
    shipSubmitting,
    platformKey,
    platformLabel,
    operationalDemoOnly,
    operationalHint,
    config,
  }
}
