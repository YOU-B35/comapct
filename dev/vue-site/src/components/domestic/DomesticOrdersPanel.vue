<script setup>
import { computed } from 'vue'
import { DOMESTIC_ORDER_STATUS_TYPE } from '@/constants/domesticShared'
import { summarizeDomesticOrders } from '@/utils/domesticPlatform'
import { formatMoneyDecimal } from '@/utils/format'
import {
  canPushPlatformOrder,
  canUrgePlatformOrder,
  shipRequestMeta,
} from '@/utils/platformShipToWarehouse'
import DomesticPanelHeader from '@/components/domestic/DomesticPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  orders: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
  showChannelColumn: { type: Boolean, default: false },
  ordersDescription: { type: String, default: '今日待处理与已发货订单' },
  ordersTitle: { type: String, default: '今日订单' },
  actionLabel: { type: String, default: '抓取今日订单' },
  amountLabel: { type: String, default: '当日金额' },
  showShipActions: { type: Boolean, default: true },
})

defineEmits(['refresh', 'ship-push', 'ship-urge'])

const summary = computed(() => summarizeDomesticOrders(props.orders))

const { keyword, page, pageSize, total, paged } = useFuzzySearchPagination(
  () => props.orders,
  {
    pageSize: 10,
    fields: ['orderNo', 'productName', 'channel'],
  },
)

function statusType(order) {
  return DOMESTIC_ORDER_STATUS_TYPE[order.status] || 'info'
}
</script>

<template>
  <div class="domestic-panel">
    <DomesticPanelHeader
      :title="ordersTitle"
      :description="ordersDescription"
      :synced-at="syncedAt"
      :action-label="actionLabel"
      :loading="loading"
      @action="$emit('refresh')"
    />

    <div class="mini-stats">
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.total }}</span>
        <span class="mini-stat__label">全部订单</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.pending }}</span>
        <span class="mini-stat__label">待处理</span>
        <el-tag v-if="summary.pending" type="warning" size="small" effect="plain">
          需跟进
        </el-tag>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.totalAmountText }}</span>
        <span class="mini-stat__label">{{ amountLabel }}</span>
      </div>
    </div>

    <TableQueryBar
      v-model:keyword="keyword"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      placeholder="搜索订单号 / 商品 / 来源"
      :show-sizes="false"
    >
      <el-table :data="paged" size="small" stripe v-loading="loading">
        <el-table-column prop="orderNo" label="订单号" min-width="150" />
        <el-table-column v-if="showStoreColumn" label="店铺" width="130">
          <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
        </el-table-column>
        <AssigneeTableColumn width="90" />
        <el-table-column prop="productName" label="商品" min-width="150" show-overflow-tooltip />
        <el-table-column v-if="showChannelColumn" prop="channel" label="来源" width="80" />
        <el-table-column label="金额" width="100" align="right">
          <template #default="{ row }">{{ formatMoneyDecimal(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="shipDeadline" label="发货截止" width="150" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="showShipActions" label="仓库" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="shipRequestMeta(row)">
              <div class="warehouse-cell">
                <div class="warehouse-cell__row">
                  <el-tag size="small" type="info" effect="plain">
                    {{ shipRequestMeta(row).warehouseName }}
                  </el-tag>
                  <el-text size="small" type="info">
                    {{ shipRequestMeta(row).warehouseStatusLabel }}
                  </el-text>
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
                  <el-text size="small" :type="row.warehouseStatus === 'blocked' ? 'danger' : 'success'" class="warehouse-cell__feedback">
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
              v-if="canPushPlatformOrder(row)"
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
            <el-text
              v-if="!canPushPlatformOrder(row) && !canUrgePlatformOrder(row)"
              type="success"
              size="small"
            >
              {{ row.status === '已发货' ? '已发货' : '—' }}
            </el-text>
          </template>
        </el-table-column>
      </el-table>
    </TableQueryBar>
  </div>
</template>

<style scoped>
.domestic-panel {
  display: grid;
  gap: 16px;
}

.mini-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.mini-stat {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 12px 16px;
  background: var(--ch-bg-soft, var(--el-fill-color-light));
  border-radius: var(--ch-radius-md, 8px);
}

.mini-stat__value {
  font-size: 20px;
  font-weight: 600;
  color: var(--ch-text, var(--el-text-color-primary));
}

.mini-stat__label {
  font-size: 12px;
  color: var(--ch-text-muted, var(--el-text-color-secondary));
}

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
</style>
