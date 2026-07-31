<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { RESTOCK_CONFIG } from '@/constants/temu'
import { formatSurgeDisplay } from '@/utils/temu'
import {
  loadHotBroadcasts,
  markHotBroadcastRead,
  publishHotBroadcast,
} from '@/api/temuHotBroadcast'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  products: { type: Array, required: true },
  broadcasts: { type: Array, default: () => [] },
  useBackendData: { type: Boolean, default: false },
})

const emit = defineEmits(['broadcast', 'update:broadcasts'])

const auth = useAuthStore()
const localBroadcasts = ref([...props.broadcasts])
const publishingSku = ref('')
const readingId = ref('')

watch(
  () => props.broadcasts,
  (next) => {
    localBroadcasts.value = [...next]
  },
)

const hotProducts = computed(() =>
  [...props.products]
    .filter((p) => p.isHot)
    .sort((a, b) => {
      const salesDiff = Number(b.dailySales) - Number(a.dailySales)
      if (salesDiff !== 0) return salesDiff
      const ra = a.surgeRatio == null ? -1 : Number(a.surgeRatio)
      const rb = b.surgeRatio == null ? -1 : Number(b.surgeRatio)
      return rb - ra
    }),
)

const {
  keyword: hotKeyword,
  page: hotPage,
  pageSize: hotPageSize,
  total: hotTotal,
  paged: hotPaged,
} = useFuzzySearchPagination(hotProducts, {
  fields: ['sku', 'name', 'storeName'],
})

const {
  keyword: broadcastKeyword,
  page: broadcastPage,
  pageSize: broadcastPageSize,
  total: broadcastTotal,
  paged: broadcastPaged,
} = useFuzzySearchPagination(localBroadcasts, {
  fields: ['name', 'operator', 'sku'],
})

const readerName = computed(() => {
  if (auth.isBoss) return auth.company?.name ? `${auth.company.name} 管理员` : '企业管理员'
  if (auth.isEmployee) return auth.employee?.name || '运营人员'
  if (auth.isWarehouse) return auth.warehouse?.name || '仓管人员'
  return '用户'
})

const readerId = computed(() => {
  if (auth.isEmployee) return String(auth.employee?.id || auth.backendUserId || '')
  if (auth.isWarehouse) return String(auth.warehouse?.id || auth.backendUserId || '')
  return String(auth.backendUserId || '')
})

onMounted(async () => {
  if (props.useBackendData) {
    localBroadcasts.value = await loadHotBroadcasts(auth)
    emit('update:broadcasts', localBroadcasts.value)
  }
})

function surgeTagType(row) {
  if (row.surgeIsNew || row.surgeRatio == null) return 'info'
  if (row.surgeRatio >= RESTOCK_CONFIG.hotSurgeRatio) return 'danger'
  if (row.surgeRatio >= 1.2) return 'warning'
  return 'info'
}

function surgeLabel(row) {
  return formatSurgeDisplay(row)
}

function hasRead(item) {
  return (item.readBy || []).includes(readerName.value)
}

async function sendBroadcast(product) {
  publishingSku.value = product.sku
  try {
    const entry = await publishHotBroadcast(
      {
        shopId: product.storeId,
        sku: product.sku,
        name: product.name,
        dailySales: product.dailySales,
        avg7DayDaily: product.avg7DayDaily,
        surgeRatio: product.surgeRatio,
        operator: readerName.value,
        time: new Date().toLocaleString('zh-CN', { hour12: false }),
      },
      auth,
    )
    if (props.useBackendData) {
      localBroadcasts.value = await loadHotBroadcasts(auth)
    } else {
      localBroadcasts.value = [entry, ...localBroadcasts.value.filter((item) => item.id !== entry.id)]
    }
    emit('broadcast', entry)
    emit('update:broadcasts', localBroadcasts.value)
    ElMessage.success(`已全公司通报：${product.name}`)
  } catch (err) {
    ElMessage.error(err.message || '通报失败')
  } finally {
    publishingSku.value = ''
  }
}

async function markRead(item) {
  if (hasRead(item)) return
  readingId.value = item.id
  try {
    if (props.useBackendData) {
      const updated = await markHotBroadcastRead(item.id, readerName.value, auth, readerId.value)
      if (updated) {
        localBroadcasts.value = localBroadcasts.value.map((row) => (row.id === updated.id ? updated : row))
      } else {
        localBroadcasts.value = await loadHotBroadcasts(auth)
      }
    } else {
      const list = await markHotBroadcastRead(item.id, readerName.value, auth)
      if (list) {
        localBroadcasts.value = list
      }
    }
    emit('update:broadcasts', localBroadcasts.value)
    ElMessage.success('已标记为已读')
  } catch (err) {
    ElMessage.error(err.message || '标记失败')
  } finally {
    readingId.value = ''
  }
}
</script>

<template>
  <div>
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never">
          <template #header>
            <span>爆款识别（当日销量 vs 7 日均值）</span>
          </template>

          <TableQueryBar
            v-model:keyword="hotKeyword"
            v-model:page="hotPage"
            v-model:page-size="hotPageSize"
            :total="hotTotal"
          />

          <el-empty v-if="!hotTotal" description="暂无动销 SKU" />

          <el-table v-else :data="hotPaged" stripe>
            <el-table-column prop="sku" label="SKU" width="110" />
            <el-table-column prop="name" label="商品名称" min-width="160" show-overflow-tooltip />
            <el-table-column label="当日销量" width="100" align="right" prop="dailySales" sortable />
            <el-table-column label="7 日均值" width="100" align="right">
              <template #default="{ row }">{{ row.avg7DayDaily }}</template>
            </el-table-column>
            <el-table-column label="增幅" width="110" align="right">
              <template #default="{ row }">
                <el-tag :type="surgeTagType(row)" size="small">
                  {{ surgeLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="判定" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.isHot" type="danger" effect="dark">爆款</el-tag>
                <el-tag v-else type="info" effect="plain">观察</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="110" fixed="right">
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  :disabled="!row.isHot"
                  :loading="publishingSku === row.sku"
                  @click="sendBroadcast(row)"
                >
                  通报
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never">
          <template #header>
            <el-space>
              <span>全公司通报记录</span>
              <el-tag size="small">{{ broadcastTotal }} 条</el-tag>
            </el-space>
          </template>

          <TableQueryBar
            v-model:keyword="broadcastKeyword"
            v-model:page="broadcastPage"
            v-model:page-size="broadcastPageSize"
            :total="broadcastTotal"
            placeholder="搜索商品 / 通报人"
            :page-sizes="[5, 10, 20, 50]"
          />

          <el-empty v-if="!broadcastTotal" description="暂无通报记录" :image-size="64" />

          <el-timeline v-else>
            <el-timeline-item
              v-for="item in broadcastPaged"
              :key="item.id"
              :timestamp="item.time"
              type="success"
            >
              <strong>{{ item.name }}</strong>
              <el-text tag="p" size="small" type="info">
                通报人 {{ item.operator || '系统' }} · 当日 {{ item.dailySales }} 件 · 7 日均 {{ item.avg7DayDaily }} · 增幅 {{ formatSurgeDisplay(item) }}
              </el-text>
              <el-text v-if="item.readBy?.length" size="small" type="success">
                已读：{{ item.readBy.join('、') }}
              </el-text>
              <div style="margin-top: 8px">
                <el-button
                  v-if="!hasRead(item)"
                  link
                  type="primary"
                  size="small"
                  :loading="readingId === item.id"
                  @click="markRead(item)"
                >
                  标记已读
                </el-button>
                <el-text v-else type="success" size="small">你已读</el-text>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>

        <el-card shadow="never" style="margin-top: 16px">
          <template #header>爆款判定规则</template>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="当日销量">≥ {{ RESTOCK_CONFIG.hotMinDailySales }} 件</el-descriptions-item>
            <el-descriptions-item label="增幅阈值">当日 / 7 日均 ≥ {{ RESTOCK_CONFIG.hotSurgeRatio }}×</el-descriptions-item>
            <el-descriptions-item label="通报范围">
              {{ useBackendData ? '全租户员工可见（服务端持久化）' : '全公司员工可见（localStorage 持久化）' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
