<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  APPEAL_STATUS_OPTIONS,
  APPEAL_STATUS_TYPE,
  APPEAL_RESULT_OPTIONS,
  APPEAL_RESULT_TYPE,
} from '@/constants/aliexpressDemo'
import { summarizeAliExpressViolations } from '@/utils/aliexpress'
import { formatMoneyDecimal } from '@/utils/format'
import AliExpressPanelHeader from '@/components/aliexpress/AliExpressPanelHeader.vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  violations: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
  initialFilter: { type: String, default: 'all' },
})

const emit = defineEmits(['refresh', 'confirm', 'open-history'])

const filterStatus = ref(props.initialFilter)
const confirming = ref(false)
const dialogVisible = ref(false)
const activeRow = ref(null)
const form = reactive({
  appealStatus: '',
  appealResult: 'pending',
  appealNote: '',
})

const summary = computed(() => summarizeAliExpressViolations(props.violations))

const filterOptions = computed(() => [
  { label: '全部', value: 'all' },
  {
    label: summary.value.pending ? `待确认 (${summary.value.pending})` : '待确认',
    value: 'pending',
  },
  { label: '未申诉', value: 'not_appealed' },
  {
    label: summary.value.appealPending ? `申诉中 (${summary.value.appealPending})` : '申诉中',
    value: 'result_pending',
  },
  { label: '申诉成功', value: 'result_success' },
  { label: '申诉不成功', value: 'result_failed' },
])

const filteredViolations = computed(() => {
  const map = {
    pending: (item) => !item.confirmed,
    not_appealed: (item) => item.appealStatus === 'not_appealed',
    result_pending: (item) => item.appealResult === 'pending',
    result_success: (item) => item.appealResult === 'success',
    result_failed: (item) => item.appealResult === 'failed',
  }
  const fn = map[filterStatus.value]
  return fn ? props.violations.filter(fn) : props.violations
})

function appealLabel(status) {
  return APPEAL_STATUS_OPTIONS.find((item) => item.value === status)?.label || '—'
}

function appealResultLabel(result) {
  return APPEAL_RESULT_OPTIONS.find((item) => item.value === result)?.label || '—'
}

function appealStatusText(row) {
  if (!row.confirmed) return '待确认'
  if (row.appealStatus === 'not_appealed') return '未申诉'
  if (row.appealResult) return appealResultLabel(row.appealResult)
  return appealLabel(row.appealStatus)
}

function appealStatusType(row) {
  if (!row.confirmed) return 'warning'
  if (row.appealStatus === 'not_appealed') return 'info'
  if (row.appealResult) return APPEAL_RESULT_TYPE[row.appealResult] || 'info'
  return APPEAL_STATUS_TYPE[row.appealStatus] || 'info'
}

function openConfirm(row) {
  activeRow.value = row
  form.appealStatus = row.appealStatus || ''
  form.appealResult = row.appealResult || 'pending'
  form.appealNote = row.appealNote || ''
  dialogVisible.value = true
}

function onAppealStatusChange() {
  if (form.appealStatus === 'appealed') {
    form.appealResult = form.appealResult || 'pending'
  } else {
    form.appealResult = ''
  }
}

async function submitConfirm() {
  if (!form.appealStatus) {
    ElMessage.warning('请选择是否已申诉')
    return
  }

  confirming.value = true
  emit('confirm', {
    id: activeRow.value.id,
    appealStatus: form.appealStatus,
    appealResult: form.appealStatus === 'appealed' ? form.appealResult || 'pending' : null,
    appealNote: form.appealNote,
  })
}

function finishConfirm() {
  confirming.value = false
  dialogVisible.value = false
  activeRow.value = null
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

defineExpose({ finishConfirm, setFilter })
</script>

<template>
  <div class="ae-panel">
    <AliExpressPanelHeader
      title="违规处理"
      description="确认申诉状态，平台审核结果通过抓取同步"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      action-label="抓取违规信息"
      :loading="loading"
      @action="$emit('refresh')"
      @open-history="$emit('open-history')"
    />

    <div class="mini-stats">
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.total }}</span>
        <span class="mini-stat__label">违规记录</span>
      </div>
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.pending }}</span>
        <span class="mini-stat__label">待确认</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.totalFineText }}</span>
        <span class="mini-stat__label">累计罚款</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.appealPending }}</span>
        <span class="mini-stat__label">申诉中</span>
      </div>
    </div>

    <el-segmented v-model="filterStatus" :options="filterOptions" />

    <el-table :data="filteredViolations" stripe size="small" v-loading="loading" class="ae-table">
      <el-table-column prop="typeLabel" label="违规类型" width="110" fixed />
      <el-table-column
        v-if="showStoreColumn"
        label="店铺"
        min-width="130"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ storeNameMap[row.storeId] || '—' }}</template>
      </el-table-column>
      <el-table-column prop="orderNo" label="关联订单" min-width="140" />
      <AssigneeTableColumn />
      <el-table-column prop="description" label="违规说明" min-width="220" show-overflow-tooltip />
      <el-table-column label="罚款" width="100" align="right">
        <template #default="{ row }">
          <el-text type="danger">{{ formatMoneyDecimal(row.fineAmount) }} {{ row.currency }}</el-text>
        </template>
      </el-table-column>
      <el-table-column prop="violatedAt" label="违规时间" width="160" />
      <el-table-column label="申诉状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="appealStatusType(row)" size="small">
            {{ appealStatusText(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <template v-if="row.confirmed">
            <el-text size="small">{{ row.appealNote || '—' }}</el-text>
            <el-text size="small" type="info" tag="p" class="confirm-meta">
              {{ row.confirmedBy }} · {{ row.confirmedAt }}
            </el-text>
          </template>
          <el-text v-else size="small" type="info">—</el-text>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.confirmed" type="primary" link size="small" @click="openConfirm(row)">
            确认
          </el-button>
          <el-text v-else size="small" type="info">已处理</el-text>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!loading && !filteredViolations.length"
      description="违规接口已对接卖家后台，当前 90 天内无处罚记录"
      :image-size="72"
    />

    <el-dialog
      v-model="dialogVisible"
      title="确认申诉状态"
      width="480px"
      destroy-on-close
      @closed="activeRow = null"
    >
      <template v-if="activeRow">
        <div class="dialog-summary">
          <div><strong>{{ activeRow.typeLabel }}</strong> · {{ activeRow.orderNo }}</div>
          <el-text size="small" type="info">{{ activeRow.description }}</el-text>
        </div>

        <el-form label-width="88px" class="confirm-form">
          <el-form-item label="是否申诉" required>
            <el-radio-group v-model="form.appealStatus" @change="onAppealStatusChange">
              <el-radio
                v-for="item in APPEAL_STATUS_OPTIONS"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="form.appealStatus === 'appealed'" label="当前结果">
            <el-radio-group v-model="form.appealResult">
              <el-radio
                v-for="item in APPEAL_RESULT_OPTIONS"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio>
            </el-radio-group>
            <el-text size="small" type="info" tag="p">
              平台审核结果会在后续抓取中自动更新
            </el-text>
          </el-form-item>

          <el-form-item label="备注">
            <el-input
              v-model="form.appealNote"
              type="textarea"
              :rows="2"
              placeholder="选填，如申诉单号或说明"
            />
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="confirming" @click="submitConfirm">确认提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ae-panel {
  display: grid;
  gap: 16px;
}

.mini-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.mini-stat {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.mini-stat.is-danger .mini-stat__value {
  color: var(--el-color-danger);
}

.mini-stat__value {
  font-size: 18px;
  font-weight: 700;
}

.mini-stat__label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.ae-table {
  border-radius: 8px;
}

.confirm-meta {
  margin-top: 4px;
}

.dialog-summary {
  display: grid;
  gap: 6px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.confirm-form {
  margin-top: 8px;
}

@media (max-width: 768px) {
  .mini-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
