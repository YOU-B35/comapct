<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, ref, watch } from 'vue'
import { summarizeDomesticIssues } from '@/utils/domesticPlatform'
import DomesticPanelHeader from '@/components/domestic/DomesticPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  issues: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
  initialFilter: { type: String, default: 'all' },
  issuesTitle: { type: String, default: '运营预警' },
  issuesDescription: { type: String, default: '商品、活动与内容相关待跟进事项' },
  /** 为 false 时不展示大标题区，仅保留同步时间 + 操作 */
  showHeader: { type: Boolean, default: true },
})

const emit = defineEmits(['refresh', 'resolve'])

const filterStatus = ref(props.initialFilter)
const resolving = ref(false)

const summary = computed(() => summarizeDomesticIssues(props.issues))

const filterOptions = computed(() => [
  { label: '全部', value: 'all' },
  {
    label: summary.value.open ? `待处理 (${summary.value.open})` : '待处理',
    value: 'open',
  },
  {
    label: summary.value.high ? `高优先级 (${summary.value.high})` : '高优先级',
    value: 'high',
  },
  { label: '已解决', value: 'resolved' },
])

const filteredIssues = computed(() => {
  const map = {
    open: (item) => !item.resolved,
    high: (item) => !item.resolved && item.severity === 'high',
    resolved: (item) => item.resolved,
  }
  const fn = map[filterStatus.value]
  return fn ? props.issues.filter(fn) : props.issues
})

const { keyword, page, pageSize, total, paged } = useFuzzySearchPagination(filteredIssues, {
  pageSize: 10,
  fields: ['sku', 'productName', 'detail', 'typeLabel'],
})

function severityType(severity) {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'info'
}

function severityLabel(severity) {
  if (severity === 'high') return '高'
  if (severity === 'medium') return '中'
  return '低'
}

function handleResolve(row) {
  resolving.value = true
  emit('resolve', { id: row.id })
}

function finishResolve() {
  resolving.value = false
}

function setFilter(value) {
  filterStatus.value = value
}

watch(
  () => props.initialFilter,
  (value) => {
    if (value) filterStatus.value = value
  },
)

defineExpose({ finishResolve, setFilter })
</script>

<template>
  <div class="domestic-panel">
    <DomesticPanelHeader
      v-if="showHeader"
      :title="issuesTitle"
      :description="issuesDescription"
      :synced-at="syncedAt"
      action-label="刷新预警"
      :loading="loading"
      @action="$emit('refresh')"
    />
    <div v-else class="domestic-panel__toolbar">
      <div class="domestic-panel__toolbar-filters">
        <el-radio-group v-model="filterStatus" size="small">
          <el-radio-button
            v-for="opt in filterOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
        <el-input
          v-model="keyword"
          clearable
          size="small"
          placeholder="搜索 SKU / 商品 / 说明"
          class="domestic-panel__toolbar-search"
        />
      </div>
      <div class="domestic-panel__toolbar-actions">
        <el-button type="primary" size="small" :loading="loading" @click="$emit('refresh')">
          刷新预警
        </el-button>
        <el-text v-if="syncedAt" size="small" type="info" class="domestic-panel__toolbar-meta">
          同步 {{ formatUtc8(syncedAt) }}
        </el-text>
      </div>
    </div>

    <div v-if="showHeader" class="domestic-panel__header-filters">
      <el-radio-group
        v-model="filterStatus"
        size="small"
        class="domestic-panel__filters"
      >
        <el-radio-button
          v-for="opt in filterOptions"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
      <el-input
        v-model="keyword"
        clearable
        size="small"
        placeholder="搜索 SKU / 商品 / 说明"
        class="domestic-panel__toolbar-search"
      />
    </div>
    <TableQueryBar
      v-model:keyword="keyword"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      placeholder="搜索 SKU / 商品 / 说明"
      :show-sizes="false"
      :show-search="false"
    >
      <el-table :data="paged" size="small" stripe v-loading="loading">
        <el-table-column prop="typeLabel" label="类型" width="110" />
        <el-table-column v-if="showStoreColumn" label="店铺" width="130">
          <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
        </el-table-column>
        <AssigneeTableColumn width="90" />
        <el-table-column prop="sku" label="SKU" width="100" />
        <el-table-column label="商品" min-width="180">
          <template #default="{ row }">
            <div class="issue-product-cell">
              <el-image
                v-if="row.productImage || row.mainImage"
                :src="row.productImage || row.mainImage"
                fit="cover"
                class="product-thumb"
                :preview-src-list="[row.productImage || row.mainImage]"
                preview-teleported
              />
              <div class="issue-product-cell__meta">
                <div class="issue-product-cell__title" :title="row.productName || ''">
                  {{ row.productName || '—' }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="说明" min-width="180" show-overflow-tooltip />
        <el-table-column label="优先级" width="72" align="center">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.resolved"
              link
              type="primary"
              size="small"
              :loading="resolving"
              @click="handleResolve(row)"
            >
              标记解决
            </el-button>
            <el-tag v-else type="success" size="small">已解决</el-tag>
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

.domestic-panel__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px 16px;
}

.domestic-panel__toolbar-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.domestic-panel__toolbar-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.domestic-panel__toolbar-meta {
  text-align: right;
  line-height: 1.3;
}

.domestic-panel__filters {
  margin-bottom: 0;
}

.domestic-panel__header-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
}

.domestic-panel__toolbar-search {
  width: min(220px, 100%);
}

.issue-product-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.product-thumb {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  flex-shrink: 0;
}

.issue-product-cell__meta {
  min-width: 0;
  flex: 1;
}

.issue-product-cell__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  line-height: 1.4;
}
</style>
