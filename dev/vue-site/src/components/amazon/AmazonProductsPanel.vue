<script setup>
import { computed, ref, watch } from 'vue'
import { summarizeTopProducts, acosMeta, formatAmazonMoney, formatAmazonPercent } from '@/utils/amazonBoss'
import { resolveAmazonProductEmptyHint } from '@/utils/amazonProductHint'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  products: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  syncIssue: { type: Object, default: null },
  dataQuality: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  reportsLoading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
  initialFilter: { type: String, default: 'all' },
})

defineEmits(['refresh', 'refreshReports', 'open-history'])

const dataQualityAlert = computed(() => {
  const q = props.dataQuality
  if (!q?.warnings?.length) return null
  const labels = {
    BR_EMPTY: 'Business Report CSV 未采到销售额数据',
    INV_CSV_EMPTY: '库存 CSV 未采到可售数量',
    ADS_CSV_EMPTY: '广告 ASIN 报表 CSV 未采到花费/ACOS',
  }
  const text = q.warnings.map((w) => labels[w] || w).join('；')
  return { type: 'warning', title: '部分数据源同步不完整', description: text }
})

const filter = ref(props.initialFilter)

const summary = computed(() => summarizeTopProducts(props.products, 20))

const emptyHint = computed(() => {
  if (summary.value.top.length || props.loading) return null
  if (props.syncIssue) return props.syncIssue
  return resolveAmazonProductEmptyHint({ syncedAt: props.syncedAt })
})

const filterOptions = computed(() => [
  { label: 'TOP20 全部', value: 'all' },
  {
    label: summary.value.highAcosCount
      ? `ACOS 偏高 (${summary.value.highAcosCount})`
      : 'ACOS 偏高',
    value: 'high-acos',
  },
  {
    label: summary.value.dangerAcosCount
      ? `ACOS 过高 (${summary.value.dangerAcosCount})`
      : 'ACOS 过高',
    value: 'danger-acos',
  },
])

const filteredProducts = computed(() => {
  let list = summary.value.top
  if (filter.value === 'high-acos') {
    list = list.filter((p) => ['warning', 'danger'].includes(acosMeta(p.acos).level))
  } else if (filter.value === 'danger-acos') {
    list = list.filter((p) => acosMeta(p.acos).level === 'danger')
  }
  return list
})

const { page, pageSize, total, paged } = useFuzzySearchPagination(filteredProducts, {
  pageSize: 15,
  fields: [],
})

function formatOptionalPercent(value) {
  const num = Number(value)
  if (!Number.isFinite(num) || num <= 0) return '—'
  return `${num}%`
}

function formatOptionalCount(value) {
  const num = Number(value)
  if (!Number.isFinite(num) || num <= 0) return '—'
  return String(num)
}

watch(
  () => props.initialFilter,
  (value) => {
    if (value === 'products:high-acos') filter.value = 'high-acos'
    else if (value) filter.value = value.replace('products:', '') || 'all'
  },
)
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      :title="`产品 TOP20${summary.total ? ` · 共 ${summary.total} SKU` : ''}`"
      description="按近 7 日销售额排序展示 TOP20，关注 ACOS、转化与 FBA 库存；完整 SKU 数以标题为准"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      secondary-action-label="Business Report 刷新"
      action-label="刷新数据"
      :secondary-loading="reportsLoading"
      :loading="loading"
      @secondary-action="$emit('refreshReports')"
      @action="$emit('refresh')"
      @open-history="$emit('open-history')"
    />

    <el-alert
      v-if="dataQualityAlert"
      :type="dataQualityAlert.type"
      :closable="false"
      show-icon
      :title="dataQualityAlert.title"
      :description="dataQualityAlert.description"
      style="margin-bottom: 4px"
    />

    <el-alert
      v-if="emptyHint"
      :type="emptyHint.type || 'warning'"
      :closable="false"
      show-icon
      :title="emptyHint.title"
      :description="emptyHint.description"
      style="margin-bottom: 4px"
    />

    <el-alert
      v-if="!summary.hasAdData && summary.top.length"
      type="info"
      :closable="false"
      show-icon
      title="SKU 级广告数据尚未同步"
      description="未从广告 ASIN 报表 CSV 采集到各 SKU 的广告花费。请点击「Business Report 刷新」重新同步（需紫鸟与同步助手在线）。"
      style="margin-bottom: 4px"
    />

    <el-alert
      v-if="summary.dangerAcosCount"
      type="error"
      :closable="false"
      show-icon
      title="部分 SKU 广告 ACOS 过高，建议下调竞价或优化关键词"
    />

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button v-for="opt in filterOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="paged" stripe size="small" v-loading="loading" class="product-table amazon-list">
      <el-table-column label="#" width="48" align="center" fixed="left">
        <template #default="{ row }">{{ row.displayRank }}</template>
      </el-table-column>
      <el-table-column prop="productName" label="商品" min-width="160" show-overflow-tooltip fixed="left" />
      <el-table-column v-if="showStoreColumn" label="店铺" width="130">
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <AssigneeTableColumn width="90" />
      <el-table-column prop="asin" label="ASIN" width="110" />
      <el-table-column label="7日订单" width="80" align="center">
        <template #default="{ row }">{{ row.orders7d }}</template>
      </el-table-column>
      <el-table-column label="7日销售额" width="128" align="right" class-name="money-col">
        <template #default="{ row }">
          <span class="money-cell">{{ formatAmazonMoney(row.revenue7d, row.currency) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="广告花费" width="118" align="right" class-name="money-col">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.adSpend7d <= 0"
            content="未从广告活动页采集到该 SKU 花费"
            placement="top"
          >
            <span class="money-cell">—</span>
          </el-tooltip>
          <span v-else class="money-cell">{{ formatAmazonMoney(row.adSpend7d, row.currency) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="ACOS" width="88" align="center" sortable :sort-method="(a, b) => a.acos - b.acos">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.acos <= 0"
            content="未从广告活动页采集到该 SKU ACOS"
            placement="top"
          >
            <span class="money-cell">—</span>
          </el-tooltip>
          <el-tag v-else :type="acosMeta(row.acos).type" size="small">
            {{ formatAmazonPercent(row.acos) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="TACoS" width="72" align="center">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.tacos <= 0"
            content="需 SKU 级广告花费与销售额方可计算"
            placement="top"
          >
            <span class="money-cell">—</span>
          </el-tooltip>
          <span v-else>{{ formatAmazonPercent(row.tacos) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="转化率" width="72" align="center">
        <template #default="{ row }">{{ formatOptionalPercent(row.conversionRate) }}</template>
      </el-table-column>
      <el-table-column label="会话" width="72" align="center">
        <template #default="{ row }">{{ formatOptionalCount(row.sessions7d) }}</template>
      </el-table-column>
      <el-table-column label="FBA库存" width="80" align="center">
        <template #default="{ row }">{{ formatOptionalCount(row.unitsOnHand) }}</template>
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

.money-cell {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum';
}

.product-table :deep(.money-col .cell) {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum';
  white-space: nowrap;
}

.product-table {
  width: 100%;
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
