<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { RESTOCK_CONFIG } from '@/constants/temu'
import { TEMU_RESTOCK_STATUS_LABELS } from '@/constants/temuOps'
import {
  loadTemuRestockStatusMap,
  resolveTemuRestockStatus,
  restockStatusKey,
  saveTemuRestockStatus,
} from '@/api/temuRestock'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  products: { type: Array, required: true },
  showStoreColumn: { type: Boolean, default: false },
  useBackendData: { type: Boolean, default: false },
})

const auth = useAuthStore()
const urgencyFilter = ref('all')
const restockStatusMap = ref({})
const savingKey = ref('')

const statusOptions = Object.entries(TEMU_RESTOCK_STATUS_LABELS).map(([value, meta]) => ({
  value,
  label: meta.label,
}))

const urgencyFiltered = computed(() => {
  let list = [...props.products].sort((a, b) => a.restock.coverDays - b.restock.coverDays)
  if (urgencyFilter.value === 'urgent') {
    list = list.filter((p) => p.restock.urgency === 'critical' || p.restock.urgency === 'warning')
  }
  if (urgencyFilter.value === 'hot') list = list.filter((p) => p.isHot)
  return list
})

const { keyword, page, pageSize, filtered, total, paged } = useFuzzySearchPagination(urgencyFiltered, {
  fields: ['sku', 'name', 'storeName'],
})

const totalSuggest = computed(() =>
  urgencyFiltered.value.reduce((s, p) => s + (Number(p.restock?.suggestedRestock) || 0), 0),
)

onMounted(async () => {
  restockStatusMap.value = await loadTemuRestockStatusMap(auth)
})

function urgencyTag(row) {
  const map = {
    critical: { type: 'danger', label: '紧急补货' },
    warning: { type: 'warning', label: '建议补货' },
    caution: { type: 'info', label: '低于安全线' },
    normal: { type: 'success', label: '正常' },
  }
  return map[row.restock.urgency] || map.normal
}

function trackedStatus(row) {
  return resolveTemuRestockStatus(restockStatusMap.value, row)?.status || 'pending'
}

function trackedNote(row) {
  const tracked = resolveTemuRestockStatus(restockStatusMap.value, row)
  if (tracked?.note) return tracked.note
  if (row.restock.suggestedRestock > 0) {
    return `建议补货 ${row.restock.suggestedRestock} 件`
  }
  return ''
}

function statusMeta(row) {
  const status = trackedStatus(row)
  return TEMU_RESTOCK_STATUS_LABELS[status] || TEMU_RESTOCK_STATUS_LABELS.pending
}

async function onStatusChange(row, status) {
  const key = restockStatusKey(row.storeId, row.sku)
  savingKey.value = key
  const note = trackedNote(row)
  try {
    await saveTemuRestockStatus(
      {
        shopId: row.storeId,
        sku: row.sku,
        status,
        note,
      },
      auth,
    )
    const entry = { status, note }
    restockStatusMap.value = {
      ...restockStatusMap.value,
      [key]: entry,
      [row.sku]: entry,
    }
    ElMessage.success('备货跟进状态已更新')
  } catch (err) {
    ElMessage.error(err.message || '更新失败')
  } finally {
    savingKey.value = ''
  }
}
</script>

<template>
  <div>
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="24">
        <el-alert type="info" show-icon :closable="false">
          <template #title>备货逻辑说明</template>
          <template #default>
            日均需求 = (近7日均×0.7 + 近30日均×0.3) × 趋势系数(0.8~1.5) ·
            告警阈值 = 提前期 {{ RESTOCK_CONFIG.leadTimeDays }} 天 + 缓冲 {{ RESTOCK_CONFIG.safetyBufferDays }} 天 ·
            覆盖天数低于阈值则需补货；目标库存 = 日均 × {{ RESTOCK_CONFIG.targetCoverDays }} 天
          </template>
        </el-alert>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <el-space wrap>
          <span>本地仓 → Temu 官方仓 备货计划</span>
          <el-radio-group v-model="urgencyFilter" size="small">
            <el-radio-button value="all">全部 SKU</el-radio-button>
            <el-radio-button value="urgent">需补货</el-radio-button>
            <el-radio-button value="hot">爆款优先</el-radio-button>
          </el-radio-group>
          <el-tag type="primary">合计建议备货 {{ totalSuggest.toLocaleString() }} 件</el-tag>
          <el-tag type="info" effect="plain">共 {{ total }} 个 SKU</el-tag>
        </el-space>
      </template>

      <TableQueryBar
        v-model:keyword="keyword"
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
      />

      <el-empty v-if="!total" description="暂无备货数据" />

      <el-table v-else :data="paged" stripe>
        <el-table-column v-if="showStoreColumn" prop="storeName" label="所属店铺" width="130" show-overflow-tooltip />
        <AssigneeTableColumn />
        <el-table-column prop="sku" label="SKU" width="110" fixed />
        <el-table-column prop="name" label="商品名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="当日/7日均" width="120" align="center">
          <template #default="{ row }">
            {{ row.dailySales }} / {{ row.avg7DayDaily }}
          </template>
        </el-table-column>
        <el-table-column label="日均需求" width="90" align="right">
          <template #default="{ row }">{{ row.restock.dailyDemand }}</template>
        </el-table-column>
        <el-table-column label="官方仓" width="90" align="right" prop="officialStock" />
        <el-table-column label="本地仓" width="90" align="right">
          <template #default="{ row }">
            {{ row.localStock == null || row.localStock === '' ? '—' : row.localStock }}
          </template>
        </el-table-column>
        <el-table-column label="可售天数" width="100" align="right">
          <template #default="{ row }">
            <el-text :type="row.restock.coverDays <= (row.restock.warningDays || RESTOCK_CONFIG.safetyDays) ? 'danger' : undefined">
              {{ row.restock.coverDays >= 999 ? '∞' : row.restock.coverDays }} 天
            </el-text>
          </template>
        </el-table-column>
        <el-table-column label="安全库存" width="100" align="right">
          <template #default="{ row }">{{ row.restock.safetyStock }}</template>
        </el-table-column>
        <el-table-column label="目标库存" width="100" align="right">
          <template #default="{ row }">{{ row.restock.targetStock }}</template>
        </el-table-column>
        <el-table-column label="建议备货" width="110" align="right">
          <template #default="{ row }">
            <strong>{{ row.restock.suggestedRestock }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="紧急度" width="110">
          <template #default="{ row }">
            <el-tag :type="urgencyTag(row).type" size="small">{{ urgencyTag(row).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="跟进状态" width="130" fixed="right">
          <template #default="{ row }">
            <el-select
              :model-value="trackedStatus(row)"
              size="small"
              :loading="savingKey === restockStatusKey(row.storeId, row.sku)"
              @change="onStatusChange(row, $event)"
            >
              <el-option
                v-for="item in statusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="备注" width="150" fixed="right">
          <template #default="{ row }">
            <el-text v-if="trackedNote(row)" size="small">{{ trackedNote(row) }}</el-text>
            <el-text v-else-if="row.restock.shortfall > 0" type="danger" size="small">
              本地缺 {{ row.restock.shortfall }}
            </el-text>
            <el-text v-else type="info" size="small">—</el-text>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>{{ useBackendData ? '参数配置' : '参数配置（Demo）' }}</template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="告警阈值">{{ RESTOCK_CONFIG.leadTimeDays + RESTOCK_CONFIG.safetyBufferDays }} 天（提前期+缓冲）</el-descriptions-item>
            <el-descriptions-item label="目标覆盖">{{ RESTOCK_CONFIG.targetCoverDays }} 天</el-descriptions-item>
            <el-descriptions-item label="备货提前期">{{ RESTOCK_CONFIG.leadTimeDays }} 天</el-descriptions-item>
            <el-descriptions-item label="补货来源">本地仓库</el-descriptions-item>
          </el-descriptions>
          <el-text v-if="useBackendData" type="info" size="small" style="display: block; margin-top: 12px">
            跟进状态已同步至服务端，运营总览与任务中心可读。
          </el-text>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>优先补货清单</template>
          <el-table
            :data="urgencyFiltered.filter((p) => p.restock.suggestedRestock > 0).slice(0, 5)"
            size="small"
          >
            <el-table-column prop="name" label="商品" show-overflow-tooltip />
            <AssigneeTableColumn width="90" />
            <el-table-column label="建议量" width="90" align="right">
              <template #default="{ row }">{{ row.restock.suggestedRestock }}</template>
            </el-table-column>
            <el-table-column label="状态" width="88">
              <template #default="{ row }">
                <el-tag :type="statusMeta(row).type" size="small">{{ statusMeta(row).label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="原因" min-width="120">
              <template #default="{ row }">
                可售 {{ row.restock.coverDays }} 天
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
