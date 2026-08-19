<script setup>
import { computed, watch } from 'vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  syncing: { type: Boolean, default: false },
  categorySync: { type: Object, default: () => ({}) },
  categoryCode: { type: String, default: '' },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['sync', 'refresh'])
const rows = computed(() => (Array.isArray(props.rows) ? props.rows : []))
const syncState = computed(() => props.categoryCode ? props.categorySync?.[props.categoryCode] : null)
const { page, pageSize, total, paged } = useFuzzySearchPagination(rows, {
  pageSize: 10,
  fields: ['productName', 'goodsNo', 'offerId'],
})

watch(rows, () => { page.value = 1 })

function thumbSrc(row) {
  const raw = String(row?.imageUrl || row?.image_url || '').trim()
  if (!raw) return ''
  if (raw.startsWith('//')) return 'https:' + raw
  if (raw.startsWith('http://')) return 'https://' + raw.slice(7)
  return raw
}

function displayPrice(row) {
  const value = row?.price
  return value == null || String(value).trim() === '' ? '—' : String(value)
}
</script>

<template>
  <div class="a1688-product-panel">
    <el-alert
      v-if="syncState?.status && syncState.status !== 'success'"
      title="该分类本次同步失败，当前继续展示上次成功结果"
      type="warning"
      show-icon
      :closable="false"
      class="sync-alert"
    />
    <div class="toolbar">
      <el-text type="info" size="small">
        共 {{ total }} 条
        <template v-if="syncState?.syncedAt"> · 分类同步于 {{ syncState.syncedAt }}</template>
      </el-text>
      <div class="toolbar-actions">
        <el-button size="small" :loading="loading" @click="emit('refresh')">刷新</el-button>
        <el-button type="primary" size="small" :loading="syncing" @click="emit('sync')">同步商品</el-button>
      </div>
    </div>

    <el-table v-loading="loading || syncing" :data="paged" stripe empty-text="暂无该分类商品" size="small">
      <el-table-column label="图片" width="92" align="center">
        <template #default="{ row }">
          <el-image v-if="thumbSrc(row)" :src="thumbSrc(row)" fit="cover" class="thumb" />
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="productName" label="商品名称" min-width="260" show-overflow-tooltip />
      <el-table-column prop="offerId" label="商品 ID" min-width="130" show-overflow-tooltip />
      <el-table-column v-if="showStoreColumn" label="店铺" min-width="130">
        <template #default="{ row }">{{ storeNameMap[row.storeId] || row.storeId || '—' }}</template>
      </el-table-column>
      <el-table-column label="价格" width="110" align="right">
        <template #default="{ row }">{{ displayPrice(row) }}</template>
      </el-table-column>
      <el-table-column prop="stock" label="库存" width="90" align="right" />
      <el-table-column prop="gmv1d" label="今日销售额" width="120" align="right" />
      <el-table-column prop="gmv30d" label="30天销售额" width="130" align="right" />
      <el-table-column prop="syncedAt" label="同步时间" width="160" />
    </el-table>

    <div class="pagination-row">
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, prev, pager, next" :total="total" />
    </div>
  </div>
</template>

<style scoped>
.toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
.toolbar-actions { display:flex; gap:8px; }
.sync-alert { margin-bottom:12px; }
.thumb { width:56px; height:56px; border-radius:6px; }
.pagination-row { display:flex; justify-content:flex-end; margin-top:16px; }
</style>
