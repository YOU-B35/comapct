<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { fetchHelperUpdateInfo, openHelperDownload } from '@/api/agentHelper'
import { fetchLocalInstallInfo } from '@/utils/agentProbe'
import { isHelperOutdated } from '@/utils/helperVersion'
import { fetchAlibaba1688Stores } from '@/api/platformAccounts'
import { scopeStores } from '@/utils/scope'
import {
  canUseAlibaba1688Backend,
  enqueueAlibaba1688ProductsSync,
  enqueueAlibaba1688OrdersSync,
  enqueueAlibaba1688PeerBestsellersSync,
  fetchAlibaba1688Products,
  fetchAlibaba1688Session,
} from '@/api/alibaba1688Api'
import { PRODUCT_TABS } from '@/constants/alibaba1688Products'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import HelperStatusBar from '@/components/helper/HelperStatusBar.vue'
import Alibaba1688ProductPanel from '@/components/alibaba1688/Alibaba1688ProductPanel.vue'
import Alibaba1688DashboardPanel from '@/components/alibaba1688/Alibaba1688DashboardPanel.vue'
import Alibaba1688OrderDetailsPanel from '@/components/alibaba1688/Alibaba1688OrderDetailsPanel.vue'
import Alibaba1688ProductAnalyticsPanel from '@/components/alibaba1688/Alibaba1688ProductAnalyticsPanel.vue'
import Alibaba1688PeerBestsellersPanel from '@/components/alibaba1688/Alibaba1688PeerBestsellersPanel.vue'
import Alibaba1688MonitorPanel from '@/components/alibaba1688/Alibaba1688MonitorPanel.vue'
import SyncHistoryDrawer from '@/components/common/SyncHistoryDrawer.vue'
import { fetchPlatformSyncLogs } from '@/api/syncLogApi'

const syncHistoryOpen = ref(false)

const auth = useAuthStore()
const router = useRouter()
const activeTab = ref('products-all')
const activeSection = ref('details')
const selectedStoreId = ref('all')
const stores1688 = ref([])
const products = ref([])
const categoryCounts = ref({})
const categorySync = ref({})
const loadingStores = ref(false)
const productsLoading = ref(false)
const productsSyncing = ref(false)
const ordersSyncing = ref(false)
const peerSyncing = ref(false)
const dashboardRef = ref(null)
const orderDetailsRef = ref(null)
const bestsellersRef = ref(null)
const todayBestsellersRef = ref(null)
const recentSalesRef = ref(null)
const peerBestsellersRef = ref(null)

const backendReady = computed(() => canUseAlibaba1688Backend(auth))
const activeMeta = computed(() => PRODUCT_TABS.find((item) => item.name === activeTab.value) || PRODUCT_TABS[0])
const showStoreColumn = computed(() => selectedStoreId.value === 'all')
const storeNameMap = computed(() => Object.fromEntries(
  stores1688.value.map((store) => [store.id, store.storeName]),
))

function tabLabel(tab) {
  if (!tab.categoryCode) return tab.label
  const count = Number(categoryCounts.value?.[tab.categoryCode])
  return Number.isFinite(count) ? tab.label + ' (' + count + ')' : tab.label
}

async function loadStores() {
  loadingStores.value = true
  try {
    const response = await fetchAlibaba1688Stores()
    stores1688.value = scopeStores(response?.data || [], auth)
    if (selectedStoreId.value !== 'all' && !stores1688.value.some((store) => store.id === selectedStoreId.value)) {
      selectedStoreId.value = 'all'
    }
  } catch (error) {
    stores1688.value = []
    ElMessage.error(error?.message || '加载 1688 店铺失败')
  } finally {
    loadingStores.value = false
  }
}

async function loadProducts() {
  if (!backendReady.value || !stores1688.value.length) {
    products.value = []
    return
  }
  productsLoading.value = true
  try {
    const data = await fetchAlibaba1688Products({
      tab: activeMeta.value.tab,
      status: 'all',
      storeId: selectedStoreId.value === 'all' ? undefined : selectedStoreId.value,
    })
    products.value = Array.isArray(data?.items) ? data.items : []
    categoryCounts.value = data?.categoryCounts && typeof data.categoryCounts === 'object'
      ? data.categoryCounts
      : {}
    categorySync.value = data?.categorySync && typeof data.categorySync === 'object'
      ? data.categorySync
      : {}
  } catch (error) {
    products.value = []
    ElMessage.error(error?.message || '加载 1688 商品失败')
  } finally {
    productsLoading.value = false
  }
}

async function syncProducts() {
  if (!(await ensureHelperUpdated())) return
  if (!backendReady.value || productsSyncing.value) return
  productsSyncing.value = true
  try {
    const queued = await enqueueAlibaba1688ProductsSync()
    if (queued?.already_open || queued?.queued === false) {
      ElMessage.warning(queued?.message || '已有 1688 同步任务进行中')
      return
    }
    ElMessage.success('已开始同步 1688 商品和分类')
    const deadline = Date.now() + 180000
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 3000))
      const session = await fetchAlibaba1688Session()
      if (!session?.profile_busy) {
        await loadProducts()
        if (session?.error_code || session?.errorCode) {
          ElMessage.warning(session?.message || '商品已同步，部分分类保留上次成功结果')
        } else {
          ElMessage.success('1688 商品和分类同步完成')
        }
        return
      }
    }
    await loadProducts()
    ElMessage.warning('同步仍在后台进行，可稍后刷新查看')
  } catch (error) {
    ElMessage.error(error?.message || '1688 商品同步失败')
  } finally {
    productsSyncing.value = false
  }
}

async function syncOrders() {
  if (!(await ensureHelperUpdated())) return
  if (!backendReady.value || ordersSyncing.value) return
  ordersSyncing.value = true
  try {
    const queued = await enqueueAlibaba1688OrdersSync({ storeId: selectedStoreId.value })
    if (queued?.queued === false) {
      ElMessage.warning(queued?.message || '已有 1688 浏览器任务进行中')
      return
    }
    ElMessage.success('已开始同步 1688 订单')
    const deadline = Date.now() + 240000
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 3000))
      const session = await fetchAlibaba1688Session()
      if (!session?.profile_busy) {
        dashboardRef.value?.load?.()
        orderDetailsRef.value?.load?.()
        bestsellersRef.value?.load?.()
        todayBestsellersRef.value?.load?.()
        recentSalesRef.value?.load?.()
        if (session?.error_code || session?.errorCode) {
          ElMessage.warning(session?.message || '订单已同步，部分数据可能不完整')
        } else {
          ElMessage.success('1688 订单同步完成')
        }
        return
      }
    }
    dashboardRef.value?.load?.()
    orderDetailsRef.value?.load?.()
    bestsellersRef.value?.load?.()
    todayBestsellersRef.value?.load?.()
    recentSalesRef.value?.load?.()
    ElMessage.warning('订单同步仍在后台进行，可稍后刷新查看')
  } catch (error) {
    ElMessage.error(error?.message || '1688 订单同步失败')
  } finally {
    ordersSyncing.value = false
  }
}

async function syncPeerBestsellers() {
  if (!(await ensureHelperUpdated())) return
  if (!backendReady.value || peerSyncing.value) return
  peerSyncing.value = true
  try {
    const queued = await enqueueAlibaba1688PeerBestsellersSync({ storeId: selectedStoreId.value })
    if (queued?.queued === false) {
      ElMessage.warning(queued?.message || '已有 1688 浏览器任务进行中')
      return
    }
    ElMessage.success('已开始抓取 1688 同行爆款')
    const deadline = Date.now() + 540000
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 3000))
      const session = await fetchAlibaba1688Session()
      if (!session?.profile_busy) {
        peerBestsellersRef.value?.load?.()
        if (session?.error_code || session?.errorCode) {
          ElMessage.warning(session?.message || '同行爆款抓取可能不完整')
        } else {
          ElMessage.success('同行爆款抓取完成')
        }
        return
      }
    }
    peerBestsellersRef.value?.load?.()
    ElMessage.warning('同行爆款抓取仍在后台进行，可稍后刷新查看')
  } catch (error) {
    ElMessage.error(error?.message || '同行爆款抓取失败')
  } finally {
    peerSyncing.value = false
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
          `当前助手版本 ${local || '未知'}，最新版本 ${latest || '—'}。请先下载最新安装包并覆盖安装，否则 1688 同步不可用。`,
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

watch([activeTab, selectedStoreId], () => { void loadProducts() })

onMounted(async () => {
  await loadStores()
  await loadProducts()
})

onActivated(() => {
  void loadStores().then(loadProducts)
})
</script>

<template>
  <PageScroll>
    <PageHeader
      title="1688 经营中心"
      description="面向个人消费者的店铺销售与商品经营数据"
    />

    <HelperStatusBar platform="1688" :store-id="selectedStoreId" />

    <PageSection v-if="stores1688.length" title="店铺" tone="toolbar">
      <div class="toolbar-row">
        <el-radio-group v-model="selectedStoreId" size="small">
          <el-radio-button value="all">全部店铺</el-radio-button>
          <el-radio-button v-for="store in stores1688" :key="store.id" :value="store.id">
            {{ store.storeName }}
          </el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="ordersSyncing" @click="syncOrders">同步订单数据</el-button>
        <el-button size="small" @click="syncHistoryOpen = true">同步日志</el-button>
      </div>
    </PageSection>

    <PageSection v-if="!loadingStores && !stores1688.length" flush>
      <el-empty description="暂无可见的 1688 店铺" :image-size="96">
        <el-text type="info" size="small">
          {{ auth.isBoss ? '请先在账户绑定中绑定 1688 店铺' : '请联系企业管理员分配负责店铺' }}
        </el-text>
        <el-button v-if="auth.isBoss" type="primary" style="margin-top:16px" @click="goToAccountBinding">
          前往账户绑定
        </el-button>
      </el-empty>
    </PageSection>

    <PageSection v-else-if="stores1688.length" title="店铺经营驾驶舱">
      <Alibaba1688DashboardPanel
        ref="dashboardRef"
        :backend-ready="backendReady"
        :stores="stores1688"
        :selected-store-id="selectedStoreId"
        :syncing="ordersSyncing"
        @sync="syncOrders"
      />
    </PageSection>

    <PageSection v-if="!loadingStores && stores1688.length" title="商品管理">
      <el-tabs v-model="activeSection" class="module-tabs">
        <el-tab-pane name="details" label="经营明细">
          <Alibaba1688OrderDetailsPanel
            ref="orderDetailsRef"
            :backend-ready="backendReady"
            :stores="stores1688"
            :selected-store-id="selectedStoreId"
            :syncing="ordersSyncing"
            @sync="syncOrders"
          />
        </el-tab-pane>
        <el-tab-pane name="bestsellers" label="爆款商品">
          <Alibaba1688ProductAnalyticsPanel
            ref="bestsellersRef"
            type="bestsellers"
            :backend-ready="backendReady"
            :stores="stores1688"
            :selected-store-id="selectedStoreId"
          />
        </el-tab-pane>
        <el-tab-pane name="today-bestsellers" label="今日爆款商品">
          <Alibaba1688ProductAnalyticsPanel
            ref="todayBestsellersRef"
            type="today_bestsellers"
            :backend-ready="backendReady"
            :stores="stores1688"
            :selected-store-id="selectedStoreId"
          />
        </el-tab-pane>
        <el-tab-pane name="recent-sales" label="近期销量">
          <Alibaba1688ProductAnalyticsPanel
            ref="recentSalesRef"
            type="recent_sales"
            :backend-ready="backendReady"
            :stores="stores1688"
            :selected-store-id="selectedStoreId"
          />
        </el-tab-pane>
        <el-tab-pane name="peer-bestsellers" label="爆款追踪">
          <Alibaba1688PeerBestsellersPanel
            ref="peerBestsellersRef"
            :backend-ready="backendReady"
            :stores="stores1688"
            :selected-store-id="selectedStoreId"
            :syncing="peerSyncing"
            @sync="syncPeerBestsellers"
          />
        </el-tab-pane>
        <el-tab-pane name="monitor" label="竞店监控">
          <Alibaba1688MonitorPanel :backend-ready="backendReady" />
        </el-tab-pane>
        <el-tab-pane name="products" label="商品分类">
          <el-tabs v-model="activeTab" class="module-tabs">
            <el-tab-pane
              v-for="tab in PRODUCT_TABS"
              :key="tab.name"
              :name="tab.name"
              :label="tabLabel(tab)"
            >
              <Alibaba1688ProductPanel
                :rows="products"
                :loading="productsLoading"
                :syncing="productsSyncing"
                :category-code="tab.categoryCode || ''"
                :category-sync="categorySync"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                @sync="syncProducts"
                @refresh="loadProducts"
              />
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>
    </PageSection>

    <SyncHistoryDrawer
      v-model="syncHistoryOpen"
      platform="1688"
      :fetcher="() => fetchPlatformSyncLogs({ platform: '1688' })"
    />
  </PageScroll>
</template>

<style scoped>
.toolbar-row { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; }
.module-tabs { margin-top:4px; }
</style>
