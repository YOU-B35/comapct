<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { fetchHelperUpdateInfo, openHelperDownload } from '@/api/agentHelper'
import { fetchLocalInstallInfo } from '@/utils/agentProbe'
import { isHelperOutdated } from '@/utils/helperVersion'
import { fetchPddStores } from '@/api/platformAccounts'
import { scopeStores } from '@/utils/scope'
import { enrichDomesticIssue } from '@/utils/domesticPlatform'
import { pushPlatformOrderToWarehouse } from '@/api/platformShipRequests'
import {
  canUsePddBackend,
  enqueuePddProductsSync,
  enqueuePddOrdersSync,
  enqueuePddIssuesSync,
  enqueuePddPeerBestsellersSync,
  fetchPddProducts,
  fetchPddIssues,
  resolvePddIssueApi,
  pollPddSyncJob,
} from '@/api/pddApi'
import { PDD_ISSUE_TYPES } from '@/constants/pddDemo'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import HelperStatusBar from '@/components/helper/HelperStatusBar.vue'
import PddProductPanel from '@/components/pdd/PddProductPanel.vue'
import PddDashboardPanel from '@/components/pdd/PddDashboardPanel.vue'
import PddOrderDetailsPanel from '@/components/pdd/PddOrderDetailsPanel.vue'
import PddProductAnalyticsPanel from '@/components/pdd/PddProductAnalyticsPanel.vue'
import PddPeerBestsellersPanel from '@/components/pdd/PddPeerBestsellersPanel.vue'
import PddMonitorPanel from '@/components/pdd/PddMonitorPanel.vue'
import DomesticIssuesPanel from '@/components/domestic/DomesticIssuesPanel.vue'
import PlatformShipPushDialog from '@/components/domestic/PlatformShipPushDialog.vue'
import SyncHistoryDrawer from '@/components/common/SyncHistoryDrawer.vue'
import { fetchPlatformSyncLogs } from '@/api/syncLogApi'

const syncHistoryOpen = ref(false)

const auth = useAuthStore()
const router = useRouter()
const activeSection = ref('details')
const selectedStoreId = ref('all')
const storesPdd = ref([])
const products = ref([])
const loadingStores = ref(false)
const productsLoading = ref(false)
const productsSyncing = ref(false)
const ordersSyncing = ref(false)
const peerSyncing = ref(false)
const issuesSyncing = ref(false)
const dashboardRef = ref(null)
const orderDetailsRef = ref(null)
const bestsellersRef = ref(null)
const todayBestsellersRef = ref(null)
const recentSalesRef = ref(null)
const peerBestsellersRef = ref(null)
const issuesPanelRef = ref(null)

const issues = ref([])
const issuesSyncedAt = ref('')
const loadingIssues = ref(false)
const issuesFilter = ref('all')

const shipDialogVisible = ref(false)
const shipDialogOrder = ref(null)
const shipDialogType = ref('push')
const shipSubmitting = ref(false)

const backendReady = computed(() => canUsePddBackend(auth))
const showStoreColumn = computed(() => selectedStoreId.value === 'all')
const storeNameMap = computed(() => Object.fromEntries(
  storesPdd.value.map((store) => [store.id, store.storeName]),
))
const pendingIssueCount = computed(() => issues.value.filter((item) => !item.resolved).length)

async function loadStores() {
  loadingStores.value = true
  try {
    const response = await fetchPddStores()
    storesPdd.value = scopeStores(response?.data || [], auth)
    if (selectedStoreId.value !== 'all' && !storesPdd.value.some((store) => store.id === selectedStoreId.value)) {
      selectedStoreId.value = 'all'
    }
  } catch (error) {
    storesPdd.value = []
    ElMessage.error(error?.message || '加载拼多多店铺失败')
  } finally {
    loadingStores.value = false
  }
}

async function loadProducts() {
  if (!backendReady.value || !storesPdd.value.length) {
    products.value = []
    return
  }
  productsLoading.value = true
  try {
    const data = await fetchPddProducts({
      storeId: selectedStoreId.value === 'all' ? undefined : selectedStoreId.value,
    })
    products.value = Array.isArray(data?.items) ? data.items : []
  } catch (error) {
    products.value = []
    ElMessage.error(error?.message || '加载拼多多商品失败')
  } finally {
    productsLoading.value = false
  }
}

async function loadIssues() {
  if (!backendReady.value || !storesPdd.value.length) {
    issues.value = []
    issuesSyncedAt.value = ''
    return
  }
  loadingIssues.value = true
  try {
    const data = await fetchPddIssues({
      storeId: selectedStoreId.value === 'all' ? undefined : selectedStoreId.value,
    })
    const items = Array.isArray(data?.items) ? data.items : []
    issues.value = items.map((issue) => enrichDomesticIssue(issue, PDD_ISSUE_TYPES))
    issuesSyncedAt.value = data?.synced_at || ''
  } catch (error) {
    issues.value = []
    issuesSyncedAt.value = ''
    ElMessage.error(error?.message || '加载拼多多工单预警失败')
  } finally {
    loadingIssues.value = false
  }
}

async function syncProducts() {
  if (!(await ensureHelperUpdated())) return
  if (!backendReady.value || productsSyncing.value) return
  productsSyncing.value = true
  try {
    const queued = await enqueuePddProductsSync({
      storeId: selectedStoreId.value === 'all' ? null : selectedStoreId.value,
    })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      ElMessage.warning(queued?.message || '未获取到同步任务')
      return
    }
    ElMessage.success('已开始同步拼多多商品')
    await pollPddSyncJob(jobId)
    await loadProducts()
    ElMessage.success('拼多多商品同步完成')
  } catch (error) {
    ElMessage.error(error?.message || '拼多多商品同步失败')
  } finally {
    productsSyncing.value = false
  }
}

async function syncOrders() {
  if (!(await ensureHelperUpdated())) return
  if (!backendReady.value || ordersSyncing.value) return
  ordersSyncing.value = true
  try {
    const queued = await enqueuePddOrdersSync({
      storeId: selectedStoreId.value === 'all' ? null : selectedStoreId.value,
    })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      ElMessage.warning(queued?.message || '未获取到同步任务')
      return
    }
    ElMessage.success('已开始同步拼多多订单')
    await pollPddSyncJob(jobId)
    dashboardRef.value?.load?.()
    orderDetailsRef.value?.load?.()
    bestsellersRef.value?.load?.()
    todayBestsellersRef.value?.load?.()
    recentSalesRef.value?.load?.()
    ElMessage.success('拼多多订单同步完成')
  } catch (error) {
    ElMessage.error(error?.message || '拼多多订单同步失败')
  } finally {
    ordersSyncing.value = false
  }
}

async function syncPeerBestsellers() {
  if (!(await ensureHelperUpdated())) return
  if (!backendReady.value || peerSyncing.value) return
  peerSyncing.value = true
  try {
    const queued = await enqueuePddPeerBestsellersSync({
      storeId: selectedStoreId.value === 'all' ? null : selectedStoreId.value,
    })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      ElMessage.warning(queued?.message || '未获取到同步任务')
      return
    }
    ElMessage.success('已开始抓取拼多多同行爆款')
    await pollPddSyncJob(jobId, { timeoutMs: 540000 })
    peerBestsellersRef.value?.load?.()
    ElMessage.success('同行爆款抓取完成')
  } catch (error) {
    ElMessage.error(error?.message || '同行爆款抓取失败')
  } finally {
    peerSyncing.value = false
  }
}

async function syncIssues() {
  if (!(await ensureHelperUpdated())) return
  if (!backendReady.value || issuesSyncing.value) return
  issuesSyncing.value = true
  try {
    const queued = await enqueuePddIssuesSync({
      storeId: selectedStoreId.value === 'all' ? null : selectedStoreId.value,
    })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      ElMessage.warning(queued?.message || '未获取到同步任务')
      return
    }
    ElMessage.success('已开始同步拼多多工单预警')
    await pollPddSyncJob(jobId, { timeoutMs: 600000 })
    await loadIssues()
    ElMessage.success('拼多多工单预警同步完成')
  } catch (error) {
    ElMessage.error(error?.message || '拼多多工单预警同步失败')
  } finally {
    issuesSyncing.value = false
  }
}

async function handleResolveIssue(payload) {
  try {
    await resolvePddIssueApi(payload.id, payload)
    await loadIssues()
    ElMessage.success('已标记为已解决')
  } catch (error) {
    ElMessage.error(error?.message || '操作失败')
  } finally {
    issuesPanelRef.value?.finishResolve?.()
  }
}

/** 旧版 Helper 强制拦截：未更新则弹提示并中止同步。 */
async function ensureHelperUpdated() {
  try {
    const [latestRes, localRes] = await Promise.allSettled([
      fetchHelperUpdateInfo(),
      fetchLocalInstallInfo(1500),
    ])
    const latest = latestRes.status === 'fulfilled' ? latestRes.value?.version : ''
    const local = localRes.status === 'fulfilled' ? localRes.value?.version : ''
    if (isHelperOutdated(local, latest)) {
      try {
        await ElMessageBox.confirm(
          `当前助手版本 ${local || '未知'}，最新版本 ${latest || '—'}。请先下载最新安装包并覆盖安装，否则拼多多同步不可用。`,
          '本机助手需要更新',
          {
            confirmButtonText: '立即下载更新',
            cancelButtonText: '稍后',
            type: 'warning',
            distinguishCancelAndClose: true,
          },
        )
        openHelperDownload()
      } catch {
        // 用户取消/关闭
      }
      return false
    }
    return true
  } catch {
    return true // 无法获取版本信息时不拦截，避免影响既有功能
  }
}

function goToAccountBinding() {
  router.push('/settings/accounts')
}

function openShipDialog(order, type) {
  shipDialogOrder.value = order
  shipDialogType.value = type
  shipDialogVisible.value = true
}

async function submitShipPush({ warehouseId, type, remark }) {
  if (!shipDialogOrder.value) return
  shipSubmitting.value = true
  try {
    const res = await pushPlatformOrderToWarehouse(auth, {
      platformKey: 'pdd',
      order: shipDialogOrder.value,
      storeName: storeNameMap.value[shipDialogOrder.value.storeId] || '',
      warehouseId,
      type,
      remark,
    })
    ElMessage.success(res.message)
    shipDialogVisible.value = false
    orderDetailsRef.value?.load?.()
  } catch (err) {
    ElMessage.error(err?.message || '操作失败')
  } finally {
    shipSubmitting.value = false
  }
}

watch(selectedStoreId, () => {
  void loadProducts()
  void loadIssues()
})

onMounted(async () => {
  await loadStores()
  await Promise.all([loadProducts(), loadIssues()])
})

onActivated(() => {
  void loadStores().then(() => Promise.all([loadProducts(), loadIssues()]))
})
</script>

<template>
  <PageScroll>
    <PageHeader
      title="拼多多运营中心"
      description="百亿补贴与商城订单、活动预警经营数据"
    />

    <HelperStatusBar platform="pdd" :store-id="selectedStoreId" />

    <PageSection v-if="storesPdd.length" title="店铺" tone="toolbar">
      <div class="toolbar-row">
        <el-radio-group v-model="selectedStoreId" size="small">
          <el-radio-button value="all">全部店铺</el-radio-button>
          <el-radio-button v-for="store in storesPdd" :key="store.id" :value="store.id">
            {{ store.storeName }}
          </el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="ordersSyncing" @click="syncOrders">同步订单数据</el-button>
        <el-button size="small" @click="syncHistoryOpen = true">同步日志</el-button>
      </div>
    </PageSection>

    <PageSection v-if="!loadingStores && !storesPdd.length" flush>
      <el-empty description="暂无可见的拼多多店铺" :image-size="96">
        <el-text type="info" size="small">
          {{ auth.isBoss ? '请先在账户绑定中绑定拼多多店铺' : '请联系企业管理员分配负责店铺' }}
        </el-text>
        <el-button v-if="auth.isBoss" type="primary" style="margin-top:16px" @click="goToAccountBinding">
          前往账户绑定
        </el-button>
      </el-empty>
    </PageSection>

    <PageSection v-else-if="storesPdd.length" title="店铺经营驾驶舱">
      <PddDashboardPanel
        ref="dashboardRef"
        :backend-ready="backendReady"
        :stores="storesPdd"
        :selected-store-id="selectedStoreId"
        :syncing="ordersSyncing"
        @sync="syncOrders"
      />
    </PageSection>

    <PageSection v-if="!loadingStores && storesPdd.length" title="商品管理">
      <el-tabs v-model="activeSection" class="module-tabs">
        <el-tab-pane name="details" label="经营明细">
          <PddOrderDetailsPanel
            ref="orderDetailsRef"
            :backend-ready="backendReady"
            :stores="storesPdd"
            :selected-store-id="selectedStoreId"
            :syncing="ordersSyncing"
            @sync="syncOrders"
          />
        </el-tab-pane>
        <el-tab-pane name="issues">
          <template #label>
            <span>活动预警</span>
            <el-badge v-if="pendingIssueCount" :value="pendingIssueCount" class="tab-badge" />
          </template>
          <DomesticIssuesPanel
            ref="issuesPanelRef"
            :issues="issues"
            :synced-at="issuesSyncedAt"
            :loading="loadingIssues || issuesSyncing"
            :show-store-column="showStoreColumn"
            :store-name-map="storeNameMap"
            :initial-filter="issuesFilter"
            issues-title="活动预警"
            issues-description="拼团、价格与库存相关待跟进事项"
            @refresh="syncIssues"
            @resolve="handleResolveIssue"
          />
        </el-tab-pane>
        <el-tab-pane name="bestsellers" label="爆款商品">
          <PddProductAnalyticsPanel
            ref="bestsellersRef"
            type="bestsellers"
            :backend-ready="backendReady"
            :stores="storesPdd"
            :selected-store-id="selectedStoreId"
          />
        </el-tab-pane>
        <el-tab-pane name="today-bestsellers" label="今日爆款商品">
          <PddProductAnalyticsPanel
            ref="todayBestsellersRef"
            type="today_bestsellers"
            :backend-ready="backendReady"
            :stores="storesPdd"
            :selected-store-id="selectedStoreId"
          />
        </el-tab-pane>
        <el-tab-pane name="recent-sales" label="近期销量">
          <PddProductAnalyticsPanel
            ref="recentSalesRef"
            type="recent_sales"
            :backend-ready="backendReady"
            :stores="storesPdd"
            :selected-store-id="selectedStoreId"
          />
        </el-tab-pane>
        <el-tab-pane name="peer-bestsellers" label="爆款追踪">
          <PddPeerBestsellersPanel
            ref="peerBestsellersRef"
            :backend-ready="backendReady"
            :stores="storesPdd"
            :selected-store-id="selectedStoreId"
            :syncing="peerSyncing"
            @sync="syncPeerBestsellers"
          />
        </el-tab-pane>
        <el-tab-pane name="monitor" label="竞店监控">
          <PddMonitorPanel :backend-ready="backendReady" />
        </el-tab-pane>
        <el-tab-pane name="products" label="商品分类">
          <PddProductPanel
            :rows="products"
            :loading="productsLoading"
            :syncing="productsSyncing"
            :show-store-column="showStoreColumn"
            :store-name-map="storeNameMap"
            @sync="syncProducts"
            @refresh="loadProducts"
          />
        </el-tab-pane>
      </el-tabs>
    </PageSection>

    <PlatformShipPushDialog
      v-model="shipDialogVisible"
      :order="shipDialogOrder"
      platform-key="pdd"
      platform-label="拼多多"
      :store-name="shipDialogOrder ? storeNameMap[shipDialogOrder.storeId] : ''"
      :request-type="shipDialogType"
      :submitting="shipSubmitting"
      @submit="submitShipPush"
    />

    <SyncHistoryDrawer
      v-model="syncHistoryOpen"
      platform="pdd"
      :fetcher="() => fetchPlatformSyncLogs({ platform: 'pdd' })"
    />
  </PageScroll>
</template>

<style scoped>
.toolbar-row { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; }
.module-tabs { margin-top:4px; }
.tab-badge { margin-left:6px; vertical-align:middle; }
.tab-badge :deep(.el-badge__content) { position:relative; transform:none; vertical-align:middle; }
</style>
