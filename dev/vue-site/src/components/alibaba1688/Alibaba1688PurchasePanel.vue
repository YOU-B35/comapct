<script setup>
import { computed, ref } from 'vue'
import { summarize1688PurchaseOrders } from '@/utils/alibaba1688'
import { formatMoneyDecimal } from '@/utils/format'
import {
  canPushPlatformOrder,
  canUrgePlatformOrder,
  shipRequestMeta,
} from '@/utils/platformShipToWarehouse'
import Alibaba1688PanelHeader from '@/components/alibaba1688/Alibaba1688PanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  orders: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
  showShipActions: { type: Boolean, default: true },
})

defineEmits(['refresh', 'ship-push', 'ship-urge'])

const statusFilter = ref('all')

const summary = computed(() => summarize1688PurchaseOrders(props.orders))

const filterOptions = computed(() => [
  { label: '全部', value: 'all' },
  { label: summary.value.pendingPayment ? `待付款 (${summary.value.pendingPayment})` : '待付款', value: 'pending_payment' },
  { label: summary.value.pendingShipment ? `待发货 (${summary.value.pendingShipment})` : '待发货', value: 'pending_shipment' },
  { label: summary.value.pendingReceive ? `待收货 (${summary.value.pendingReceive})` : '待收货', value: 'pending_receive' },
  { label: '已完成', value: 'completed' },
])

const filteredOrders = computed(() => {
  if (statusFilter.value === 'all') return props.orders
  return props.orders.filter((order) => order.status === statusFilter.value)
})
</script>

<template>
  <div class="panel">
    <Alibaba1688PanelHeader
      title="采购订单"
      description="1688 采购单状态：待付款 → 待发货 → 待收货 → 已完成"
      :synced-at="syncedAt"
      action-label="刷新采购单"
      :loading="loading"
      @action="$emit('refresh')"
    />

    <div class="mini-stats">
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.total }}</span>
        <span class="mini-stat__label">采购单</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.totalAmountText }}</span>
        <span class="mini-stat__label">采购总额</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.pending }}</span>
        <span class="mini-stat__label">待跟进</span>
      </div>
    </div>

    <el-segmented v-model="statusFilter" :options="filterOptions" />

    <el-table :data="filteredOrders" stripe size="small" v-loading="loading" class="data-table">
      <el-table-column prop="orderNo" label="采购单号" min-width="140" fixed />
      <el-table-column
        v-if="showStoreColumn"
        label="采购账号"
        min-width="130"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <AssigneeTableColumn />
      <el-table-column prop="productName" label="商品" min-width="150" show-overflow-tooltip />
      <el-table-column prop="supplierName" label="供应商" min-width="150" show-overflow-tooltip />
      <el-table-column prop="quantity" label="数量" width="80" align="center" />
      <el-table-column label="单价" width="90" align="right">
        <template #default="{ row }">{{ formatMoneyDecimal(row.unitPrice) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="100" align="right">
        <template #default="{ row }">{{ row.amountText || formatMoneyDecimal(row.amount) }}</template>
      </el-table-column>
      <el-table-column prop="linkedPlatform" label="关联平台" width="100" />
      <el-table-column prop="expectedShipAt" label="预计发货" width="110" />
      <el-table-column prop="expectedArrivalAt" label="预计到货" width="110" />
      <el-table-column label="异常" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.isDelayed" type="warning" size="small" style="margin-right: 4px">延期</el-tag>
          <el-tag v-if="row.isStockout" type="danger" size="small">缺货</el-tag>
          <span v-if="!row.isDelayed && !row.isStockout">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.statusType" size="small">{{ row.statusLabel }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="showShipActions" label="仓库" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <template v-if="shipRequestMeta(row)">
            <div class="warehouse-cell">
              <div class="warehouse-cell__row">
                <el-tag size="small" type="info" effect="plain">{{ shipRequestMeta(row).warehouseName }}</el-tag>
                <el-text size="small" type="info">{{ shipRequestMeta(row).warehouseStatusLabel }}</el-text>
                <el-tag
                  v-if="shipRequestMeta(row).urgeCount"
                  type="warning"
                  size="small"
                  effect="plain"
                >
                  催 {{ shipRequestMeta(row).urgeCount }}
                </el-tag>
              </div>
              <el-tooltip
                v-if="shipRequestMeta(row).hasFeedback"
                :content="shipRequestMeta(row).feedbackDetail"
                placement="top"
                :show-after="300"
              >
                <el-text
                  size="small"
                  :type="row.warehouseStatus === 'blocked' ? 'danger' : 'success'"
                  class="warehouse-cell__feedback"
                >
                  {{ shipRequestMeta(row).feedbackSummary }}
                </el-text>
              </el-tooltip>
            </div>
          </template>
          <el-text v-else type="info" size="small">未推送</el-text>
        </template>
      </el-table-column>
      <el-table-column v-if="showShipActions" label="操作" width="168" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="canPushPlatformOrder(row, '1688')"
            link
            type="primary"
            size="small"
            @click="$emit('ship-push', row)"
          >
            推送发货
          </el-button>
          <el-button
            v-if="canUrgePlatformOrder(row)"
            link
            type="warning"
            size="small"
            @click="$emit('ship-urge', row)"
          >
            催促发货
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !filteredOrders.length" description="暂无采购订单" :image-size="72" />
  </div>
</template>

<style scoped>
.panel { display: grid; gap: 16px; }

.mini-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.mini-stat {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.mini-stat__value { font-size: 18px; font-weight: 700; }
.mini-stat__label { font-size: 13px; color: var(--el-text-color-secondary); }

.data-table { border-radius: 8px; }

.warehouse-cell {
  display: grid;
  gap: 4px;
}

.warehouse-cell__row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.warehouse-cell__feedback {
  display: block;
  line-height: 1.4;
}

@media (max-width: 768px) {
  .mini-stats { grid-template-columns: 1fr; }
}
</style>
