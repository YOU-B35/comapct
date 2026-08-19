<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchAlibaba1688ProductAnalytics } from '@/api/alibaba1688Api'
import { BESTSELLER_TIERS, classifyBestsellerTier, formatAnalyticsAmount } from '@/utils/alibaba1688Analytics'

const props = defineProps({
  type: { type: String, required: true }, // bestsellers | today_bestsellers | recent_sales
  backendReady: { type: Boolean, default: false },
  stores: { type: Array, default: () => [] },
  selectedStoreId: { type: String, default: 'all' },
})

const TITLES = {
  bestsellers: '爆款商品（近30天销量分层）',
  today_bestsellers: '今日爆款商品（24小时销量 ≥10）',
  recent_sales: '近期销量（近3天上架商品）',
}

const tier = ref('')
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

const filteredRows = computed(() => {
  if (props.type !== 'bestsellers' || !tier.value) return rows.value
  return rows.value.filter((row) => classifyBestsellerTier(row.salesQty) === tier.value)
})
const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})
const filteredTotal = computed(() => filteredRows.value.length)

async function load() {
  if (!props.backendReady || !props.stores.length) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await fetchAlibaba1688ProductAnalytics({ type: props.type, storeId: props.selectedStoreId })
    rows.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || rows.value.length
  } catch (error) {
    rows.value = []
    total.value = 0
    ElMessage.error(error?.message || `加载${TITLES[props.type] || '分析列表'}失败`)
  } finally {
    loading.value = false
  }
}

function thumbSrc(row) {
  const raw = String(row?.imageUrl || '').trim()
  if (!raw) return ''
  if (raw.startsWith('//')) return 'https:' + raw
  if (raw.startsWith('http://')) return 'https://' + raw.slice(7)
  return raw
}

function tierType(tierLabel) {
  if (tierLabel === '爆款') return 'danger'
  if (tierLabel === '潜力爆款') return 'warning'
  if (tierLabel === '一般') return 'primary'
  return 'info'
}

watch(() => [props.backendReady, props.stores.length, props.selectedStoreId], () => void load())
watch(tier, () => {
  page.value = 1
})
watch(pageSize, () => {
  page.value = 1
})
onMounted(() => void load())
defineExpose({ load })
</script>

<template>
  <div class="a1688-analytics">
    <div class="toolbar">
      <el-text type="info" size="small">{{ TITLES[type] }} · 共 {{ filteredRows.length }} 件</el-text>
      <el-select v-if="type === 'bestsellers'" v-model="tier" size="small" style="width: 130px">
        <el-option v-for="opt in BESTSELLER_TIERS" :key="opt.key || 'all'" :label="opt.label" :value="opt.key" />
      </el-select>
      <el-button size="small" :loading="loading" style="margin-left:auto" @click="load">刷新</el-button>
    </div>

    <el-table v-loading="loading" :data="pagedRows" stripe empty-text="暂无数据" size="small">
      <el-table-column label="商品" min-width="240">
        <template #default="{ row }">
          <div class="product-cell">
            <el-image v-if="thumbSrc(row)" :src="thumbSrc(row)" fit="cover" class="thumb" />
            <span>{{ row.productName || '—' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="单价" width="110" align="right">
        <template #default="{ row }">{{ row.price || '—' }}</template>
      </el-table-column>
      <el-table-column label="销量" width="90" align="right">
        <template #default="{ row }">{{ formatAnalyticsAmount(row.salesQty) }}</template>
      </el-table-column>
      <el-table-column label="销售额" width="120" align="right">
        <template #default="{ row }">{{ formatAnalyticsAmount(row.salesAmount) }}</template>
      </el-table-column>
      <el-table-column v-if="type === 'recent_sales'" prop="productUpdatedAt" label="上架时间" width="140" />
      <el-table-column prop="stock" label="库存" width="90" align="right" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column v-if="type === 'bestsellers'" label="档位" width="100">
        <template #default="{ row }">
          <el-tag :type="tierType(classifyBestsellerTier(row.salesQty))" size="small">
            {{ classifyBestsellerTier(row.salesQty) }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        layout="total, prev, pager, next"
        :total="filteredTotal"
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; }
.product-cell { display: flex; align-items: center; gap: 8px; }
.thumb { width: 40px; height: 40px; border-radius: 4px; flex: none; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 14px; }
</style>
