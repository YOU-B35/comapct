<script setup>
import { computed, ref } from 'vue'
import { summarizeCases } from '@/utils/amazon'
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

    <div class="mini-stats">
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.newReplies }}</span>
        <span class="mini-stat__label">新回复未读</span>
      </div>
      <div class="mini-stat is-warning">
        <span class="mini-stat__value">{{ summary.pendingReply }}</span>
        <span class="mini-stat__label">待我方回复</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.open }}</span>
        <span class="mini-stat__label">进行中</span>
      </div>
    </div>

    <el-segmented v-model="filter" :options="[
      { label: summary.newReplies ? `新回复 (${summary.newReplies})` : '新回复', value: 'new' },
      { label: '待回复', value: 'pending' },
      { label: '全部', value: 'all' },
    ]" />

    <el-table :data="filtered" stripe size="small" v-loading="loading">
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
