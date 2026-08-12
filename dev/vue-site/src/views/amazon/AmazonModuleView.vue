<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { usePlatformSyncStore } from '@/stores/platformSync'
import { buildPlatformSyncTargets } from '@/api/platformSync'
import {
  loadAmazonDailyWorkflow,
  loadAmazonBossInsights,
  refreshAmazonBossInsights,
  refreshAmazonDailyWorkflow,
  refreshAmazonAccountHealth,
  refreshAmazonAllData,
  replyBuyerMessage,
  handleReview,
  acknowledgeCase,
  shipOutboundOrder,
} from '@/api/amazon'
import { fetchAmazonStores } from '@/api/platformAccounts'
import { scopeStores } from '@/utils/scope'
import { buildSyncSummaryText } from '@/utils/syncHistory'
import { fetchPlatformSyncStatus } from '@/api/temuApi'
import { fetchAmazonSyncJobs } from '@/api/agentApi'
import { useStoreAssignees } from '@/composables/useStoreAssignees'
import { buildAmazonDailyChecklist } from '@/utils/amazon'
import { summarizeTopProducts, summarizeOutboundOrders, isValidAmazonProduct } from '@/utils/amazonBoss'
import { resolveAmazonProductEmptyHint } from '@/utils/amazonProductHint'
import { isPlatformOperationalDemoOnly, platformOperationalHint } from '@/utils/platformOperationalMode'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import SyncSummaryLine from '@/components/common/SyncSummaryLine.vue'
import SyncHistoryDrawer from '@/components/common/SyncHistoryDrawer.vue'
import AmazonDailyOverview from '@/components/amazon/AmazonDailyOverview.vue'
import AmazonBossOverview from '@/components/amazon/AmazonBossOverview.vue'
import AmazonProductsPanel from '@/components/amazon/AmazonProductsPanel.vue'
import AmazonOutboundPanel from '@/components/amazon/AmazonOutboundPanel.vue'
import AmazonBuyerMessagesPanel from '@/components/amazon/AmazonBuyerMessagesPanel.vue'
import AmazonAccountHealthPanel from '@/components/amazon/AmazonAccountHealthPanel.vue'
import AmazonReviewsPanel from '@/components/amazon/AmazonReviewsPanel.vue'
import AmazonCouponsPanel from '@/components/amazon/AmazonCouponsPanel.vue'
import AmazonSellerNewsPanel from '@/components/amazon/AmazonSellerNewsPanel.vue'
import AmazonShipmentsPanel from '@/components/amazon/AmazonShipmentsPanel.vue'
import AmazonCasesPanel from '@/components/amazon/AmazonCasesPanel.vue'
import AmazonIntegrationGuide from '@/components/amazon/AmazonIntegrationGuide.vue'
import HelperStatusBar from '@/components/helper/HelperStatusBar.vue'
import { canUsePlatformUserHelper } from '@/utils/opsSyncPolicy'

const auth = useAuthStore()
const syncStore = usePlatformSyncStore()
const { assigneeMap, loadAssignees, enrichItems } = useStoreAssignees()
const router = useRouter()

const activeTab = ref(auth.isBoss ? 'products' : 'dashboard')
const selectedStoreId = ref('all')
const amazonStores = ref([])
const workflow = ref(emptyWorkflow())
const bossProducts = ref([])
const outboundOrders = ref([])
const syncedAt = ref('')
const bossSyncedAt = ref('')
const loadingStores = ref(false)
const loading = ref(false)
const loadingBoss = ref(false)
const loadingReports = ref(false)
const loadingAll = ref(false)
const productDataQuality = ref(null)
const productSyncIssue = ref(null)

const messagesPanel = ref(null)
const reviewsPanel = ref(null)
const productsPanel = ref(null)
const outboundPanel = ref(null)
const casesPanel = ref(null)
const productsFilter = ref('all')
const outboundFilter = ref('pending')

const operationalDemoOnly = computed(() => isPlatformOperationalDemoOnly('amazon'))
const operationalHint = computed(() => platformOperationalHint('amazon'))
const showManualSyncControls = computed(() => canUsePlatformUserHelper(auth))
const showIntegrationGuide = computed(
  () => false,
)
const helperOnline = ref(false)
const syncHistoryOpen = ref(false)
const lastSyncJob = ref(null)
const syncSummaryText = computed(() => buildSyncSummaryText(lastSyncJob.value, 'amazon'))

function onHelperOnline(online) {
  helperOnline.value = Boolean(online)
}

const storeNameMap = computed(() =>
  Object.fromEntries(amazonStores.value.map((s) => [s.id, s.storeName])),
)

const showStoreColumn = computed(() => selectedStoreId.value === 'all')
const showStoreList = computed(
  () => selectedStoreId.value === 'all' && amazonStores.value.length > 0,
)

const overviewStores = computed(() => {
  if (selectedStoreId.value === 'all') return amazonStores.value
  return amazonStores.value.filter((s) => s.id === selectedStoreId.value)
})

function emptyWorkflow() {
  return {
    buyerMessages: [],
    accountMetrics: [],
    reviews: [],
    coupons: [],
    sellerNews: [],
    shipments: [],
    cases: [],
  }
}

function filterByStore(items) {
  if (selectedStoreId.value === 'all') return enrichItems(items)
  return enrichItems(items.filter((i) => i.storeId === selectedStoreId.value))
}

const filteredProducts = computed(() => filterByStore(bossProducts.value))
const filteredOutbound = computed(() => filterByStore(outboundOrders.value))

const bossProductSummary = computed(() => summarizeTopProducts(filteredProducts.value, 20))
const outboundSummary = computed(() => summarizeOutboundOrders(filteredOutbound.value))

const filtered = computed(() => {
  let cases = filterByStore(workflow.value.cases)
  if (!cases.length) {
    cases = filterByStore(workflow.value.sellerNews)
      .filter((item) => /业绩通知|performance notification/i.test(String(item.title || '')))
      .map((item) => ({
        id: item.id,
        storeId: item.storeId,
        caseId: item.id,
        title: item.title,
        status: item.status === 'read' ? 'read' : 'pending',
        openedAt: item.publishedAt || '',
        note: item.summary || item.title || '',
      }))
  }
  return {
    buyerMessages: filterByStore(workflow.value.buyerMessages),
    accountMetrics: filterByStore(workflow.value.accountMetrics),
    reviews: filterByStore(workflow.value.reviews),
    coupons: filterByStore(workflow.value.coupons),
    sellerNews: filterByStore(workflow.value.sellerNews),
    shipments: filterByStore(workflow.value.shipments),
    cases,
  }
})

const checklist = computed(() => buildAmazonDailyChecklist(filtered.value))

const tabBadges = computed(() => {
  const map = Object.fromEntries(checklist.value.map((s) => [s.tab, s.count]))
  return {
    products: bossProductSummary.value.highAcosCount,
    outbound: outboundSummary.value.actionRequired,
    dashboard: 0,
    messages: map.messages || 0,
    account: map.account || 0,
    reviews: map.reviews || 0,
    coupons: map.coupons || 0,
    news: map.news || 0,
    shipments: map.shipments || 0,
    cases: map.cases || 0,
  }
})

function applyWorkflowData(data) {
  workflow.value = {
    buyerMessages: data.buyerMessages || [],
    accountMetrics: data.accountMetrics || [],
    reviews: data.reviews || [],
    coupons: data.coupons || [],
    sellerNews: data.sellerNews || [],
    shipments: data.shipments || [],
    cases: data.cases || [],
  }
  syncedAt.value = data.syncedAt || ''
  markAmazonSidebarSync()
}

function applyBossData(data) {
  bossProducts.value = data.products || []
  outboundOrders.value = data.outboundOrders || []
  bossSyncedAt.value = data.syncedAt || ''
  productDataQuality.value = data.dataQuality || null
  if (bossProducts.value.length) {
    const validCount = bossProducts.value.filter(isValidAmazonProduct).length
    if (validCount > 0) {
      productSyncIssue.value = null
      markAmazonSidebarSync()
      return
    }
    productSyncIssue.value = resolveAmazonProductEmptyHint({
      errorCode: 'AMAZON_NO_VALID_PRODUCT_ROWS',
      syncedAt: bossSyncedAt.value,
      rawProductCount: bossProducts.value.length,
    })
  }
}

function notifySyncResult(res, fallbackMessage) {
  if (res?.partial) {
    productSyncIssue.value = resolveAmazonProductEmptyHint({
      errorCode: res.errorCode,
      errorMessage: res.warning || res.errorMessage,
      syncedAt: bossSyncedAt.value || syncedAt.value,
    })
    ElMessage.warning(res.warning || res.message || fallbackMessage)
    return
  }
  ElMessage.success(res?.message || fallbackMessage)
}

function notifySyncError(err) {
  productSyncIssue.value = resolveAmazonProductEmptyHint({
    errorCode: err?.code || err?.errorCode,
    errorMessage: err?.message,
    syncedAt: bossSyncedAt.value || syncedAt.value,
  })
  ElMessage.error(err?.message || '同步失败')
}

async function ensurePlatformSyncSeeded() {
  if (!auth.backendLinked || syncStore.hasItems) return
  try {
    const targets = await buildPlatformSyncTargets(auth)
    if (targets.length) syncStore.updateItems(targets)
  } catch {
    // best effort
  }
}


async function hydrateAmazonLastSync() {
  try {
    const status = await fetchPlatformSyncStatus()
    let job = status?.platforms?.amazon?.last_job || null
    if (!job) {
      const jobs = await fetchAmazonSyncJobs({ limit: 1 })
      job = Array.isArray(jobs) && jobs.length ? jobs[0] : null
    }
    if (job) lastSyncJob.value = job
  } catch (_) { /* ignore */ }
}

function markAmazonSidebarSync({ status = 'success', message = '' } = {}) {
  if (operationalDemoOnly.value || !amazonStores.value.length) return
  const productCount = bossProducts.value.filter(isValidAmazonProduct).length
  const workflowCount =
    (workflow.value.accountMetrics?.length || 0)
    + (workflow.value.reviews?.length || 0)
    + (workflow.value.coupons?.length || 0)
    + (workflow.value.shipments?.length || 0)
    + (workflow.value.cases?.length || 0)
  const rowCount = productCount + outboundOrders.value.length + workflowCount
  const resolvedStatus = rowCount > 0 ? status : 'empty'
  const resolvedMessage =
    message
    || (productCount > 0
      ? `已同步 ${productCount} SKU · ${outboundOrders.value.length} 订单`
      : workflowCount > 0
        ? `已同步 ${workflowCount} 条运营待办`
        : '暂无 Amazon 同步数据')

  for (const store of amazonStores.value) {
    syncStore.updateStoreStatus({
      platform: 'amazon',
      storeId: store.id,
      storeName: store.storeName,
      externalShopId: store.externalShopId || '',
      status: resolvedStatus,
      message: resolvedMessage,
      rowCount,
      syncedAt: bossSyncedAt.value || syncedAt.value,
    })
  }
}

async function syncBossInsights(refresh = false) {
  if (refresh && !showManualSyncControls.value) return
  if (operationalDemoOnly.value || !amazonStores.value.length) {
    applyBossData({ products: [], outboundOrders: [], syncedAt: '' })
    return
  }
  loadingBoss.value = true
  try {
    const res = refresh
      ? await refreshAmazonBossInsights(amazonStores.value, { refresh: true, scope: 'reports' })
      : await loadAmazonBossInsights(amazonStores.value)
    applyBossData(res.data)
    if (refresh) {
      await hydrateAmazonLastSync()
      notifySyncResult(res, '已刷新产品数据')
    }
  } catch (err) {
    notifySyncError(err)
  } finally {
    loadingBoss.value = false
  }
}

async function syncBossReports(refresh = false) {
  if (operationalDemoOnly.value || !amazonStores.value.length) {
    return
  }
  loadingReports.value = true
  try {
    const res = refresh
      ? await refreshAmazonBossInsights(amazonStores.value, { refresh: true, scope: 'reports' })
      : await loadAmazonBossInsights(amazonStores.value)
    applyBossData(res.data)
    if (refresh) {
      await hydrateAmazonLastSync()
      notifySyncResult(res, '已刷新 Business Report 产品数据')
    }
  } catch (err) {
    notifySyncError(err)
  } finally {
    loadingReports.value = false
  }
}

async function syncWorkflow(refresh = false) {
  if (operationalDemoOnly.value || !amazonStores.value.length) {
    applyWorkflowData(emptyWorkflow())
    return
  }
  loading.value = true
  try {
    const res = refresh
      ? await refreshAmazonDailyWorkflow(amazonStores.value, { refresh: true })
      : await loadAmazonDailyWorkflow(amazonStores.value)
    applyWorkflowData(res.data)
    if (refresh) {
      await hydrateAmazonLastSync()
      notifySyncResult(res, '已刷新今日运营数据')
    }
  } catch (err) {
    notifySyncError(err)
  } finally {
    loading.value = false
  }
}

async function syncAccountHealth(refresh = false) {
  if (operationalDemoOnly.value || !amazonStores.value.length) {
    return
  }
  loading.value = true
  try {
    const res = refresh
      ? await refreshAmazonAccountHealth(amazonStores.value, { refresh: true })
      : await loadAmazonDailyWorkflow(amazonStores.value)
    applyWorkflowData({ ...workflow.value, accountMetrics: res.data.accountMetrics || [], syncedAt: res.data.syncedAt })
    if (refresh) {
      await hydrateAmazonLastSync()
      ElMessage.success(res.message || '已刷新账户状况')
    }
  } catch (err) {
    ElMessage.error(err.message || '账户状况加载失败')
  } finally {
    loading.value = false
  }
}

async function syncAllAmazon() {
  if (!showManualSyncControls.value) return
  if (operationalDemoOnly.value || !amazonStores.value.length) return
  loadingAll.value = true
  loadingBoss.value = true
  loading.value = true
  try {
    const res = await refreshAmazonAllData(amazonStores.value)
    if (res.dailyData) applyWorkflowData(res.dailyData)
    else if (res.data?.daily) applyWorkflowData(res.data.daily)
    if (res.insightsData) applyBossData(res.insightsData)
    else if (res.data?.insights) applyBossData(res.data.insights)
    if (!res.dailyData && !res.data?.daily) {
      const [dailyRes, insightsRes] = await Promise.all([
        loadAmazonDailyWorkflow(amazonStores.value),
        loadAmazonBossInsights(amazonStores.value),
      ])
      applyWorkflowData(dailyRes.data)
      applyBossData(insightsRes.data)
    }
    await hydrateAmazonLastSync()
    notifySyncResult(res, '已刷新 Amazon 全部数据（运营 + 产品 + 广告）')
  } catch (err) {
    notifySyncError(err)
  } finally {
    loadingAll.value = false
    loadingBoss.value = false
    loading.value = false
  }
}

async function loadModule() {
  loadingStores.value = true
  try {
    const res = await fetchAmazonStores()
    amazonStores.value = scopeStores(res.data || [], auth)
    await ensurePlatformSyncSeeded()
    if (amazonStores.value.length && !operationalDemoOnly.value) {
      await Promise.all([syncWorkflow(), syncBossInsights(false)])
      if (!bossProducts.value.length) {
        productSyncIssue.value = resolveAmazonProductEmptyHint({
          syncedAt: bossSyncedAt.value,
        })
      } else if (!bossProducts.value.filter(isValidAmazonProduct).length) {
        productSyncIssue.value = resolveAmazonProductEmptyHint({
          errorCode: 'AMAZON_NO_VALID_PRODUCT_ROWS',
          syncedAt: bossSyncedAt.value,
          rawProductCount: bossProducts.value.length,
        })
      }
    } else if (!amazonStores.value.length) {
      applyWorkflowData(emptyWorkflow())
      applyBossData({ products: [], outboundOrders: [], syncedAt: '' })
    }
  } catch {
    amazonStores.value = []
    applyWorkflowData(emptyWorkflow())
  } finally {
    loadingStores.value = false
  }
}

function goToAccountBinding() {
  router.push(auth.isBoss ? '/boss/accounts' : '/employee/dashboard')
}

function handleNavigate(target) {
  if (target.startsWith('products')) {
    activeTab.value = 'products'
    productsFilter.value = target === 'products:high-acos' ? 'high-acos' : 'all'
    return
  }
  if (target.startsWith('outbound')) {
    activeTab.value = 'outbound'
    outboundFilter.value = target === 'outbound:packed' ? 'packed' : 'pending'
    return
  }
  activeTab.value = target
}

async function onShipOutbound(payload) {
  try {
    const res = await shipOutboundOrder(payload.id, payload)
    const idx = outboundOrders.value.findIndex((o) => o.id === payload.id)
    if (idx !== -1) outboundOrders.value[idx] = res.data
    ElMessage.success('已标记发货')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    outboundPanel.value?.finishShip?.()
  }
}

async function onReplyMessage(payload) {
  try {
    const res = await replyBuyerMessage(payload.id, payload)
    const idx = workflow.value.buyerMessages.findIndex((m) => m.id === payload.id)
    if (idx !== -1) workflow.value.buyerMessages[idx] = res.data
    ElMessage.success('已回复买家消息')
  } catch (err) {
    ElMessage.error(err.message || '回复失败')
  } finally {
    messagesPanel.value?.finishReply?.()
  }
}

async function onHandleReview(payload) {
  try {
    const res = await handleReview(payload.id, payload)
    const idx = workflow.value.reviews.findIndex((r) => r.id === payload.id)
    if (idx !== -1) workflow.value.reviews[idx] = res.data
    ElMessage.success('已标记差评处理')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    reviewsPanel.value?.finishHandle?.()
  }
}

async function onAcknowledgeCase(id) {
  try {
    const res = await acknowledgeCase(id)
    const idx = workflow.value.cases.findIndex((c) => c.id === id)
    if (idx !== -1) workflow.value.cases[idx] = res.data
    ElMessage.success('已标记 Case 已读')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    casesPanel.value?.finishAcknowledge?.()
  }
}

watch(amazonStores, (stores) => {
  if (selectedStoreId.value === 'all') return
  if (!stores.some((s) => s.id === selectedStoreId.value)) {
    selectedStoreId.value = 'all'
  }
})

onMounted(async () => {
  await loadAssignees()
  await loadModule()
  await hydrateAmazonLastSync()
})
onActivated(loadModule)
</script>

<template>
  <PageScroll>
    <template #header>
      <div v-if="amazonStores.length" class="page-toolbar">
        <el-radio-group v-model="selectedStoreId" size="small">
          <el-radio-button value="all">全部店铺</el-radio-button>
          <el-radio-button v-for="store in amazonStores" :key="store.id" :value="store.id">
            {{ store.storeName }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <PageHeader
        v-else-if="!amazonStores.length && !auth.isBoss"
        title="Amazon 运营"
        :description="`${auth.employee.name} · 一日运营工作流`"
      />
    </template>

    <SyncHistoryDrawer
      v-model="syncHistoryOpen"
      platform="amazon"
      :fetcher="() => fetchAmazonSyncJobs({ limit: 20 })"
    />

    <HelperStatusBar
      v-if="showManualSyncControls"
      platform="amazon"
      @update:online="onHelperOnline"
    />

    <el-empty
      v-if="!loadingStores && !amazonStores.length"
      description="暂无可见的 Amazon 店铺"
      :image-size="96"
    >
      <el-text type="info" size="small">
        {{
          auth.isBoss
            ? '请先在「账户绑定」中绑定 Amazon 店铺；本机可先下载并绑定 Sync Helper'
            : '请联系企业管理员分配负责店铺；本机可先下载并绑定 Sync Helper'
        }}
      </el-text>
      <el-button v-if="auth.isBoss" type="primary" style="margin-top: 16px" @click="goToAccountBinding">
        前往账户绑定
      </el-button>
    </el-empty>

    <template v-else-if="amazonStores.length">
      <AmazonIntegrationGuide v-if="showIntegrationGuide" />

      <div v-if="showManualSyncControls" class="amazon-sync-bar">
        <el-button
          type="primary"
          :loading="loadingAll"
          :disabled="!helperOnline"
          @click="syncAllAmazon"
        >
          一键刷新全部数据
        </el-button>
        <SyncSummaryLine
          :summary-text="syncSummaryText"
          @open-history="syncHistoryOpen = true"
        />
        <el-text size="small" type="info">
          依次同步今日运营、Business Report 产品与广告（约 3–8 分钟，需本机 Sync Helper 与紫鸟在线）
        </el-text>
      </div>

      <el-alert
        v-if="operationalDemoOnly && operationalHint"
        :title="operationalHint"
        type="info"
        show-icon
        :closable="false"
        class="operational-hint"
      />

      <AmazonBossOverview
        v-if="auth.isBoss"
        :products="filteredProducts"
        :outbound-orders="filteredOutbound"
        :account-metrics="filtered.accountMetrics"
        :stores="overviewStores"
        :assignee-map="assigneeMap"
        :show-store-list="showStoreList"
        @navigate="handleNavigate"
      />

      <el-tabs v-model="activeTab" class="module-tabs">
        <el-tab-pane v-if="auth.isBoss" name="products">
          <template #label>
            <span>产品 TOP20</span>
            <el-badge v-if="tabBadges.products" :value="tabBadges.products" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonProductsPanel
              ref="productsPanel"
              :products="filteredProducts"
              :synced-at="bossSyncedAt"
              :summary-text="syncSummaryText"
              :sync-issue="productSyncIssue"
              :data-quality="productDataQuality"
              :loading="loadingBoss"
              :reports-loading="loadingReports"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              :initial-filter="productsFilter"
              @refresh="syncBossInsights(true)"
              @refresh-reports="syncBossReports(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="outbound">
          <template #label>
            <span>订单发货</span>
            <el-badge v-if="tabBadges.outbound" :value="tabBadges.outbound" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonOutboundPanel
              ref="outboundPanel"
              :orders="filteredOutbound"
              :synced-at="bossSyncedAt"
              :summary-text="syncSummaryText"
              :loading="loadingBoss"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              :initial-filter="outboundFilter"
              @refresh="syncBossInsights(true)"
              @ship="onShipOutbound"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="dashboard">
          <template #label>
            <span>今日工作台</span>
          </template>
          <div class="tab-panel">
            <AmazonDailyOverview
              :workflow="filtered"
              :stores="overviewStores"
              :assignee-map="assigneeMap"
              :show-store-list="showStoreList"
              @navigate="handleNavigate"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="messages">
          <template #label>
            <span>买家消息</span>
            <el-badge v-if="tabBadges.messages" :value="tabBadges.messages" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonBuyerMessagesPanel
              ref="messagesPanel"
              :messages="filtered.buyerMessages"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @reply="onReplyMessage"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="account">
          <template #label>
            <span>账户状况</span>
            <el-badge v-if="tabBadges.account" :value="tabBadges.account" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonAccountHealthPanel
              :metrics="filtered.accountMetrics"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncAccountHealth(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="reviews">
          <template #label>
            <span>差评预警</span>
            <el-badge v-if="tabBadges.reviews" :value="tabBadges.reviews" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonReviewsPanel
              ref="reviewsPanel"
              :reviews="filtered.reviews"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @handle="onHandleReview"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="coupons">
          <template #label>
            <span>优惠券</span>
            <el-badge v-if="tabBadges.coupons" :value="tabBadges.coupons" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonCouponsPanel
              :coupons="filtered.coupons"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncWorkflow(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="news">
          <template #label>
            <span>卖家新闻</span>
            <el-badge v-if="tabBadges.news" :value="tabBadges.news" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonSellerNewsPanel
              :news="filtered.sellerNews"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="shipments">
          <template #label>
            <span>货件到货</span>
            <el-badge v-if="tabBadges.shipments" :value="tabBadges.shipments" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonShipmentsPanel
              :shipments="filtered.shipments"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncWorkflow(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="cases">
          <template #label>
            <span>Case 回复</span>
            <el-badge v-if="tabBadges.cases" :value="tabBadges.cases" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonCasesPanel
              ref="casesPanel"
              :cases="filtered.cases"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @acknowledge="onAcknowledgeCase"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
  </PageScroll>
</template>

<style scoped>
.page-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.amazon-sync-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.module-tabs :deep(.el-tabs__header) {
  margin-bottom: 4px;
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
