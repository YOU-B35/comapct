<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, ref } from 'vue'
import { COUPON_STATUS } from '@/constants/amazonDaily'
import { summarizeCoupons } from '@/utils/amazon'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  coupons: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['refresh', 'open-history'])

const filter = ref('alert')
const summary = computed(() => summarizeCoupons(props.coupons))

const filtered = computed(() => {
  if (filter.value === 'alert') {
    return props.coupons.filter((c) => ['expiring', 'expired', 'abnormal'].includes(c.status))
  }
  if (filter.value === 'all') return props.coupons
  return props.coupons.filter((c) => c.status === filter.value)
})

const { page, pageSize, total, paged } = useFuzzySearchPagination(filtered, {
  pageSize: 15,
  fields: [],
})

function statusMeta(row) {
  return COUPON_STATUS[row.status] || COUPON_STATUS.active
}
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="优惠券监控"
      description="检查优惠券是否异常；过期或配置错误需及时下架或续期"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      action-label="刷新今日数据"
      :loading="loading"
      @action="emit('refresh')"
      @open-history="$emit('open-history')"
    />

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="alert">{{ summary.alerts ? `待关注 (${summary.alerts})` : '待关注' }}</el-radio-button>
        <el-radio-button value="active">生效中</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="paged" stripe size="small" v-loading="loading" class="amazon-list">
      <el-table-column prop="name" label="优惠券" min-width="160" show-overflow-tooltip />
      <el-table-column
        v-if="showStoreColumn"
        label="店铺"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <AssigneeTableColumn />
      <el-table-column prop="discount" label="力度" width="80" />
      <el-table-column label="有效期" min-width="180">
        <template #default="{ row }">{{ formatUtc8(row.startAt) }} ~ {{ formatUtc8(row.endAt) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row).type" size="small">{{ statusMeta(row).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="核销/预算" width="110" align="center">
        <template #default="{ row }">{{ row.redemptions }} / {{ row.budget }}</template>
      </el-table-column>
      <el-table-column prop="note" label="备注" min-width="180" show-overflow-tooltip />
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
