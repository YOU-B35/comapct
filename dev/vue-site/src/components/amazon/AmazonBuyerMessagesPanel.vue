<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MESSAGE_REPLY_TEMPLATES } from '@/constants/amazonDaily'
import { summarizeBuyerMessages } from '@/utils/amazon'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['reply', 'open-history'])

const filter = ref('pending')
const dialogVisible = ref(false)
const activeRow = ref(null)
const selectedTemplate = ref('')
const replyNote = ref('')
const replying = ref(false)

const summary = computed(() => summarizeBuyerMessages(props.messages))

const filterOptions = computed(() => [
  { label: summary.value.pending ? `待回复 (${summary.value.pending})` : '待回复', value: 'pending' },
  { label: '已回复', value: 'replied' },
  { label: '全部', value: 'all' },
])

const filtered = computed(() => {
  if (filter.value === 'all') return props.messages
  if (filter.value === 'pending') {
    return props.messages.filter((m) => m.status === 'pending' || m.status === 'pending_write')
  }
  return props.messages.filter((m) => m.status === filter.value)
})

function slaType(row) {
  if (row.status === 'replied') return 'success'
  const received = new Date(row.receivedAt.replace(' ', 'T')).getTime()
  const hours = (Date.now() - received) / 3600000
  if (hours >= (row.slaHours || 24)) return 'danger'
  if (hours >= (row.slaHours || 24) * 0.75) return 'warning'
  return 'info'
}

function slaLabel(row) {
  if (row.status === 'replied') return '已回复'
  const received = new Date(row.receivedAt.replace(' ', 'T')).getTime()
  const hours = (Date.now() - received) / 3600000
  const remain = Math.max(0, (row.slaHours || 24) - hours)
  if (remain <= 0) return '已超时'
  return `剩余 ${Math.ceil(remain)}h`
}

function openReply(row) {
  activeRow.value = row
  selectedTemplate.value = MESSAGE_REPLY_TEMPLATES[0]?.id || ''
  replyNote.value = ''
  dialogVisible.value = true
}

function templateBody(id) {
  return MESSAGE_REPLY_TEMPLATES.find((t) => t.id === id)?.body || ''
}

function submitReply() {
  if (!selectedTemplate.value) {
    ElMessage.warning('请选择回复模板')
    return
  }
  replying.value = true
  emit('reply', {
    id: activeRow.value.id,
    templateId: selectedTemplate.value,
    note: replyNote.value,
  })
}

function finishReply() {
  replying.value = false
  dialogVisible.value = false
  activeRow.value = null
}

defineExpose({ finishReply })
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="买家消息"
      description="24 小时内回复，避免迟复扣绩效；可套用统一模板快速回复"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      @open-history="$emit('open-history')"
    />

    <div class="mini-stats">
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.pending }}</span>
        <span class="mini-stat__label">待回复</span>
      </div>
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.urgent }}</span>
        <span class="mini-stat__label">临近超时</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.replied }}</span>
        <span class="mini-stat__label">今日已回</span>
      </div>
    </div>

    <el-segmented v-model="filter" :options="filterOptions" />

    <el-table :data="filtered" stripe size="small" v-loading="loading">
      <el-table-column prop="buyerName" label="买家" width="100" />
      <el-table-column
        v-if="showStoreColumn"
        label="店铺"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <el-table-column prop="subject" label="主题" min-width="140" show-overflow-tooltip />
      <AssigneeTableColumn />
      <el-table-column prop="preview" label="内容摘要" min-width="200" show-overflow-tooltip />
      <el-table-column prop="receivedAt" label="收到时间" width="155" />
      <el-table-column label="回复时效" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="slaType(row)" size="small">{{ slaLabel(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" type="primary" link size="small" @click="openReply(row)">
            回复
          </el-button>
          <el-tag v-else-if="row.status === 'pending_write'" size="small" type="warning">写回中</el-tag>
          <el-text v-else size="small" type="success">已回复</el-text>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="套用模板回复" width="520px" destroy-on-close>
      <template v-if="activeRow">
        <div class="dialog-summary">
          <strong>{{ activeRow.buyerName }}</strong> · {{ activeRow.subject }}
          <el-text size="small" type="info" tag="p">{{ activeRow.preview }}</el-text>
        </div>
        <el-form label-width="80px">
          <el-form-item label="回复模板" required>
            <el-select v-model="selectedTemplate" style="width: 100%">
              <el-option
                v-for="tpl in MESSAGE_REPLY_TEMPLATES"
                :key="tpl.id"
                :label="tpl.title"
                :value="tpl.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="预览">
            <el-input :model-value="templateBody(selectedTemplate)" type="textarea" :rows="4" readonly />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="replyNote" placeholder="选填" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="replying" @click="submitReply">确认回复</el-button>
      </template>
    </el-dialog>
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
.dialog-summary {
  margin-bottom: 16px; padding: 12px 14px;
  border-radius: 8px; background: var(--el-fill-color-lighter);
}
</style>
