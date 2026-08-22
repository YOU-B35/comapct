<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, onActivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Plus, Refresh, View } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import {
  canCancelOrder,
  canDeleteOrder,
  canMarkShipped,
  canReleaseBlocked,
  canReviewOrder,
  cancelWarehouseOrder,
  createWarehouseOrder,
  deleteWarehouseOrder,
  fetchWarehouseOrders,
  fetchWarehouseOrder,
  markWarehouseOrderShipped,
  releaseBlockedWarehouseOrder,
  submitWarehouseReview,
} from '@/api/warehouseOrders'
import { ORDER_STATUS_OPTIONS } from '@/constants/warehouseOrders'
import { statusLabel, statusTagType } from '@/utils/warehouseOrders'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import WarehouseOrderFormDialog from '@/components/warehouse/WarehouseOrderFormDialog.vue'
import WarehouseReviewDialog from '@/components/warehouse/WarehouseReviewDialog.vue'
import WarehouseReleaseDialog from '@/components/warehouse/WarehouseReleaseDialog.vue'
import WarehouseOrderDetailDrawer from '@/components/warehouse/WarehouseOrderDetailDrawer.vue'
import WarehouseScopePanel from '@/components/warehouse/WarehouseScopePanel.vue'

const auth = useAuthStore()
const route = useRoute()

const loading = ref(false)
const orders = ref([])
const stats = ref({ total: 0, pendingReview: 0, pendingShipment: 0, blocked: 0, shipped: 0 })
const filterStatus = ref('all')
const formVisible = ref(false)
const reviewVisible = ref(false)
const releaseVisible = ref(false)
const detailVisible = ref(false)
const activeOrder = ref(null)

const routeStatusFilter = computed(() => {
  const filter = route.meta.orderStatusFilter
  if (Array.isArray(filter)) return filter
  if (filter) return [filter]
  return null
})

const pageTitle = computed(() => {
  if (auth.isWarehouse && route.meta.title) return route.meta.title
  return '仓库下单'
})

const pageDescription = computed(() => {
  if (auth.isWarehouse) {
    if (route.path.includes('pending-review')) {
      return '处理运营/管理员提交的出库申请，审批后进入待发货或暂不可发。'
    }
    if (route.path.includes('pending-shipment')) {
      return '待出库与暂不可发订单；补货完成后可确认可发并标记发货。'
    }
    if (route.path.includes('shipped')) {
      return '已完成出库的订单记录。'
    }
    return '接收运营/管理员出库申请，审批反馈后进入待发货或暂不可发；补货完成后可确认可发并出库。'
  }
  if (auth.isBoss) {
    return '向仓库提交出库需求，查看全员下单记录与仓库审批反馈。'
  }
  return '提交仓库出库申请，仅可查看与管理本人下单记录及仓库反馈。'
})

const filteredOrders = computed(() => {
  let list = orders.value
  if (routeStatusFilter.value?.length) {
    list = list.filter((item) => routeStatusFilter.value.includes(item.status))
  } else if (filterStatus.value !== 'all') {
    list = list.filter((item) => item.status === filterStatus.value)
  }
  return [...list].sort((a, b) => {
    const urgeA = a.lastUrgedAt || ''
    const urgeB = b.lastUrgedAt || ''
    if (urgeA && urgeB) return urgeB.localeCompare(urgeA)
    if (urgeA) return -1
    if (urgeB) return 1
    return String(b.submittedAt).localeCompare(String(a.submittedAt))
  })
})

function rowClassName({ row }) {
  return row.shipUrges?.length ? 'order-row--urged' : ''
}

async function refreshActiveOrder() {
  if (!activeOrder.value?.id) return
  try {
    const fresh = await fetchWarehouseOrder(activeOrder.value.id, auth)
    if (fresh) activeOrder.value = fresh
  } catch {
    /* ignore */
  }
}

const canCreate = computed(() => auth.isBoss || auth.isEmployee)

async function loadOrders() {
  loading.value = true
  try {
    const res = await fetchWarehouseOrders(auth, {})
    orders.value = res.data
    stats.value = res.stats
  } catch (err) {
    ElMessage.error(err.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function openDetail(order) {
  try {
    const fresh = await fetchWarehouseOrder(order.id, auth)
    activeOrder.value = fresh || order
  } catch {
    activeOrder.value = order
  }
  detailVisible.value = true
}

function openReview(order) {
  activeOrder.value = order
  reviewVisible.value = true
}

function openRelease(order) {
  activeOrder.value = order
  releaseVisible.value = true
}

async function handleCreate(payload) {
  try {
    await createWarehouseOrder(auth, payload)
    ElMessage.success('已提交至仓库，等待审批')
    formVisible.value = false
    await loadOrders()
  } catch (err) {
    ElMessage.error(err.message || '提交失败')
  }
}

async function handleReview(payload) {
  try {
    await submitWarehouseReview(auth, activeOrder.value.id, payload)
    ElMessage.success(payload.canShip ? '已反馈：订单进入待发货' : '已反馈：订单暂不可发')
    reviewVisible.value = false
    detailVisible.value = false
    await loadOrders()
  } catch (err) {
    ElMessage.error(err.message || '审批失败')
  }
}

async function handleRelease(payload) {
  try {
    await releaseBlockedWarehouseOrder(auth, activeOrder.value.id, payload)
    ElMessage.success('已确认可发，订单进入待发货')
    releaseVisible.value = false
    detailVisible.value = false
    await loadOrders()
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  }
}

async function handleShip(order) {
  try {
    await ElMessageBox.confirm(`确认将 ${order.orderNo} 标记为已发货？`, '出库确认')
    await markWarehouseOrderShipped(order.id, auth)
    ElMessage.success('已标记为已发货')
    detailVisible.value = false
    await loadOrders()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message || '操作失败')
  }
}

async function handleCancel(order) {
  try {
    await ElMessageBox.confirm(`确认取消出库单 ${order.orderNo}？`, '取消订单')
    await cancelWarehouseOrder(order.id, auth)
    ElMessage.success('订单已取消')
    detailVisible.value = false
    await loadOrders()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message || '操作失败')
  }
}

async function handleDelete(order) {
  try {
    await ElMessageBox.confirm(
      `确定删除出库单 ${order.orderNo}？删除后不可恢复。`,
      '删除订单',
      { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' },
    )
    await deleteWarehouseOrder(order.id, auth)
    ElMessage.success('订单已删除')
    detailVisible.value = false
    await loadOrders()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message || '删除失败')
  }
}

watch(() => route.path, () => {
  if (auth.isWarehouse) detailVisible.value = false
})

function handleWarehouseOrdersChanged() {
  loadOrders()
  if (detailVisible.value) refreshActiveOrder()
}

function handleStorageChange(event) {
  if (event.key === 'crosshub_warehouse_orders') handleWarehouseOrdersChanged()
}

onMounted(() => {
  loadOrders()
  window.addEventListener('crosshub-warehouse-orders-changed', handleWarehouseOrdersChanged)
  window.addEventListener('storage', handleStorageChange)
})

onActivated(loadOrders)

onUnmounted(() => {
  window.removeEventListener('crosshub-warehouse-orders-changed', handleWarehouseOrdersChanged)
  window.removeEventListener('storage', handleStorageChange)
})
</script>

<template>
  <PageScroll>
    <PageHeader :title="pageTitle" eyebrow="仓储" :description="pageDescription">
      <template #actions>
        <el-button :icon="Refresh" @click="loadOrders">刷新</el-button>
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="formVisible = true">
          新建出库单
        </el-button>
      </template>
    </PageHeader>

    <WarehouseScopePanel v-if="auth.isWarehouse" variant="alert" class="scope-banner" />

    <PageSection v-if="!auth.isWarehouse" title="订单概览">
    <div class="stat-row">
      <div class="stat-card">
        <span>全部</span>
        <strong>{{ stats.total }}</strong>
      </div>
      <div class="stat-card stat-card--warn">
        <span>待审核</span>
        <strong>{{ stats.pendingReview }}</strong>
      </div>
      <div class="stat-card stat-card--ok">
        <span>待发货</span>
        <strong>{{ stats.pendingShipment }}</strong>
      </div>
      <div class="stat-card stat-card--danger">
        <span>暂不可发</span>
        <strong>{{ stats.blocked }}</strong>
      </div>
      <div class="stat-card">
        <span>已发货</span>
        <strong>{{ stats.shipped }}</strong>
      </div>
    </div>
    </PageSection>

    <PageSection title="出库单列表">
    <div v-if="!routeStatusFilter?.length" class="toolbar">
      <el-radio-group v-model="filterStatus" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button
          v-for="opt in ORDER_STATUS_OPTIONS"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <el-table
      v-loading="loading"
      :data="filteredOrders"
      :row-class-name="rowClassName"
      border
      stripe
      class="order-table"
    >
      <el-table-column prop="orderNo" label="单号" width="140" />
      <el-table-column prop="warehouseName" label="出库仓库" width="120" show-overflow-tooltip />
      <el-table-column prop="sourceLabel" label="货源" min-width="160" show-overflow-tooltip />
      <el-table-column label="平台单号" width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <template v-if="row.platformOrderNo">
            {{ row.platformOrderNo }}
          </template>
          <el-text v-else type="info" size="small">—</el-text>
        </template>
      </el-table-column>
      <el-table-column label="催促" width="120" align="center">
        <template #default="{ row }">
          <template v-if="row.shipUrges?.length">
            <el-tag type="warning" size="small" effect="dark">
              催 {{ row.shipUrges.length }}
            </el-tag>
            <el-text v-if="row.lastUrgedAt" size="small" type="warning" class="urge-time">
              {{ formatUtc8(row.lastUrgedAt).slice(5, 16) }}
            </el-text>
          </template>
          <el-text v-else type="info" size="small">—</el-text>
        </template>
      </el-table-column>
      <el-table-column label="货品" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.items?.map((i) => i.productName).join('、') }}
        </template>
      </el-table-column>
      <el-table-column prop="submittedByName" label="下单人" width="100" />
      <el-table-column prop="submittedAt" label="提交时间" width="160" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small" effect="light">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="仓库反馈" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.warehouseReview">{{ row.warehouseReview.reviewRemark }}</span>
          <el-text v-else type="info">待审批</el-text>
        </template>
      </el-table-column>
      <el-table-column label="操作" :width="auth.isBoss ? 300 : 260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :icon="View" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="canReviewOrder(auth, row)"
            link
            type="warning"
            @click="openReview(row)"
          >
            审批
          </el-button>
          <el-button
            v-if="canReleaseBlocked(auth, row)"
            link
            type="success"
            @click="openRelease(row)"
          >
            确认可发
          </el-button>
          <el-button
            v-if="canMarkShipped(auth, row)"
            link
            type="success"
            @click="handleShip(row)"
          >
            发货
          </el-button>
          <el-button
            v-if="canDeleteOrder(auth, row)"
            link
            type="danger"
            :icon="Delete"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    </PageSection>

    <WarehouseOrderFormDialog v-model="formVisible" @submit="handleCreate" />

    <WarehouseReviewDialog
      v-model="reviewVisible"
      :order="activeOrder"
      @submit="handleReview"
    />

    <WarehouseReleaseDialog
      v-model="releaseVisible"
      :order="activeOrder"
      @submit="handleRelease"
    />

    <WarehouseOrderDetailDrawer
      v-model="detailVisible"
      :order="activeOrder"
      show-actions
    >
      <template #actions>
        <el-button
          v-if="activeOrder && canReviewOrder(auth, activeOrder)"
          type="warning"
          @click="openReview(activeOrder)"
        >
          仓库审批
        </el-button>
        <el-button
          v-if="activeOrder && canReleaseBlocked(auth, activeOrder)"
          type="success"
          @click="openRelease(activeOrder)"
        >
          确认可发
        </el-button>
        <el-button
          v-if="activeOrder && canMarkShipped(auth, activeOrder)"
          type="success"
          @click="handleShip(activeOrder)"
        >
          标记已发货
        </el-button>
        <el-button
          v-if="activeOrder && canCancelOrder(auth, activeOrder)"
          type="danger"
          plain
          @click="handleCancel(activeOrder)"
        >
          取消订单
        </el-button>
        <el-button
          v-if="activeOrder && canDeleteOrder(auth, activeOrder)"
          type="danger"
          :icon="Delete"
          @click="handleDelete(activeOrder)"
        >
          删除订单
        </el-button>
      </template>
    </WarehouseOrderDetailDrawer>
  </PageScroll>
</template>

<style scoped>
.scope-banner {
  margin-bottom: 16px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  padding: 12px 14px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-md);
  background: var(--ch-surface);
}

.stat-card span {
  display: block;
  font-size: 12px;
  color: var(--ch-text-muted);
}

.stat-card strong {
  font-size: 22px;
  font-weight: 600;
  color: var(--ch-text);
}

.stat-card--warn strong { color: var(--el-color-warning); }
.stat-card--ok strong { color: var(--el-color-success); }
.stat-card--danger strong { color: var(--el-color-danger); }

.toolbar {
  margin-bottom: 12px;
}

.order-table {
  flex: 1;
}

.order-table :deep(.order-row--urged) {
  background-color: var(--el-color-warning-light-9) !important;
}

.urge-time {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.2;
}

@media (max-width: 960px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
