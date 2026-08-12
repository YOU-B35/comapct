<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { usePlatformSyncStore } from '@/stores/platformSync'
import { buildPlatformSyncTargets } from '@/api/platformSync'
import {
  loadAliExpressOperationalData,
  fetchTodayAliExpressOrders,
  loadAliExpressViolations,
  crawlAliExpressViolations,
  confirmAliExpressViolationAppeal,
} from '@/api/aliexpress'
import { bootstrapAliExpressHotBroadcasts } from '@/api/aliexpressHotBroadcast'
import { fetchAliExpressStores } from '@/api/platformAccounts'
import { scopeStores } from '@/utils/scope'
import { useStoreAssignees } from '@/composables/useStoreAssignees'
import { enrichAllProducts } from '@/utils/temu'
import { isPlatformOperationalDemoOnly, platformOperationalHint } from '@/utils/platformOperationalMode'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import AliExpressBossOverview from '@/components/aliexpress/AliExpressBossOverview.vue'
import AliExpressOrdersPanel from '@/components/aliexpress/AliExpressOrdersPanel.vue'
import AliExpressViolationsPanel from '@/components/aliexpress/AliExpressViolationsPanel.vue'
import AliExpressHotBroadcast from '@/components/aliexpress/AliExpressHotBroadcast.vue'
import HelperStatusBar from '@/components/helper/HelperStatusBar.vue'
import { canUsePlatformUserHelper } from '@/utils/opsSyncPolicy'

const auth = useAuthStore()
const syncStore = usePlatformSyncStore()
const { assigneeMap, loadAssignees, enrichItems } = useStoreAssignees()
const router = useRouter()
const activeTab = ref('orders')
const selectedStoreId = ref('all')
const aliexpressStores = ref([])
const rawProducts = ref([])
const hotBroadcasts = ref([])
const todayOrders = ref([])
const violations = ref([])
const ordersSyncedAt = ref('')
const violationsSyncedAt = ref('')
const loadingStores = ref(false)
const loadingOrders = ref(false)
const loadingViolations = ref(false)
const violationsPanel = ref(null)
const violationsFilter = ref('all')
const helperOnline = ref(false)

const showHelperBar = computed(() => canUsePlatformUserHelper(auth))

function onHelperOnline(online) {
  helperOnline.value = Boolean(online)
}

const operationalDemoOnly = computed(() => isPlatformOperationalDemoOnly('aliexpress'))
const operationalHint = computed(() => platformOperationalHint('aliexpress'))

const storeNameMap = computed(() =>
  Object.fromEntries(aliexpressStores.value.map((store) => [store.id, store.storeName])),
)

const products = computed(() => {
  let list = enrichItems(
    enrichAllProducts(rawProducts.value).map((product) => ({
      ...product,
      storeName: storeNameMap.value[product.storeId] || '未分配店铺',
    })),
  )
  if (selectedStoreId.value !== 'all') {
    list = list.filter((product) => product.storeId === selectedStoreId.value)
  }
  return list
})

const enrichedOrders = computed(() => enrichItems(todayOrders.value))
const enrichedViolations = computed(() => enrichItems(violations.value))

const broadcasts = computed(() => hotBroadcasts.value)

async function ensurePlatformSyncSeeded() {
  if (!auth.backendLinked || syncStore.hasItems) return
  try {
    const targets = await buildPlatformSyncTargets(auth)
    if (targets.length) syncStore.updateItems(targets)
  } catch {
    // best effort
  }
}

function markSidebarAliExpressSync({ status = 'success', message = '' } = {}) {
  if (operationalDemoOnly.value || !aliexpressStores.value.length) return
  for (const store of aliexpressStores.value) {
    const orderCount = todayOrders.value.filter((order) => order.storeId === store.id).length
    const violationCount = violations.value.filter((item) => item.storeId === store.id).length
    const productCount = products.value.filter((product) => product.storeId === store.id).length
    const rowCount = orderCount + violationCount + productCount
    const resolvedStatus = rowCount > 0 ? status : 'empty'
    const resolvedMessage = message || (() => {
      const parts = []
      if (orderCount > 0) parts.push(`${orderCount} 笔今日订单`)
      if (violationCount > 0) parts.push(`${violationCount} 条违规`)
      if (productCount > 0) parts.push(`${productCount} 个商品`)
      return parts.length ? `已同步 ${parts.join('、')}` : '暂无 AliExpress 入库数据'
    })()
    syncStore.updateStoreStatus({
      platform: 'aliexpress',
      storeId: store.id,
      storeName: store.storeName,
      externalShopId: store.externalShopId || '',
      status: resolvedStatus,
      message: resolvedMessage,
      rowCount,
      syncedAt: ordersSyncedAt.value || violationsSyncedAt.value,
    })
  }
}

async function loadHotBroadcastFeed() {
  hotBroadcasts.value = await bootstrapAliExpressHotBroadcasts(auth, {
    storeId: selectedStoreId.value,
  })
}

function onBroadcastsUpdate(list) {
  hotBroadcasts.value = list
}

const showStoreColumn = computed(() => selectedStoreId.value === 'all')

const showStoreList = computed(
  () => selectedStoreId.value === 'all' && aliexpressStores.value.length > 0,
)

const overviewStores = computed(() => {
  if (selectedStoreId.value === 'all') {
    return aliexpressStores.value
  }
  return aliexpressStores.value.filter((store) => store.id === selectedStoreId.value)
})

const filteredOrders = computed(() => {
  if (selectedStoreId.value === 'all') return enrichedOrders.value
  return enrichedOrders.value.filter((order) => order.storeId === selectedStoreId.value)
})

const filteredViolations = computed(() => {
  if (selectedStoreId.value === 'all') return enrichedViolations.value
  return enrichedViolations.value.filter((item) => item.storeId === selectedStoreId.value)
})

const pendingOrderCount = computed(() =>
  filteredOrders.value.filter((order) =>
    order.fulfillmentType === 'jit'
      ? ['待发货', '待揽收'].includes(order.status)
      : order.status === '待出库',
  ).length,
)

const pendingViolationCount = computed(() =>
  filteredViolations.value.filter((item) => !item.confirmed).length,
)

const hotProductCount = computed(() => products.value.filter((product) => product.isHot).length)

async function syncTodayOrders(refresh = false) {
  if (!aliexpressStores.value.length) {
    todayOrders.value = []
    ordersSyncedAt.value = ''
    return
  }

  loadingOrders.value = true
  try {
    const res = await fetchTodayAliExpressOrders(aliexpressStores.value, { refresh, auth })
    todayOrders.value = res.data.orders
    ordersSyncedAt.value = res.data.syncedAt
    if (refresh) {
      ElMessage.success(res.message || '已刷新当日订单')
    }
  } catch (err) {
    ElMessage.error(err.message || '订单抓取失败')
  } finally {
    loadingOrders.value = false
  }
}

async function syncViolations(refresh = false) {
  if (!aliexpressStores.value.length) {
    violations.value = []
    violationsSyncedAt.value = ''
    return
  }

  loadingViolations.value = true
  try {
    const res = refresh
      ? await crawlAliExpressViolations(aliexpressStores.value, { refresh: true, auth })
      : await loadAliExpressViolations(aliexpressStores.value, auth)
    violations.value = res.data.violations
    violationsSyncedAt.value = res.data.syncedAt
    if (refresh) {
      ElMessage.success(res.message || '已刷新违规信息')
    }
  } catch (err) {
    ElMessage.error(err.message || '违规信息抓取失败')
  } finally {
    loadingViolations.value = false
  }
}

async function handleConfirmViolation(payload) {
  try {
    const res = await confirmAliExpressViolationAppeal(payload.id, {
      appealStatus: payload.appealStatus,
      appealResult: payload.appealResult,
      appealNote: payload.appealNote,
    }, auth)
    const index = violations.value.findIndex((item) => item.id === payload.id)
    if (index !== -1) {
      violations.value[index] = res.data
    }
    ElMessage.success('申诉状态已确认')
  } catch (err) {
    ElMessage.error(err.message || '确认失败')
  } finally {
    violationsPanel.value?.finishConfirm?.()
  }
}

async function loadAliExpressModule() {
  loadingStores.value = true
  let stores = []
  try {
    const res = await fetchAliExpressStores()
    stores = scopeStores(res.data || [], auth)
    aliexpressStores.value = stores
  } catch (err) {
    aliexpressStores.value = []
    ElMessage.error(err.message || '加载 AliExpress 店铺失败')
    return
  } finally {
    loadingStores.value = false
  }

  if (!stores.length) {
    rawProducts.value = []
    hotBroadcasts.value = []
    todayOrders.value = []
    violations.value = []
    ordersSyncedAt.value = ''
    violationsSyncedAt.value = ''
    return
  }

  try {
    const demoRes = await loadAliExpressOperationalData(stores, auth)
    rawProducts.value = demoRes.products || demoRes.data?.products || []
    await loadHotBroadcastFeed()
    await Promise.all([syncTodayOrders(false), syncViolations(false)])
    markSidebarAliExpressSync()
  } catch (err) {
    ElMessage.warning(err.message || '运营数据加载失败，店铺列表仍可用')
  }
}

async function reloadOperationalBundle() {
  const data = await loadAliExpressOperationalData(aliexpressStores.value, auth)
  rawProducts.value = data.products || []
  await loadHotBroadcastFeed()
}

async function handleRefreshAll() {
  if (!aliexpressStores.value.length) return
  loadingOrders.value = true
  loadingViolations.value = true
  try {
    const orderRes = await fetchTodayAliExpressOrders(aliexpressStores.value, { refresh: true, auth })
    todayOrders.value = orderRes.data.orders
    ordersSyncedAt.value = orderRes.data.syncedAt
    await reloadOperationalBundle()
    const violationRes = await loadAliExpressViolations(aliexpressStores.value, auth)
    violations.value = violationRes.data.violations
    violationsSyncedAt.value = violationRes.data.syncedAt
    ElMessage.success(
      orderRes.message
        || `已同步 ${todayOrders.value.length} 笔订单、${violations.value.length} 条违规`,
    )
    markSidebarAliExpressSync()
  } catch (err) {
    ElMessage.error(err.message || '同步失败')
  } finally {
    loadingOrders.value = false
    loadingViolations.value = false
  }
}

function goToAccountBinding() {
  router.push(auth.isBoss ? '/boss/accounts' : '/employee/dashboard')
}

function handleOverviewNavigate(target) {
  if (target.startsWith('violations')) {
    activeTab.value = 'violations'
    const filter = target === 'violations:pending' ? 'result_pending' : 'pending'
    violationsFilter.value = filter
    violationsPanel.value?.setFilter?.(filter)
    return
  }
  activeTab.value = target
}

watch(aliexpressStores, (stores) => {
  if (selectedStoreId.value === 'all') return
  if (!stores.some((store) => store.id === selectedStoreId.value)) {
    selectedStoreId.value = 'all'
  }
})

watch(selectedStoreId, () => {
  loadHotBroadcastFeed()
})

onMounted(async () => {
  await ensurePlatformSyncSeeded()
  await loadAssignees()
  await loadAliExpressModule()
})
onActivated(loadAliExpressModule)
</script>

<template>
  <PageScroll>
    <template #header>
      <div v-if="aliexpressStores.length" class="page-toolbar">
        <el-space wrap>
          <el-radio-group v-model="selectedStoreId" size="small">
            <el-radio-button value="all">全部店铺</el-radio-button>
            <el-radio-button
              v-for="store in aliexpressStores"
              :key="store.id"
              :value="store.id"
            >
              {{ store.storeName }}
            </el-radio-button>
          </el-radio-group>
          <el-button
            type="primary"
            size="small"
            :icon="Refresh"
            :loading="loadingOrders || loadingViolations"
            :disabled="showHelperBar && !helperOnline"
            @click="handleRefreshAll"
          >
            同步数据
          </el-button>
          <el-text v-if="ordersSyncedAt" size="small" type="info">
            订单 {{ ordersSyncedAt }}
          </el-text>
        </el-space>
      </div>

      <PageHeader
        v-else-if="!aliexpressStores.length && !auth.isBoss"
        title="AliExpress 运营"
        :description="`${auth.employee.name} · 订单处理与爆款跟进`"
      />
    </template>

    <HelperStatusBar
      v-if="showHelperBar"
      platform="aliexpress"
      @update:online="onHelperOnline"
    />

    <el-empty
      v-if="!loadingStores && !aliexpressStores.length"
      description="暂无可见的 AliExpress 店铺"
      :image-size="96"
    >
      <el-text type="info" size="small">
        {{
          auth.isBoss
            ? '请先在「账户绑定」中绑定速卖通店铺；本机可先下载并绑定 Sync Helper'
            : '请联系企业管理员分配负责店铺；本机可先下载并绑定 Sync Helper'
        }}
      </el-text>
      <el-button v-if="auth.isBoss" type="primary" style="margin-top: 16px" @click="goToAccountBinding">
        前往账户绑定
      </el-button>
    </el-empty>

    <template v-else-if="aliexpressStores.length">
      <el-alert
        v-if="operationalDemoOnly && operationalHint"
        :title="operationalHint"
        type="info"
        show-icon
        :closable="false"
        class="operational-hint"
      />

      <AliExpressBossOverview
        v-if="auth.isBoss"
        :orders="filteredOrders"
        :violations="filteredViolations"
        :products="products"
        :stores="overviewStores"
        :assignee-map="assigneeMap"
        :show-store-list="showStoreList"
        @navigate="handleOverviewNavigate"
      />

      <el-tabs v-model="activeTab" class="module-tabs">
        <el-tab-pane name="orders">
          <template #label>
            <span>今日订单</span>
            <el-badge v-if="pendingOrderCount" :value="pendingOrderCount" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AliExpressOrdersPanel
              :orders="filteredOrders"
              :synced-at="ordersSyncedAt"
              :loading="loadingOrders"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncTodayOrders(true)"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="violations">
          <template #label>
            <span>违规处理</span>
            <el-badge v-if="pendingViolationCount" :value="pendingViolationCount" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AliExpressViolationsPanel
              ref="violationsPanel"
              :violations="filteredViolations"
              :synced-at="violationsSyncedAt"
              :loading="loadingViolations"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              :initial-filter="violationsFilter"
              @refresh="syncViolations(true)"
              @confirm="handleConfirmViolation"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="hot">
          <template #label>
            <span>爆款通报</span>
            <el-badge v-if="hotProductCount" :value="hotProductCount" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AliExpressHotBroadcast
              :products="products"
              :broadcasts="broadcasts"
              :store-id="selectedStoreId"
              @update:broadcasts="onBroadcastsUpdate"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
  </PageScroll>
</template>

<style scoped>
.page-toolbar {
  margin-bottom: 16px;
}

.module-tabs {
  margin-top: 20px;
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
</style>
