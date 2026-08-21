<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  create1688MonitorTarget,
  delete1688MonitorTarget,
  fetch1688MonitorLatest,
  fetch1688MonitorSignals,
  fetch1688MonitorTrend,
  list1688MonitorTargets,
  trigger1688MonitorTarget,
  update1688MonitorSchedule,
} from '@/api/alibaba1688MonitorApi'

const props = defineProps({
  backendReady: { type: Boolean, default: false },
})

const targets = ref([])
const selectedTargetId = ref('')
const latest = ref(null)
const products = ref([])
const signals = ref([])
const trend = ref([])
const trendProductId = ref('')
const loading = ref(false)
const showAdd = ref(false)
const form = ref({
  label: '',
  target_url: '',
  crawl_strategy: '1688_shop_topn',
  top_n: 20,
  pinned_offer_ids: '',
  interval_minutes: 120,
  webhook_url: '',
})

const SIGNAL_TYPE_TEXT = {
  price_change: '价格变动',
  sales_surge: '销量异常',
  delist_or_relist: '下架/恢复上架',
  bestseller_new_entry: '新爆款上榜',
  stock_warning: '缺货预警',
  auth_or_risk: '登录/风控告警',
  recent_launch: '新品上架',
  sales_outlier: '销量异动',
}

function signalTypeText(type) {
  return SIGNAL_TYPE_TEXT[type] || String(type || '')
}

function formatSignalValue(type, raw) {
  let obj = raw
  if (typeof raw === 'string') {
    try {
      obj = JSON.parse(raw)
    } catch (e) {
      return String(raw || '')
    }
  }
  if (!obj || typeof obj !== 'object') return String(raw || '')
  switch (type) {
    case 'price_change':
      return `价格变动：${obj.old ?? '-'} → ${obj.new ?? '-'}`
    case 'sales_surge':
      return `日增量 ${obj.delta ?? '-'}（历史均值 ${obj.avg ?? '-'}）`
    case 'delist_or_relist':
      return obj.status === 'relisted' ? '商品恢复上架' : '商品已下架'
    case 'bestseller_new_entry':
      return `新进入店铺爆款榜第 ${obj.rank ?? '-'} 名`
    case 'auth_or_risk':
      return obj.code ? `异常代码：${obj.code}` : '登录或风控异常'
    case 'stock_warning':
      return obj.text || '出现缺货/低库存信号'
    default:
      return String(raw || '')
  }
}

async function loadTargets() {
  if (!props.backendReady) return
  try {
    const data = await list1688MonitorTargets()
    targets.value = Array.isArray(data) ? data : []
    if (!selectedTargetId.value && targets.value.length) selectedTargetId.value = targets.value[0].id
    if (selectedTargetId.value) await loadLatest()
  } catch (error) {
    ElMessage.error(error?.message || '加载 1688 竞店监控失败')
  }
}

async function loadLatest() {
  if (!selectedTargetId.value) return
  loading.value = true
  try {
    const data = await fetch1688MonitorLatest(selectedTargetId.value)
    latest.value = data
    products.value = Array.isArray(data?.products) ? data.products : []
    signals.value = await fetch1688MonitorSignals(selectedTargetId.value, 50)
    await loadTrend()
  } catch (error) {
    ElMessage.error(error?.message || '加载快照失败')
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  trend.value = await fetch1688MonitorTrend(selectedTargetId.value, {
    days: 30,
    productId: trendProductId.value,
  })
  renderTrend()
}

function renderTrend() {
  const chartEl = document.getElementById('a1688-monitor-trend')
  if (!chartEl) return
  const chart = echarts.init(chartEl)
  const seriesMap = {}
  for (const row of trend.value) {
    if (!seriesMap[row.product_id]) seriesMap[row.product_id] = []
    seriesMap[row.product_id].push([row.snapshot_at, row.total_sales])
  }
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll' },
    xAxis: { type: 'category' },
    yAxis: { type: 'value' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: Object.entries(seriesMap).map(([pid, points]) => ({
      name: pid,
      type: 'line',
      data: points,
      showSymbol: false,
    })),
  })
}

async function trigger(targetId) {
  try {
    await trigger1688MonitorTarget(targetId, { force: true, bypass_cooldown: true, reason: 'manual refresh' })
    ElMessage.success('已触发刷新，请稍后查看最新快照')
  } catch (error) {
    ElMessage.error(error?.message || '触发失败')
  }
}

async function saveTarget() {
  const payload = {
    label: form.value.label,
    target_url: form.value.target_url,
    target_type: 'shop',
    platform: '1688',
    crawl_strategy: form.value.crawl_strategy,
    config_json: JSON.stringify({
      top_n: Number(form.value.top_n) || 20,
      pinned_offer_ids: form.value.pinned_offer_ids.split(',').map((s) => s.trim()).filter(Boolean),
      webhook_url: form.value.webhook_url.trim(),
    }),
  }
  try {
    const created = await create1688MonitorTarget(payload)
    if (created?.id) {
      await update1688MonitorSchedule(created.id, {
        enabled: true,
        schedule_type: 'interval',
        interval_minutes: Number(form.value.interval_minutes) || 120,
        max_products: Number(form.value.top_n) || 20,
        retry_limit: 1,
      })
    }
    showAdd.value = false
    form.value.pinned_offer_ids = ''
    await loadTargets()
    ElMessage.success('店铺监控已添加')
  } catch (error) {
    ElMessage.error(error?.message || '添加失败')
  }
}

async function removeTarget(targetId) {
  try {
    await ElMessageBox.confirm('确认删除该监控目标？历史快照会保留。', '删除确认')
    await delete1688MonitorTarget(targetId)
    if (selectedTargetId.value === targetId) selectedTargetId.value = ''
    await loadTargets()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error?.message || '删除失败')
  }
}

function thumbSrc(row) {
  const raw = String(row?.image_url || row?.imageUrl || '').trim()
  if (!raw) return ''
  if (raw.startsWith('//')) return 'https:' + raw
  return raw
}

function productInitial(row) {
  return String(row?.product_name || row?.product_id || '?').slice(0, 1)
}

onMounted(() => void loadTargets())
defineExpose({ loadTargets })
</script>

<template>
  <div class="a1688-monitor">
    <div class="toolbar">
      <el-button type="primary" :disabled="!backendReady" @click="showAdd = true">添加店铺监控</el-button>
      <el-button :disabled="!selectedTargetId" :loading="loading" @click="loadLatest">刷新快照</el-button>
    </div>

    <el-dialog v-model="showAdd" title="添加 1688 店铺监控" width="560px">
      <el-form label-width="110px">
        <el-form-item label="店铺名称"><el-input v-model="form.label" placeholder="如：东博瑞" /></el-form-item>
        <el-form-item label="店铺/商品链接">
          <el-input v-model="form.target_url" placeholder="https://shop16yx1905b2433.1688.com" />
        </el-form-item>
        <el-form-item label="监控类型">
          <el-select v-model="form.crawl_strategy">
            <el-option label="店铺爆款 Top N" value="1688_shop_topn" />
            <el-option label="指定商品盯梢" value="1688_pinned_offers" />
          </el-select>
        </el-form-item>
        <el-form-item label="Top N"><el-input-number v-model="form.top_n" :min="1" :max="50" /></el-form-item>
        <el-form-item label="盯梢商品">
          <el-input v-model="form.pinned_offer_ids" placeholder="offerId，逗号分隔，如 930671411701,867473865842" />
        </el-form-item>
        <el-form-item label="轮询间隔">
          <el-select v-model="form.interval_minutes">
            <el-option label="60 分钟" :value="60" />
            <el-option label="120 分钟" :value="120" />
          </el-select>
        </el-form-item>
        <el-form-item label="Webhook"><el-input v-model="form.webhook_url" placeholder="钉钉/企微机器人地址（可选）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="saveTarget">保存</el-button>
      </template>
    </el-dialog>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>监控店铺</template>
          <el-table
            :data="targets"
            size="small"
            highlight-current-row
            @current-change="(row) => { selectedTargetId = row?.id || ''; loadLatest() }"
          >
            <el-table-column prop="label" label="店铺" />
            <el-table-column label="状态" width="70">
              <template #default="{ row }">{{ row.status === 'active' ? '监控中' : '停用' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="130">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="trigger(row.id)">立即刷新</el-button>
                <el-button link type="danger" size="small" @click="removeTarget(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            爆款榜
            <span v-if="latest?.latest_snapshot_at" style="float: right; font-size: 12px; color: #999">
              最近快照：{{ latest.latest_snapshot_at }}
            </span>
          </template>
          <el-table :data="products" size="small" max-height="420">
            <el-table-column prop="rank" label="排名" width="55" />
            <el-table-column label="商品" min-width="220">
              <template #default="{ row }">
                <a :href="row.url" target="_blank" rel="noopener">
                  <el-image
                    v-if="thumbSrc(row)"
                    :src="thumbSrc(row)"
                    fit="cover"
                    style="width: 36px; height: 36px; vertical-align: middle"
                  />
                  <span
                    v-else
                    style="display: inline-block; width: 36px; height: 36px; line-height: 36px; text-align: center; background: #f0f2f5; color: #909399; border-radius: 4px; vertical-align: middle"
                  >{{ productInitial(row) }}</span>
                  <span style="margin-left: 6px">{{ row.product_name }}</span>
                </a>
              </template>
            </el-table-column>
            <el-table-column prop="shop_name" label="店铺" min-width="140" />
            <el-table-column prop="price" label="价格" width="70" />
            <el-table-column prop="total_sales" label="累计销量" width="90" />
            <el-table-column prop="daily_sales" label="日增量" width="80" />
            <el-table-column prop="dropship_7d" label="代发7天" width="90" />
            <el-table-column prop="rebuy_rate" label="复购率" width="90" />
            <el-table-column label="状态" width="70">
              <template #default="{ row }">
                <el-tag v-if="row.expired" type="danger" size="small">下架</el-tag>
                <el-tag v-else type="success" size="small">在售</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        累计销量趋势（30 天）
        <el-select v-model="trendProductId" size="small" style="float: right; width: 220px" @change="loadTrend">
          <el-option label="全部商品" value="" />
          <el-option v-for="p in products" :key="p.product_id" :label="p.product_name" :value="p.product_id" />
        </el-select>
      </template>
      <div id="a1688-monitor-trend" style="height: 320px"></div>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>告警信号</template>
      <el-table :data="signals" size="small">
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column label="类型" width="150">
          <template #default="{ row }">{{ signalTypeText(row.signal_type) }}</template>
        </el-table-column>
        <el-table-column prop="product_name" label="商品" min-width="180" />
        <el-table-column label="详情" min-width="220">
          <template #default="{ row }">{{ formatSignalValue(row.signal_type, row.signal_value) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
