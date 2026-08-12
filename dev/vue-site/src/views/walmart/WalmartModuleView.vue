<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  fetchTodayWalmartOrders,
  loadWalmartListingIssues,
  crawlWalmartListingIssues,
  resolveWalmartIssue,
} from '@/api/walmart'
import { fetchWalmartStores } from '@/api/platformAccounts'
import { scopeStores } from '@/utils/scope'
import { useStoreAssignees } from '@/composables/useStoreAssignees'
import { enrichListingIssue } from '@/utils/walmart'
import { isPlatformOperationalDemoOnly, platformOperationalHint } from '@/utils/platformOperationalMode'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import WalmartBossOverview from '@/components/walmart/WalmartBossOverview.vue'
import WalmartOrdersPanel from '@/components/walmart/WalmartOrdersPanel.vue'
import WalmartListingsPanel from '@/components/walmart/WalmartListingsPanel.vue'

const auth = useAuthStore()
const { assigneeMap, loadAssignees, enrichItems } = useStoreAssignees()
const router = useRouter()
const activeTab = ref('orders')
const selectedStoreId = ref('all')
const walmartStores = ref([])
const todayOrders = ref([])
const listingIssues = ref([])
const ordersSyncedAt = ref('')
const listingsSyncedAt = ref('')
const loadingStores = ref(false)
const loadingOrders = ref(false)
const loadingListings = ref(false)
const listingsPanel = ref(null)
const listingsFilter = ref('all')

const operationalDemoOnly = computed(() => isPlatformOperationalDemoOnly('walmart'))
const operationalHint = computed(() => platformOperationalHint('walmart'))

const storeNameMap = computed(() =>
  Object.fromEntries(walmartStores.value.map((store) => [store.id, store.storeName])),
)

const enrichedOrders = computed(() => enrichItems(todayOrders.value))
const enrichedIssues = computed(() =>
  enrichItems(listingIssues.value.map((issue) => enrichListingIssue(issue))),
)

const showStoreColumn = computed(() => selectedStoreId.value === 'all')

const showStoreList = computed(
  () => selectedStoreId.value === 'all' && walmartStores.value.length > 0,
)

const overviewStores = computed(() => {
  if (selectedStoreId.value === 'all') {
    return walmartStores.value
  }
  return walmartStores.value.filter((store) => store.id === selectedStoreId.value)
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
  filteredOrders.value.filter((order) => {
    if (order.fulfillmentType === 'wfs') {
      return ['待拣货', '待发货'].includes(order.status)
    }
    return ['待确认', '待发货'].includes(order.status)
  }).length,
)

const pendingListingCount = computed(() =>
  filteredIssues.value.filter((item) => !item.resolved).length,
)

async function syncTodayOrders(refresh = false) {
  if (operationalDemoOnly.value || !walmartStores.value.length) {
    todayOrders.value = []
    ordersSyncedAt.value = ''
    return
  }

  loadingOrders.value = true
  try {
    const res = await fetchTodayWalmartOrders(walmartStores.value, { refresh })
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

async function syncListings(refresh = false) {
  if (operationalDemoOnly.value || !walmartStores.value.length) {
    listingIssues.value = []
    listingsSyncedAt.value = ''
    return
  }

  loadingListings.value = true
  try {
    const res = refresh
      ? await crawlWalmartListingIssues(walmartStores.value, { refresh: true })
      : loadWalmartListingIssues(walmartStores.value)
    listingIssues.value = res.data.issues
    listingsSyncedAt.value = res.data.syncedAt
    if (refresh) {
      ElMessage.success(res.message || '已刷新 Listing 问题')
    }
  } catch (err) {
    ElMessage.error(err.message || 'Listing 问题抓取失败')
  } finally {
    loadingListings.value = false
  }
}

async function handleResolveIssue(payload) {
  try {
    const res = resolveWalmartIssue(payload.id)
    const index = listingIssues.value.findIndex((item) => item.id === payload.id)
    if (index !== -1) {
      listingIssues.value[index] = res.data
    }
    ElMessage.success('已标记为已解决')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    listingsPanel.value?.finishResolve?.()
  }
}

async function loadWalmartModule() {
  loadingStores.value = true
  try {
    const res = await fetchWalmartStores()
    walmartStores.value = scopeStores(res.data || [], auth)
    if (walmartStores.value.length && !operationalDemoOnly.value) {
      await Promise.all([syncTodayOrders(false), syncListings(false)])
    } else if (!walmartStores.value.length) {
      todayOrders.value = []
      listingIssues.value = []
      ordersSyncedAt.value = ''
      listingsSyncedAt.value = ''
    }
  } catch {
    walmartStores.value = []
    todayOrders.value = []
    listingIssues.value = []
    ordersSyncedAt.value = ''
    listingsSyncedAt.value = ''
  } finally {
    loadingStores.value = false
  }
}

function goToAccountBinding() {
  router.push(auth.isBoss ? '/boss/accounts' : '/employee/dashboard')
}

function handleOverviewNavigate(target) {
  if (target.startsWith('listings')) {
    activeTab.value = 'listings'
    const filter = target === 'listings:high' ? 'high' : 'open'
    listingsFilter.value = filter
    listingsPanel.value?.setFilter?.(filter)
    return
  }
  activeTab.value = target
}

watch(walmartStores, (stores) => {
  if (selectedStoreId.value === 'all') return
  if (!stores.some((store) => store.id === selectedStoreId.value)) {
    selectedStoreId.value = 'all'
  }
})

onMounted(async () => {
  await loadAssignees()
  await loadWalmartModule()
})
onActivated(loadWalmartModule)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="Walmart 运营"
        eyebrow="平台"
        :description="
          auth.isBoss
            ? '订单处理与 Listing 跟进'
            : `${auth.employee.name} · 订单处理与 Listing 跟进`
        "
      />
    </template>

    <PageSection v-if="walmartStores.length" tone="toolbar" title="店铺">
      <el-radio-group v-model="selectedStoreId" size="small">
        <el-radio-button value="all">全部店铺</el-radio-button>
        <el-radio-button
          v-for="store in walmartStores"
          :key="store.id"
          :value="store.id"
        >
          {{ store.storeName }}
        </el-radio-button>
      </el-radio-group>
    </PageSection>

    <PageSection v-if="!loadingStores && !walmartStores.length" flush>
      <el-empty
        description="暂无可见的 Walmart 店铺"
        :image-size="96"
      >
        <el-text type="info" size="small">
          {{ auth.isBoss ? '请先在「账户绑定」中绑定 Walmart 店铺' : '请联系企业管理员在运营绑定中分配负责店铺' }}
        </el-text>
        <el-button v-if="auth.isBoss" type="primary" style="margin-top: 16px" @click="goToAccountBinding">
          前往账户绑定
        </el-button>
      </el-empty>
    </PageSection>

    <template v-else-if="walmartStores.length">
      <el-alert
        v-if="operationalDemoOnly && operationalHint"
        :title="operationalHint"
        type="info"
        show-icon
        :closable="false"
        class="operational-hint"
      />

      <PageSection title="经营概览与明细">
      <WalmartBossOverview
        v-if="auth.isBoss"
        :orders="filteredOrders"
        :issues="filteredIssues"
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
            <WalmartOrdersPanel
              :orders="filteredOrders"
              :synced-at="ordersSyncedAt"
              :loading="loadingOrders"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncTodayOrders(true)"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="listings">
          <template #label>
            <span>Listing 问题</span>
            <el-badge v-if="pendingListingCount" :value="pendingListingCount" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <WalmartListingsPanel
              ref="listingsPanel"
              :issues="filteredIssues"
              :synced-at="listingsSyncedAt"
              :loading="loadingListings"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              :initial-filter="listingsFilter"
              @refresh="syncListings(true)"
              @resolve="handleResolveIssue"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
      </PageSection>
    </template>
  </PageScroll>
</template>

<style scoped>
.module-tabs {
  margin-top: 12px;
}

.tab-panel {
  padding: 12px 0 4px;
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
