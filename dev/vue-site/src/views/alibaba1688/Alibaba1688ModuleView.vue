<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { loadAlibaba1688OperationalData } from '@/api/alibaba1688'
import { fetchAlibaba1688Stores } from '@/api/platformAccounts'
import { scopeStores } from '@/utils/scope'
import { useStoreAssignees } from '@/composables/useStoreAssignees'
import { pushPlatformOrderToWarehouse, enrichOrdersWithWarehouseFeedback } from '@/api/platformShipRequests'
import { isPlatformOperationalDemoOnly, platformOperationalHint } from '@/utils/platformOperationalMode'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import Alibaba1688BossOverview from '@/components/alibaba1688/Alibaba1688BossOverview.vue'
import Alibaba1688PurchasePanel from '@/components/alibaba1688/Alibaba1688PurchasePanel.vue'
import Alibaba1688SupplierPanel from '@/components/alibaba1688/Alibaba1688SupplierPanel.vue'
import PlatformShipPushDialog from '@/components/domestic/PlatformShipPushDialog.vue'

const auth = useAuthStore()
const router = useRouter()
const { assigneeMap, loadAssignees, enrichItems } = useStoreAssignees()
const activeTab = ref('purchase')
const selectedStoreId = ref('all')
const stores1688 = ref([])
const purchaseOrders = ref([])
const supplierAlerts = ref([])
const syncedAt = ref('')
const loadingStores = ref(false)
const shipDialogVisible = ref(false)
const shipDialogOrder = ref(null)
const shipDialogType = ref('push')
const shipSubmitting = ref(false)

const operationalDemoOnly = computed(() => isPlatformOperationalDemoOnly('1688'))
const operationalHint = computed(() => platformOperationalHint('1688'))

const storeNameMap = computed(() =>
  Object.fromEntries(stores1688.value.map((store) => [store.id, store.storeName])),
)

const enrichedOrders = computed(() => enrichItems(purchaseOrders.value))
const enrichedAlerts = computed(() => enrichItems(supplierAlerts.value))

const filteredOrders = computed(() => {
  if (selectedStoreId.value === 'all') return enrichedOrders.value
  return enrichedOrders.value.filter((order) => order.storeId === selectedStoreId.value)
})

const filteredAlerts = computed(() => {
  if (selectedStoreId.value === 'all') return enrichedAlerts.value
  return enrichedAlerts.value.filter((alert) => alert.storeId === selectedStoreId.value)
})

const overviewStores = computed(() => {
  if (selectedStoreId.value === 'all') return stores1688.value
  return stores1688.value.filter((store) => store.id === selectedStoreId.value)
})

const showStoreList = computed(
  () => selectedStoreId.value === 'all' && stores1688.value.length > 0,
)

const showStoreColumn = computed(() => selectedStoreId.value === 'all')

const pendingPurchaseCount = computed(() =>
  filteredOrders.value.filter((order) => order.isActionNeeded).length,
)

const openAlertCount = computed(() =>
  filteredAlerts.value.filter((alert) => alert.isOpen).length,
)

async function loadModuleData() {
  loadingStores.value = true
  try {
    const res = await fetchAlibaba1688Stores()
    stores1688.value = scopeStores(res.data || [], auth)
    if (stores1688.value.length && !operationalDemoOnly.value) {
      const demoRes = loadAlibaba1688OperationalData(stores1688.value)
      purchaseOrders.value = enrichOrdersWithWarehouseFeedback(demoRes.data.purchaseOrders)
      supplierAlerts.value = demoRes.data.supplierAlerts
      syncedAt.value = demoRes.data.syncedAt
    } else if (!stores1688.value.length) {
      purchaseOrders.value = []
      supplierAlerts.value = []
      syncedAt.value = ''
    }
  } catch {
    stores1688.value = []
    purchaseOrders.value = []
    supplierAlerts.value = []
    syncedAt.value = ''
  } finally {
    loadingStores.value = false
  }
}

function refreshData() {
  if (!stores1688.value.length || operationalDemoOnly.value) return
  const demoRes = loadAlibaba1688OperationalData(stores1688.value)
  purchaseOrders.value = enrichOrdersWithWarehouseFeedback(demoRes.data.purchaseOrders)
  supplierAlerts.value = demoRes.data.supplierAlerts
  syncedAt.value = demoRes.data.syncedAt
  ElMessage.success('已刷新 1688 运营数据')
}

function goToAccountBinding() {
  router.push(auth.isBoss ? '/boss/accounts' : '/employee/dashboard')
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
      platformKey: '1688',
      order: shipDialogOrder.value,
      storeName: storeNameMap.value[shipDialogOrder.value.storeId] || '',
      warehouseId,
      type,
      remark,
    })
    const updated = res.data?.platformOrder
    if (updated) {
      const index = purchaseOrders.value.findIndex((item) => item.id === updated.id)
      if (index !== -1) purchaseOrders.value[index] = updated
    }
    ElMessage.success(res.message)
    shipDialogVisible.value = false
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    shipSubmitting.value = false
  }
}

watch(stores1688, (stores) => {
  if (selectedStoreId.value === 'all') return
  if (!stores.some((store) => store.id === selectedStoreId.value)) {
    selectedStoreId.value = 'all'
  }
})

onMounted(async () => {
  await loadAssignees()
  await loadModuleData()
})
onActivated(loadModuleData)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="1688 运营"
        eyebrow="平台"
        :description="
          auth.isBoss
            ? '采购订单与供应商跟进'
            : `${auth.employee.name} · 采购订单与供应商跟进`
        "
      />
    </template>

    <PageSection v-if="stores1688.length" tone="toolbar" title="店铺">
      <el-radio-group v-model="selectedStoreId" size="small">
        <el-radio-button value="all">全部账号</el-radio-button>
        <el-radio-button
          v-for="store in stores1688"
          :key="store.id"
          :value="store.id"
        >
          {{ store.storeName }}
        </el-radio-button>
      </el-radio-group>
    </PageSection>

    <PageSection v-if="!loadingStores && !stores1688.length" flush>
      <el-empty
        description="暂无可见的 1688 采购账号"
        :image-size="96"
      >
        <el-text type="info" size="small">
          {{ auth.isBoss ? '请先在「账户绑定」中绑定 1688 采购账号' : '请联系企业管理员在运营绑定中分配负责账号' }}
        </el-text>
        <el-button v-if="auth.isBoss" type="primary" style="margin-top: 16px" @click="goToAccountBinding">
          前往账户绑定
        </el-button>
      </el-empty>
    </PageSection>

    <template v-else-if="stores1688.length">
      <el-alert
        v-if="operationalDemoOnly && operationalHint"
        :title="operationalHint"
        type="info"
        show-icon
        :closable="false"
        class="operational-hint"
      />

      <PageSection title="经营概览与明细">
        <Alibaba1688BossOverview
          v-if="auth.isBoss"
          :purchase-orders="filteredOrders"
          :supplier-alerts="filteredAlerts"
          :stores="overviewStores"
          :assignee-map="assigneeMap"
          :show-store-list="showStoreList"
          @navigate="activeTab = $event"
        />

        <el-tabs v-model="activeTab" class="module-tabs">
          <el-tab-pane name="purchase">
            <template #label>
              <span>采购订单</span>
              <el-badge v-if="pendingPurchaseCount" :value="pendingPurchaseCount" class="tab-badge" />
            </template>
            <div class="tab-panel">
              <Alibaba1688PurchasePanel
                :orders="filteredOrders"
                :synced-at="syncedAt"
                :loading="loadingStores"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                @refresh="refreshData"
                @ship-push="openShipDialog($event, 'push')"
                @ship-urge="openShipDialog($event, 'urge')"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane name="supplier">
            <template #label>
              <span>供应商跟进</span>
              <el-badge v-if="openAlertCount" :value="openAlertCount" class="tab-badge" />
            </template>
            <div class="tab-panel">
              <Alibaba1688SupplierPanel
                :alerts="filteredAlerts"
                :synced-at="syncedAt"
                :loading="loadingStores"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                @refresh="refreshData"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
      </PageSection>

      <PlatformShipPushDialog
        v-model="shipDialogVisible"
        :order="shipDialogOrder"
        platform-key="1688"
        platform-label="1688"
        :store-name="shipDialogOrder ? storeNameMap[shipDialogOrder.storeId] : ''"
        :request-type="shipDialogType"
        :submitting="shipSubmitting"
        @submit="submitShipPush"
      />
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
