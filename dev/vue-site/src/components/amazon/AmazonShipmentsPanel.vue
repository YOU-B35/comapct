<script setup>
import { computed, ref } from 'vue'
import { SHIPMENT_STATUS } from '@/constants/amazonDaily'
import { summarizeShipments } from '@/utils/amazon'
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

    <div class="mini-stats">
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.shortage }}</span>
        <span class="mini-stat__label">缺件</span>
      </div>
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.closedNoStock }}</span>
        <span class="mini-stat__label">完成无货</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.inTransit }}</span>
        <span class="mini-stat__label">运输中</span>
      </div>
    </div>

    <el-segmented v-model="filter" :options="[
      { label: summary.alerts ? `预警 (${summary.alerts})` : '预警', value: 'alert' },
      { label: '运输中', value: 'in_transit' },
      { label: '全部', value: 'all' },
    ]" />

    <el-table :data="filtered" stripe size="small" v-loading="loading">
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
  </div>
</template>

<style scoped>
.amz-panel { display: grid; gap: 16px; }
.mini-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.mini-stat {
  display: grid; gap: 4px; padding: 12px 14px;
  border-radius: 8px; background: var(--el-fill-color-lighter);
}
.mini-stat.is-danger .mini-stat__value { color: var(--el-color-danger); }
.mini-stat__value { font-size: 18px; font-weight: 700; }
.mini-stat__label { font-size: 13px; color: var(--el-text-color-secondary); }
</style>
