<script setup>
import { computed, ref } from 'vue'
import { summarizeCases } from '@/utils/amazon'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  cases: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['acknowledge', 'open-history'])

const filter = ref('new')
const acknowledgingId = ref('')
const summary = computed(() => summarizeCases(props.cases))

const filtered = computed(() => {
  if (filter.value === 'new') {
    return props.cases.filter((c) => c.hasNewReply && !c.read)
  }
  if (filter.value === 'pending') {
    return props.cases.filter((c) => c.status === 'pending_reply')
  }
  return props.cases
})

const { page, pageSize, total, paged } = useFuzzySearchPagination(filtered, {
  pageSize: 15,
  fields: [],
})

function replyFromLabel(from) {
  return from === 'amazon' ? 'Amazon 回复' : '我方回复'
}

function replyFromType(from) {
  return from === 'amazon' ? 'danger' : 'info'
}

function handleAcknowledge(id) {
  acknowledgingId.value = id
  emit('acknowledge', id)
}

function finishAcknowledge() {
  acknowledgingId.value = ''
}

defineExpose({ finishAcknowledge })
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="Case 跟进"
      description="平台 Case 有新回复时单独提醒，避免遗漏影响索赔或申诉"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      @open-history="$emit('open-history')"
    />

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="new">{{ summary.newReplies ? `新回复 (${summary.newReplies})` : '新回复' }}</el-radio-button>
        <el-radio-button value="pending">待回复</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="paged" stripe size="small" v-loading="loading" class="amazon-list">
      <el-table-column prop="caseId" label="Case ID" width="130" />
      <el-table-column
        v-if="showStoreColumn"
        label="店铺"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <el-table-column prop="subject" label="主题" min-width="180" show-overflow-tooltip />
      <AssigneeTableColumn />
      <el-table-column prop="preview" label="最新内容" min-width="200" show-overflow-tooltip />
      <el-table-column label="最新回复" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="replyFromType(row.lastReplyFrom)" size="small">
            {{ replyFromLabel(row.lastReplyFrom) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="lastReplyAt" label="回复时间" width="155" />
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.hasNewReply && !row.read && row.status !== 'pending_write'"
            type="primary"
            link
            size="small"
            :loading="acknowledgingId === row.id"
            @click="handleAcknowledge(row.id)"
          >
            标记已读
          </el-button>
          <el-tag v-else-if="row.status === 'pending_write'" size="small" type="warning">写回中</el-tag>
          <el-text v-else size="small" type="info">已读</el-text>
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
  </div>
</template>

<style scoped>
.amz-panel { display: grid; gap: 16px; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 8px; }
.amazon-list :deep(.el-table__cell .cell) { font-size: 12px; line-height: 1.4; }
.amazon-list :deep(.el-table__cell) { padding: 5px 0; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 10px; }
</style>
