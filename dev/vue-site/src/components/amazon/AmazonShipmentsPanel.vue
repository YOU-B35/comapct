<script setup>
import { computed, ref } from 'vue'
import { SHIPMENT_STATUS } from '@/constants/amazonDaily'
import { summarizeShipments } from '@/utils/amazon'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  shipments: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['refresh', 'open-history'])

const filter = ref('alert')
const summary = computed(() => summarizeShipments(props.shipments))

const filtered = computed(() => {
  if (filter.value === 'alert') {
    return props.shipments.filter(
      (s) => s.alertLevel === 'danger' || ['shortage', 'closed_no_stock'].includes(s.status),
    )
  }
  if (filter.value === 'all') return props.shipments
  return props.shipments.filter((s) => s.status === filter.value)
})

const { page, pageSize, total, paged } = useFuzzySearchPagination(filtered, {
  pageSize: 15,
  fields: [],
})

function statusMeta(row) {
  return SHIPMENT_STATUS[row.status] || SHIPMENT_STATUS.in_transit
}
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="货件到货"
      description="跟踪 FBA 货件：送达、缺件、显示完成但无库存等情况均需预警"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      action-label="刷新今日数据"
      :loading="loading"
      @action="emit('refresh')"
      @open-history="$emit('open-history')"
    />

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="alert">{{ summary.alerts ? `预警 (${summary.alerts})` : '预警' }}</el-radio-button>
        <el-radio-button value="in_transit">运输中</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="paged" stripe size="small" v-loading="loading" class="amazon-list">
      <el-table-column prop="shipmentId" label="货件号" min-width="130" />
      <el-table-column
        v-if="showStoreColumn"
        label="店铺"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <el-table-column prop="productName" label="商品" min-width="140" show-overflow-tooltip />
      <AssigneeTableColumn />
      <el-table-column label="实收/预期" width="110" align="center">
        <template #default="{ row }">
          <el-text :type="row.unitsReceived < row.unitsExpected ? 'danger' : undefined">
            {{ row.unitsReceived }} / {{ row.unitsExpected }}
          </el-text>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row).type" size="small">{{ statusMeta(row).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="eta" label="预计到达" width="110" />
      <el-table-column prop="note" label="说明" min-width="200" show-overflow-tooltip />
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
  </div>
</template>

<style scoped>
.amz-panel { display: grid; gap: 16px; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 8px; }
.amazon-list :deep(.el-table__cell .cell) { font-size: 12px; line-height: 1.4; }
.amazon-list :deep(.el-table__cell) { padding: 5px 0; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 10px; }
</style>
