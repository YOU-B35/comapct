<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchAlibaba1688Orders } from '@/api/alibaba1688Api'

const props = defineProps({
  backendReady: { type: Boolean, default: false },
  stores: { type: Array, default: () => [] },
  selectedStoreId: { type: String, default: 'all' },
  syncing: { type: Boolean, default: false },
})

const emit = defineEmits(['sync'])

const PRESETS = [
  { key: 'today', label: '今日' },
  { key: 'yesterday', label: '昨日' },
  { key: 'd7', label: '近7日' },
  { key: 'd30', label: '近30日' },
  { key: 'custom', label: '自定义' },
]

const STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: '未支付', value: 'unpaid' },
  { label: '已支付', value: 'paid' },
  { label: '退款中', value: 'refunding' },
  { label: '售后中', value: 'after_sale' },
  { label: '交易成功', value: 'completed' },
  { label: '已关闭', value: 'cancelled' },
]

const preset = ref('today')
const customRange = ref([])
const status = ref('')
const keyword = ref('')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)

function dateText(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function rangeOf() {
  if (preset.value === 'custom') {
    if (customRange.value?.length === 2) return [customRange.value[0], customRange.value[1]]
    return [dateText(0), dateText(0)]
  }
  if (preset.value === 'yesterday') return [dateText(-1), dateText(-1)]
  if (preset.value === 'd7') return [dateText(-6), dateText(0)]
  if (preset.value === 'd30') return [dateText(-29), dateText(0)]
  return [dateText(0), dateText(0)]
}

async function load() {
  if (!props.backendReady || !props.stores.length) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const [start, end] = rangeOf()
    const data = await fetchAlibaba1688Orders({
      startDate: start,
      endDate: end,
      status: status.value,
      keyword: keyword.value.trim(),
      storeId: props.selectedStoreId,
      page: page.value,
      pageSize: pageSize.value,
    })
    rows.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
  } catch (error) {
    rows.value = []
    total.value = 0
    ElMessage.error(error?.message || '加载 1688 经营明细失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function thumbSrc(row) {
  const raw = String(row?.imageUrl || '').trim()
  if (!raw) return ''
  if (raw.startsWith('//')) return 'https:' + raw
  if (raw.startsWith('http://')) return 'https://' + raw.slice(7)
  return raw
}

watch(() => [props.backendReady, props.stores.length, props.selectedStoreId, preset.value, status.value], () => search())
watch(customRange, () => {
  if (preset.value === 'custom') search()
})
watch(page, () => void load())

onMounted(() => void load())

defineExpose({ load })
</script>

<template>
  <div class="a1688-order-details">
    <div class="toolbar">
      <el-radio-group v-model="preset" size="small">
        <el-radio-button v-for="p in PRESETS" :key="p.key" :value="p.key">{{ p.label }}</el-radio-button>
      </el-radio-group>
      <el-date-picker
        v-if="preset === 'custom'"
        v-model="customRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        size="small"
      />
      <el-select v-model="status" size="small" style="width: 130px">
        <el-option v-for="opt in STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-input
        v-model="keyword"
        size="small"
        placeholder="订单号 / 商品关键词"
        clearable
        style="width: 220px"
        @keyup.enter="search"
        @clear="search"
      />
      <div class="toolbar-actions">
        <el-button size="small" :loading="loading" @click="search">查询</el-button>
        <el-button type="primary" size="small" :loading="syncing" @click="emit('sync')">同步订单</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="rows" stripe empty-text="暂无订单明细" size="small">
      <el-table-column label="商品" min-width="220">
        <template #default="{ row }">
          <div class="product-cell">
            <el-image v-if="thumbSrc(row)" :src="thumbSrc(row)" fit="cover" class="thumb" referrerpolicy="no-referrer" />
            <span>{{ row.productName || '—' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="orderNo" label="订单号" min-width="160" show-overflow-tooltip />
      <el-table-column prop="skuText" label="SKU" min-width="120" show-overflow-tooltip />
      <el-table-column prop="quantity" label="数量" width="70" align="right" />
      <el-table-column label="单价" width="90" align="right">
        <template #default="{ row }">{{ row.unitPrice || '—' }}</template>
      </el-table-column>
      <el-table-column label="行金额" width="100" align="right">
        <template #default="{ row }">{{ row.itemAmount || '0' }}</template>
      </el-table-column>
      <el-table-column label="订单实付" width="100" align="right">
        <template #default="{ row }">{{ row.paidAmount || '0' }}</template>
      </el-table-column>
      <el-table-column label="退款金额" width="100" align="right">
        <template #default="{ row }">{{ row.refundedAmount || '0' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90" />
      <el-table-column prop="paidAt" label="支付时间" width="150" />
      <el-table-column prop="refundedAt" label="退款时间" width="150">
        <template #default="{ row }">{{ row.refundedAt || '—' }}</template>
      </el-table-column>
      <el-table-column prop="buyerMasked" label="买家" width="90" />
    </el-table>

    <div class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        layout="total, prev, pager, next"
        :total="total"
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 14px; }
.toolbar-actions { display: flex; gap: 8px; margin-left: auto; }
.product-cell { display: flex; align-items: center; gap: 8px; }
.thumb { width: 40px; height: 40px; border-radius: 4px; flex: none; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 14px; }
</style>
