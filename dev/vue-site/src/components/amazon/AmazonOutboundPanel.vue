<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { OUTBOUND_FULFILLMENT, OUTBOUND_STATUS } from '@/constants/amazonBoss'
import { summarizeOutboundOrders, formatAmazonMoney } from '@/utils/amazonBoss'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  orders: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
  initialFilter: { type: String, default: 'pending' },
})

const emit = defineEmits(['refresh', 'ship', 'open-history'])

const filter = ref(props.initialFilter)
const shippingId = ref('')
const dialogVisible = ref(false)
const activeRow = ref(null)
const trackingNo = ref('')

const summary = computed(() => summarizeOutboundOrders(props.orders))

const filterOptions = computed(() => [
  {
    label: summary.value.pending ? `待发货 (${summary.value.pending})` : '待发货',
    value: 'pending',
  },
  {
    label: summary.value.packed ? `待揽收 (${summary.value.packed})` : '待揽收',
    value: 'packed',
  },
  { label: '已发货', value: 'shipped' },
  { label: '全部', value: 'all' },
])

const filteredOrders = computed(() => {
  if (filter.value === 'all') return props.orders
  if (filter.value === 'pending') {
    return props.orders.filter((o) => o.status === 'pending' || o.status === 'pending_write')
  }
  if (filter.value === 'packed') {
    return props.orders.filter((o) => o.status === 'packed')
  }
  return props.orders.filter((o) => o.status === filter.value)
})

function fulfillmentMeta(row) {
  return OUTBOUND_FULFILLMENT[row.fulfillmentType] || OUTBOUND_FULFILLMENT.fbm
}

function statusMeta(row) {
  return OUTBOUND_STATUS[row.status] || OUTBOUND_STATUS.pending
}

function handleShip(row) {
  activeRow.value = row
  trackingNo.value = row.trackingNo || ''
  dialogVisible.value = true
}

function submitShip() {
  if (!trackingNo.value.trim()) {
    ElMessage.warning('请输入运单号')
    return
  }
  shippingId.value = activeRow.value.id
  emit('ship', { id: activeRow.value.id, trackingNo: trackingNo.value.trim() })
}

function finishShip() {
  shippingId.value = ''
  dialogVisible.value = false
  activeRow.value = null
}

watch(
  () => props.initialFilter,
  (value) => {
    if (value === 'outbound:packed') filter.value = 'packed'
    else if (value === 'outbound') filter.value = 'pending'
    else if (value) filter.value = value
  },
)

defineExpose({ finishShip })
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="订单发货"
      description="FBA 与自发货（FBM）待处理订单，优先处理临近截止时间的订单"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      action-label="刷新订单"
      :loading="loading"
      @action="$emit('refresh')"
      @open-history="$emit('open-history')"
    />

    <div class="mini-stats">
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.pending }}</span>
        <span class="mini-stat__label">待发货</span>
      </div>
      <div class="mini-stat is-warning">
        <span class="mini-stat__value">{{ summary.packed }}</span>
        <span class="mini-stat__label">待揽收</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.fbmPending }}</span>
        <span class="mini-stat__label">FBM 待处理</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.fbaPending }}</span>
        <span class="mini-stat__label">FBA 待处理</span>
      </div>
    </div>

    <el-segmented v-model="filter" :options="filterOptions" size="small" />

    <el-table :data="filteredOrders" stripe size="small" v-loading="loading">
      <el-table-column prop="orderNo" label="订单号" min-width="150" />
      <el-table-column v-if="showStoreColumn" label="店铺" width="130">
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <AssigneeTableColumn width="90" />
      <el-table-column prop="productName" label="商品" min-width="150" show-overflow-tooltip />
      <el-table-column label="数量" width="60" align="center">
        <template #default="{ row }">{{ row.quantity }}</template>
      </el-table-column>
      <el-table-column label="金额" width="100" align="right">
        <template #default="{ row }">{{ formatAmazonMoney(row.amount, row.currency) }}</template>
      </el-table-column>
      <el-table-column label="配送" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="fulfillmentMeta(row).type" size="small">{{ fulfillmentMeta(row).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="shipDeadline" label="发货截止" width="150" />
      <el-table-column prop="buyerRegion" label="地区" width="80" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row).type" size="small">{{ statusMeta(row).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'pending' || row.status === 'packed'"
            link
            type="primary"
            size="small"
            :loading="shippingId === row.id"
            @click="handleShip(row)"
          >
            标记发货
          </el-button>
          <el-tag v-else-if="row.status === 'pending_write'" size="small" type="warning">写回中</el-tag>
          <span v-else-if="row.trackingNo" class="tracking">{{ row.trackingNo }}</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="标记发货" width="440px" destroy-on-close>
      <el-form v-if="activeRow" label-width="80px">
        <el-form-item label="订单号">{{ activeRow.orderNo }}</el-form-item>
        <el-form-item label="运单号" required>
          <el-input v-model="trackingNo" placeholder="填写物流单号，将写回 Seller Central" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="shippingId === activeRow?.id" @click="submitShip">确认发货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.amz-panel {
  display: grid;
  gap: 16px;
}

.mini-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

@media (max-width: 960px) {
  .mini-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

.mini-stat {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.mini-stat.is-danger .mini-stat__value {
  color: var(--el-color-danger);
}

.mini-stat.is-warning .mini-stat__value {
  color: var(--el-color-warning);
}

.mini-stat__value {
  font-size: 18px;
  font-weight: 700;
}

.mini-stat__label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.tracking {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
