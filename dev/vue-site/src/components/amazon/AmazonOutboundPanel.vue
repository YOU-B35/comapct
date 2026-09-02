<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { OUTBOUND_FULFILLMENT, OUTBOUND_STATUS } from '@/constants/amazonBoss'
import { summarizeOutboundOrders, formatAmazonMoney } from '@/utils/amazonBoss'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
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

const { page, pageSize, total, paged } = useFuzzySearchPagination(filteredOrders, {
  pageSize: 15,
  fields: [],
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

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="pending">{{ summary.pending ? `待发货 (${summary.pending})` : '待发货' }}</el-radio-button>
        <el-radio-button value="packed">{{ summary.packed ? `待揽收 (${summary.packed})` : '待揽收' }}</el-radio-button>
        <el-radio-button value="shipped">已发货</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="paged" stripe size="small" v-loading="loading" class="amazon-list">
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

    <div class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        small
        layout="total, prev, pager, next"
        :total="total"
      />
    </div>

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

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.tracking {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.amazon-list :deep(.el-table__cell .cell) {
  font-size: 12px;
  line-height: 1.4;
}

.amazon-list :deep(.el-table__cell) {
  padding: 5px 0;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>
