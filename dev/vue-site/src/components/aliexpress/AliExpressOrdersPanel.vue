<script setup>
import { computed, ref } from 'vue'
import {
  JIT_STATUS_TYPE,
  WAREHOUSE_STATUS_TYPE,
} from '@/constants/aliexpressDemo'
import { summarizeAliExpressOrders } from '@/utils/aliexpress'
import { formatMoneyDecimal } from '@/utils/format'
import AliExpressPanelHeader from '@/components/aliexpress/AliExpressPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  orders: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

defineEmits(['refresh', 'open-history'])

const orderType = ref('jit')

const summary = computed(() => summarizeAliExpressOrders(props.orders))

const jitOrders = computed(() => props.orders.filter((order) => order.fulfillmentType === 'jit'))
const warehouseOrders = computed(() =>
  props.orders.filter((order) => order.fulfillmentType === 'warehouse'),
)

const currentOrders = computed(() =>
  orderType.value === 'jit' ? jitOrders.value : warehouseOrders.value,
)

function formatOrderAmount(row) {
  const amount = Number(row?.amount)
  if (!Number.isFinite(amount) || amount <= 0) return '—'
  return `${formatMoneyDecimal(amount)} ${row.currency || ''}`.trim()
}

function statusType(order) {
  if (order.fulfillmentType === 'jit') {
    return JIT_STATUS_TYPE[order.status] || 'info'
  }
  return WAREHOUSE_STATUS_TYPE[order.status] || 'info'
}
</script>

<template>
  <div class="ae-panel">
    <AliExpressPanelHeader
      title="今日订单"
      description="JIT 与仓发订单，按履约类型分开展示"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      action-label="抓取今日订单"
      :loading="loading"
      @action="$emit('refresh')"
      @open-history="$emit('open-history')"
    />

    <div class="mini-stats">
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.jitTotal }}</span>
        <span class="mini-stat__label">JIT 订单</span>
        <el-tag v-if="summary.jitPending" type="warning" size="small" effect="plain">
          {{ summary.jitPending }} 待处理
        </el-tag>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.warehouseTotal }}</span>
        <span class="mini-stat__label">仓发订单</span>
        <el-tag v-if="summary.warehousePending" type="warning" size="small" effect="plain">
          {{ summary.warehousePending }} 待出库
        </el-tag>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.totalAmountText }}</span>
        <span class="mini-stat__label">当日金额</span>
      </div>
    </div>

    <el-segmented v-model="orderType" :options="[
      { label: `JIT (${summary.jitTotal})`, value: 'jit' },
      { label: `仓发 (${summary.warehouseTotal})`, value: 'warehouse' },
    ]" />

    <el-table :data="currentOrders" stripe size="small" v-loading="loading" class="ae-table">
      <el-table-column prop="orderNo" label="订单号" min-width="150" fixed />
      <el-table-column
        v-if="showStoreColumn"
        label="店铺"
        min-width="130"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <el-table-column prop="productName" label="商品" min-width="160" show-overflow-tooltip />
      <AssigneeTableColumn />
      <el-table-column prop="sku" label="SKU" width="100" />
      <el-table-column prop="quantity" label="数量" width="70" align="center" />
      <el-table-column label="金额" width="100" align="right">
        <template #default="{ row }">
          {{ formatOrderAmount(row) }}
        </template>
      </el-table-column>
      <el-table-column prop="country" label="目的国" width="90" />
      <el-table-column v-if="orderType === 'warehouse'" prop="warehouseName" label="发货仓" width="100" />
      <el-table-column v-if="orderType === 'jit'" prop="shipDeadline" label="发货截止" width="160" />
      <el-table-column prop="orderedAt" label="下单时间" width="160" />
      <el-table-column label="状态" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-tag :type="statusType(row)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!loading && !currentOrders.length"
      :description="orderType === 'jit' ? '今日暂无 JIT 订单' : '今日暂无仓发订单'"
      :image-size="72"
    />
  </div>
</template>

<style scoped>
.ae-panel {
  display: grid;
  gap: 16px;
}

.mini-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.mini-stat {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.mini-stat__value {
  font-size: 18px;
  font-weight: 700;
}

.mini-stat__label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.ae-table {
  border-radius: 8px;
}

@media (max-width: 768px) {
  .mini-stats {
    grid-template-columns: 1fr;
  }
}
</style>
