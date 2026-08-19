<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchAlibaba1688PeerBestsellers,
} from '@/api/alibaba1688Api'

const props = defineProps({
  backendReady: { type: Boolean, default: false },
  stores: { type: Array, default: () => [] },
  syncing: { type: Boolean, default: false },
})

const emit = defineEmits(['sync'])

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)

async function load() {
  if (!props.backendReady || !props.stores.length) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await fetchAlibaba1688PeerBestsellers({ page: page.value, pageSize: pageSize.value })
    rows.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
  } catch (error) {
    rows.value = []
    total.value = 0
    ElMessage.error(error?.message || '加载同行爆款追踪失败')
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

function openOffer(row) {
  if (row?.offerUrl) window.open(row.offerUrl, '_blank', 'noopener')
}

watch(() => [props.backendReady, props.stores.length], () => {
  page.value = 1
  void load()
})
watch(page, () => void load())
watch(pageSize, () => {
  page.value = 1
  void load()
})

onMounted(() => void load())
defineExpose({ load })
</script>

<template>
  <div class="a1688-peer">
    <div class="toolbar">
      <el-tooltip placement="top" :content="'销量为平台公开「已售 X 件」展示口径，平台未标注为累计或近30天，以 1688 商品页展示为准'">
        <el-text type="info" size="small">
          同行店铺同类爆款（平台公开「已售」销量口径）· 共 {{ total }} 条
        </el-text>
      </el-tooltip>
      <div class="toolbar-actions">
        <el-button size="small" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" size="small" :loading="syncing" @click="emit('sync')">抓取同行爆款</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="rows" stripe empty-text="暂无数据，点击「抓取同行爆款」同步" size="small">
      <el-table-column label="商品" min-width="240">
        <template #default="{ row }">
          <div class="product-cell" @click="openOffer(row)">
            <el-image v-if="thumbSrc(row)" :src="thumbSrc(row)" fit="cover" class="thumb" />
            <span class="title">{{ row.title || '—' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="shopName" label="店铺名称" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.shopName || '—' }}</template>
      </el-table-column>
      <el-table-column label="单价" width="100" align="right">
        <template #default="{ row }">{{ row.price ? `¥${row.price}` : '—' }}</template>
      </el-table-column>
      <el-table-column label="销量（平台已售）" width="130" align="right">
        <template #default="{ row }">{{ row.saleText || row.sales || '—' }}</template>
      </el-table-column>
      <el-table-column label="商品质量分" width="100" align="center">
        <template #default="{ row }">{{ row.qualityScore || '—' }}</template>
      </el-table-column>
      <el-table-column prop="suggestion" label="追踪建议" min-width="200" show-overflow-tooltip />
      <el-table-column prop="syncedAt" label="抓取时间" width="150" />
    </el-table>

    <div class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="10"
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; }
.toolbar-actions { display: flex; gap: 8px; margin-left: auto; }
.product-cell { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.thumb { width: 40px; height: 40px; border-radius: 4px; flex: none; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 14px; }
</style>
