<script setup>
import { computed, ref } from 'vue'
import { summarizeReviews } from '@/utils/amazon'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  reviews: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['handle', 'open-history'])

const filter = ref('pending')
const handleNote = ref('')
const dialogVisible = ref(false)
const activeRow = ref(null)
const handling = ref(false)

const summary = computed(() => summarizeReviews(props.reviews))

const filtered = computed(() => {
  if (filter.value === 'all') return props.reviews
  if (filter.value === 'pending') {
    return props.reviews.filter((r) => r.status === 'pending' || r.status === 'pending_write')
  }
  return props.reviews.filter((r) => r.status === filter.value)
})

const { page, pageSize, total, paged } = useFuzzySearchPagination(filtered, {
  pageSize: 15,
  fields: [],
})

function starType(rating) {
  if (rating <= 1) return 'danger'
  if (rating <= 2) return 'warning'
  return 'info'
}

function openHandle(row) {
  activeRow.value = row
  handleNote.value = ''
  dialogVisible.value = true
}

function submitHandle() {
  handling.value = true
  emit('handle', { id: activeRow.value.id, note: handleNote.value })
}

function finishHandle() {
  handling.value = false
  dialogVisible.value = false
  activeRow.value = null
}

defineExpose({ finishHandle })
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="差评预警"
      description="1-3 星评价需及时联系买家或申诉，降低 ODR 与账户风险"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      @open-history="$emit('open-history')"
    />

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="pending">{{ summary.pending ? `待处理 (${summary.pending})` : '待处理' }}</el-radio-button>
        <el-radio-button value="handled">已处理</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="paged" stripe size="small" v-loading="loading" class="amazon-list">
      <el-table-column label="星级" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="starType(row.rating)" size="small">{{ row.rating }} 星</el-tag>
        </template>
      </el-table-column>
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
      <el-table-column prop="content" label="评价内容" min-width="200" show-overflow-tooltip />
      <el-table-column prop="reviewedAt" label="评价时间" width="155" />
      <el-table-column label="操作" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" type="primary" link size="small" @click="openHandle(row)">
            标记处理
          </el-button>
          <el-tag v-else-if="row.status === 'pending_write'" size="small" type="warning">写回中</el-tag>
          <el-text v-else size="small" type="success">已处理</el-text>
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

    <el-dialog v-model="dialogVisible" title="标记差评已处理" width="440px" destroy-on-close>
      <el-form v-if="activeRow" label-width="80px">
        <el-form-item label="商品">{{ activeRow.productName }}</el-form-item>
        <el-form-item label="备注">
          <el-input v-model="handleNote" type="textarea" :rows="2" placeholder="如：已联系买家、已申诉" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="handling" @click="submitHandle">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.amz-panel { display: grid; gap: 16px; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 8px; }
.amazon-list :deep(.el-table__cell .cell) { font-size: 12px; line-height: 1.4; }
.amazon-list :deep(.el-table__cell) { padding: 5px 0; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 10px; }
</style>
