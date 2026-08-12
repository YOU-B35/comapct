<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { usePlatformSyncStore } from '@/stores/platformSync'
import { resolveAppError } from '@/utils/appErrorCode'
import { enqueueAndPollTemuSync } from '@/api/agentHelper'
import {
  canUseTemuBackend,
  fetchTemuSalesTrend,
  fetchTemuStores,
  loadTemuModuleData,
} from '@/api/temuApi'
import { scopeStoreIds } from '@/utils/scope'
import { useStoreAssignees } from '@/composables/useStoreAssignees'
import { bootstrapHotBroadcasts, loadHotBroadcasts } from '@/api/temuHotBroadcast'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import TemuOverviewCards from '@/components/temu/TemuOverviewCards.vue'
import TemuBossOverview from '@/components/temu/TemuBossOverview.vue'
import PriceLossTable from '@/components/temu/PriceLossTable.vue'
import SlowMovingPanel from '@/components/temu/SlowMovingPanel.vue'
import HotProductBroadcast from '@/components/temu/HotProductBroadcast.vue'
import RestockPlanner from '@/components/temu/RestockPlanner.vue'
import CompetitorAnalysis from '@/components/temu/CompetitorAnalysis.vue'
import TemuHelperStatusBar from '@/components/temu/TemuHelperStatusBar.vue'

const auth = useAuthStore()
const syncStore = usePlatformSyncStore()
const { assigneeMap, loadAssignees, enrichItems } = useStoreAssignees()
const activeTab = ref('profit')
const selectedStoreId = ref('')
const temuStores = ref([])
const productsRaw = ref([])
const loading = ref(false)
const crawling = ref(false)
const crawlHint = ref('')
const helperStatusBarRef = ref(null)
const helperOnline = ref(false)
const syncError = ref(null)
const dataLoadError = ref('')
const hotBroadcasts = ref([])
const salesTrend = ref({ labels: [], values: [] })

const useBackendData = computed(() => canUseTemuBackend(auth))
/** 用户本机 Helper：后端会话即可手动同步 / 登录（离线时按钮禁用） */
const showManualSyncControls = computed(() => useBackendData.value)
const scopedStoreIds = computed(() => scopeStoreIds(temuStores.value, auth))

function onHelperOnline(online) {
  helperOnline.value = Boolean(online)
}

const storeNameMap = computed(() =>
  Object.fromEntries(temuStores.value.map((s) => [s.id, s.storeName])),
)

function withStoreMeta(list) {
  return enrichItems(
    list.map((p) => ({
      ...p,
      storeName: storeNameMap.value[p.storeId] || '未分配店铺',
    })),
  )
}

const selectedStore = computed(
  () => temuStores.value.find((s) => s.id === selectedStoreId.value) || null,
)

const products = computed(() => {
  if (!selectedStoreId.value) return []
  let list = productsRaw.value.filter((p) => scopedStoreIds.value.has(p.storeId))
  if (selectedStoreId.value !== 'all') {
    list = list.filter((p) => p.storeId === selectedStoreId.value)
  }
  return withStoreMeta(list)
})

const overviewProducts = computed(() => products.value)

const overviewStores = computed(() => {
  if (selectedStoreId.value === 'all') return temuStores.value
  return selectedStore.value ? [selectedStore.value] : []
})

const awaitingSync = computed(
  () =>
    useBackendData.value
    && temuStores.value.length > 0
    && !loading.value
    && !crawling.value
    && productsRaw.value.length === 0
    && !syncError.value
    && !dataLoadError.value,
)

/** 全部店铺视图展示店铺列 */
const showStoreColumn = computed(() => selectedStoreId.value === 'all')

const alertCount = computed(() => {
  const p = products.value
  return {
    loss: p.filter((i) => i.isLoss).length,
    slow: p.filter((i) => i.slowMoving).length,
    hot: p.filter((i) => i.isHot).length,
    restock: p.filter((i) => i.restock.urgency !== 'normal').length,
  }
})

function ensureSelectedStore() {
  const stores = temuStores.value
  if (!stores.length) {
    selectedStoreId.value = ''
    return
  }
  if (selectedStoreId.value === 'all') return
  const stillValid = stores.some((s) => s.id === selectedStoreId.value)
  if (!stillValid) {
    selectedStoreId.value = stores[0].id
  }
}

async function loadTemuStores() {
  try {
    temuStores.value = await fetchTemuStores(auth)
    ensureSelectedStore()
  } catch (err) {
    temuStores.value = []
    selectedStoreId.value = ''
    dataLoadError.value = err.message || '加载店铺失败'
  }
}

async function loadHotBroadcastFeed(products = []) {
  hotBroadcasts.value = await bootstrapHotBroadcasts(products, auth)
}

async function loadProducts() {
  ensureSelectedStore()
  if (!temuStores.value.length || !selectedStoreId.value) {
    productsRaw.value = []
    salesTrend.value = { labels: [], values: [] }
    return
  }

  loading.value = true
  dataLoadError.value = ''
  try {
    const shopId = selectedStoreId.value
    const result = await loadTemuModuleData({
      auth,
      shopId: shopId === 'all' ? undefined : shopId,
    })
    productsRaw.value = result.products
    await loadHotBroadcastFeed(result.products)
    if (useBackendData.value && result.products?.length > 0) {
      const scopeLabel = shopId === 'all'
        ? `全部店铺 · ${result.products.length} 条 SKU`
        : `已加载 ${result.products.length} 条 SKU（${selectedStore.value?.storeName || shopId}）`
      markSidebarTemuSync({
        status: 'success',
        message: scopeLabel,
        rowCount: result.products.length,
        syncedAt: result.meta?.reportTime || '',
      })
    }
    if (auth.isBoss) {
      salesTrend.value = await fetchTemuSalesTrend({
        auth,
        shopId: shopId === 'all' ? undefined : shopId,
      })
    }
  } catch (err) {
    productsRaw.value = []
    salesTrend.value = { labels: [], values: [] }
    dataLoadError.value = err.message || '加载 Temu 数据失败'
    ElMessage.warning(dataLoadError.value)
  } finally {
    loading.value = false
  }
}

function onBroadcastsUpdate(list) {
  hotBroadcasts.value = list
}

function markSidebarTemuSync({ status, message, rowCount = 0, syncedAt = '' }) {
  // 刷新会拉全账号店铺，侧栏按店分别更新；当前页指标仍只展示选中店
  const stores = temuStores.value.length
    ? temuStores.value
    : []

  for (const store of stores) {
    const isCurrent = selectedStoreId.value === 'all' || store.id === selectedStoreId.value
    syncStore.updateStoreStatus({
      platform: 'temu',
      storeId: store.accountId || store.id,
      storeName: store.storeName,
      externalShopId: store.externalShopId || store.id,
      status,
      message: isCurrent ? message : (status === 'success' ? '账号已同步，请切换店铺查看' : message),
      rowCount: selectedStoreId.value === 'all' ? rowCount : (isCurrent ? rowCount : 0),
      syncedAt,
    })
  }
}

async function handleRefreshData() {
  if (!showManualSyncControls.value || crawling.value) return
  if (!helperOnline.value) {
    ElMessage.warning('本机同步助手未在线，请先安装并绑定')
    await helperStatusBarRef.value?.reload?.()
    return
  }

  crawling.value = true
  syncError.value = null
  crawlHint.value = '正在提交同步任务...'
  try {
    const res = await enqueueAndPollTemuSync({
      force: true,
      onStatus: ({ label }) => {
        crawlHint.value = label || '同步进行中'
      },
    })
    syncError.value = null
    await loadTemuStores()
    await loadProducts()
    await helperStatusBarRef.value?.reload?.()
    const rows = res.job?.rows_count ?? res.job?.shops?.rows_count
    const reportTime = res.job?.report_time || ''
    markSidebarTemuSync({
      status: 'success',
      message: rows != null ? `已同步 ${rows} 条销售数据` : '已刷新 Temu 数据',
      rowCount: productsRaw.value.length,
      syncedAt: reportTime,
    })
    ElMessage.success(
      res.partial
        ? (res.job?.error_message || '同步部分完成，请检查店铺数据')
        : (rows != null ? `已同步 ${rows} 条销售数据` : '已刷新 Temu 数据'),
    )
  } catch (err) {
    syncError.value = resolveAppError(
      { errorCode: err.errorCode, message: err.message },
      auth.tenantId,
    )
    markSidebarTemuSync({
      status: 'failed',
      message: syncError.value.title || err.message || 'Temu 同步失败',
    })
    ElMessage.error(syncError.value.title)
    await helperStatusBarRef.value?.reload?.()
  } finally {
    crawling.value = false
    crawlHint.value = ''
  }
}

onMounted(async () => {
  await loadAssignees()
  await loadTemuStores()
  await loadHotBroadcastFeed()
  if (selectedStoreId.value) {
    await loadProducts()
  }
})

watch(selectedStoreId, (id, prev) => {
  // 跳过首次由 ensureSelectedStore 写入（onMounted 会统一 loadProducts）
  if (!prev || !id || id === 'all' || id === prev) return
  loadProducts()
})
</script>

<template>
  <PageScroll>
    <template #header>
      <div v-if="temuStores.length" class="page-toolbar">
        <div class="store-switcher">
          <span class="store-switcher-label">切换店铺</span>
          <el-select
            v-model="selectedStoreId"
            size="default"
            class="store-switcher-select"
            placeholder="请选择店铺"
          >
            <el-option
              v-if="temuStores.length > 1"
              label="全部店铺"
              value="all"
            />
            <el-option
              v-for="store in temuStores"
              :key="store.id"
              :label="store.storeName"
              :value="store.id"
            />
          </el-select>
          <el-tag v-if="useBackendData" type="success" size="small">后端实时数据</el-tag>
          <el-tag v-if="temuStores.length > 1" type="info" size="small" effect="plain">
            同账号多店 · 共 {{ temuStores.length }} 家
          </el-tag>
          <el-button
            v-if="showManualSyncControls"
            type="primary"
            size="small"
            :icon="Refresh"
            :loading="crawling"
            :disabled="crawling || !helperOnline"
            @click="handleRefreshData"
          >
            刷新数据
          </el-button>
          <el-tag v-if="showManualSyncControls && !helperOnline" type="warning" size="small" effect="plain">
            助手离线
          </el-tag>
        </div>
      </div>

      <PageHeader
        v-else-if="!temuStores.length && !auth.isBoss"
        title="Temu 运营"
        :description="`${auth.employee.name} · 日常运营与库存管理`"
      />
    </template>

    <el-alert
      v-if="syncError"
      type="warning"
      closable
      show-icon
      style="margin-bottom: 16px"
      :title="syncError.title"
      @close="syncError = null"
    >
      <template #default>
        <p class="sync-alert-text">{{ syncError.summary }}</p>
        <ol v-if="syncError.steps?.length" class="sync-steps">
          <li v-for="(step, index) in syncError.steps" :key="index">{{ step }}</li>
        </ol>
      </template>
    </el-alert>

    <el-alert
      v-if="temuStores.length && !selectedStoreId"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
      title="请先选择店铺"
      description="未选店铺时不展示运营明细。多店账号可选手动「全部店铺」查看汇总。"
    />

    <el-alert
      v-if="dataLoadError"
      type="error"
      closable
      show-icon
      style="margin-bottom: 16px"
      :title="dataLoadError"
      @close="dataLoadError = ''"
    />

    <el-alert
      v-if="awaitingSync"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
      title="店铺已绑定，运营数据待同步"
    >
      <template #default>
        请确认本机 Sync Helper 在线后点击「刷新数据」；也可等待每日自动同步（在线助手）完成后查看结果。
      </template>
    </el-alert>

    <!-- Boss / 员工共用：有后端会话即可绑定本机助手（即使尚未分配店铺） -->
    <TemuHelperStatusBar
      v-if="showManualSyncControls"
      ref="helperStatusBarRef"
      @update:online="onHelperOnline"
    />

    <el-empty
      v-if="!temuStores.length && !loading"
      description="暂无可见的 Temu 店铺"
      :image-size="96"
    >
      <el-text type="info" size="small">
        {{
          auth.isBoss
            ? '请在「运营绑定」确认 Temu 店铺；本机可先下载并绑定 Sync Helper'
            : '请联系管理员分配 Temu 店铺；本机可先下载并绑定 Sync Helper'
        }}
      </el-text>
    </el-empty>

    <template v-else-if="temuStores.length">
      <div
        v-loading="loading || crawling"
        :element-loading-text="crawlHint || '加载中...'"
      >
        <TemuBossOverview
          v-if="auth.isBoss"
          :products="overviewProducts"
          :stores="overviewStores"
          :assignee-map="assigneeMap"
          :show-store-list="false"
          :store-name="selectedStore?.storeName || ''"
          :sales-trend="salesTrend"
          @navigate="activeTab = $event"
        />

        <TemuOverviewCards v-else :products="products" />

        <el-tabs v-model="activeTab" class="temu-tabs">
          <el-tab-pane name="profit">
            <template #label>
              <span>价格亏损</span>
              <el-badge v-if="alertCount.loss" :value="alertCount.loss" class="tab-badge" />
            </template>
            <PriceLossTable :products="products" :show-store-column="showStoreColumn" />
          </el-tab-pane>

          <el-tab-pane name="slow">
            <template #label>
              <span>滞销预警</span>
              <el-badge v-if="alertCount.slow" :value="alertCount.slow" class="tab-badge" />
            </template>
            <SlowMovingPanel :products="products" :show-store-column="showStoreColumn" />
          </el-tab-pane>

          <el-tab-pane name="hot">
            <template #label>
              <span>爆款通报</span>
              <el-badge v-if="alertCount.hot" :value="alertCount.hot" class="tab-badge" />
            </template>
            <HotProductBroadcast
              :products="products"
              :broadcasts="hotBroadcasts"
              :use-backend-data="useBackendData"
              @update:broadcasts="onBroadcastsUpdate"
            />
          </el-tab-pane>

          <el-tab-pane name="restock">
            <template #label>
              <span>备货分析</span>
              <el-badge v-if="alertCount.restock" :value="alertCount.restock" class="tab-badge" />
            </template>
            <RestockPlanner
              :products="products"
              :show-store-column="showStoreColumn"
              :use-backend-data="useBackendData"
            />
          </el-tab-pane>

          <el-tab-pane v-if="auth.isBoss" name="competitor">
            <template #label>
              <span>竞店分析</span>
            </template>
            <CompetitorAnalysis :use-backend-data="useBackendData" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>
  </PageScroll>
</template>

<style scoped>
.page-toolbar {
  margin-bottom: 16px;
}

.store-switcher {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.store-switcher-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}

.store-switcher-select {
  width: 240px;
}

.temu-tabs {
  margin-top: 20px;
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

.sync-alert-text {
  margin: 0;
  line-height: 1.6;
}

.sync-steps {
  margin: 8px 0 0;
  padding-left: 20px;
  line-height: 1.7;
}

.sync-detail {
  margin-top: 8px;
  border: none;
}

.sync-detail-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}
</style>
