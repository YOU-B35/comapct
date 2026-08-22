<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, ref } from 'vue'
import { COUPON_STATUS } from '@/constants/amazonDaily'
import { summarizeCoupons } from '@/utils/amazon'
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

    <div class="mini-stats">
      <div class="mini-stat is-warning">
        <span class="mini-stat__value">{{ summary.expiring }}</span>
        <span class="mini-stat__label">即将过期</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.expired }}</span>
        <span class="mini-stat__label">已过期</span>
      </div>
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.abnormal }}</span>
        <span class="mini-stat__label">配置异常</span>
      </div>
    </div>

    <el-segmented v-model="filter" :options="[
      { label: summary.alerts ? `待关注 (${summary.alerts})` : '待关注', value: 'alert' },
      { label: '生效中', value: 'active' },
      { label: '全部', value: 'all' },
    ]" />

    <el-table :data="filtered" stripe size="small" v-loading="loading">
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
.mini-stat.is-warning .mini-stat__value { color: var(--el-color-warning); }
.mini-stat__value { font-size: 18px; font-weight: 700; }
.mini-stat__label { font-size: 13px; color: var(--el-text-color-secondary); }
</style>
