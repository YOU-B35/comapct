<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AnalyticsStrip from '@/components/charts/AnalyticsStrip.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import {
  buildPlatformAlertsOption,
  buildPlatformRevenueOption,
  buildTaskStatusOption,
} from '@/utils/opsChartOptions'

const props = defineProps({
  platformSales: { type: Array, default: () => [] },
  overview: { type: Object, default: null },
  tasks: { type: Array, default: () => [] },
  highlightPlatformId: { type: String, default: '' },
})

const emit = defineEmits(['select-platform'])

const router = useRouter()
const auth = useAuthStore()

const revenueOption = computed(() => buildPlatformRevenueOption(props.platformSales))
const alertsOption = computed(() => buildPlatformAlertsOption(props.platformSales, props.overview))
const taskOption = computed(() => buildTaskStatusOption(props.tasks))

const platformRouteMap = {
  temu: 'temu',
  aliexpress: 'aliexpress',
  walmart: 'walmart',
  pdd: 'pdd',
  douyin: 'douyin',
  channels: 'channels',
  amazon: 'amazon',
  '1688': '1688',
  dtc: 'dtc',
}

function resolvePlatformId(params) {
  if (params?.data?.platformId) return params.data.platformId
  const name = params?.name
  if (!name) return ''
  const row = props.platformSales.find((p) => p.name === name)
  return row?.id || ''
}

function onRevenueClick(params) {
  const id = resolvePlatformId(params)
  if (!id) return
  emit('select-platform', id)
  const segment = platformRouteMap[id]
  if (!segment) return
  const prefix = auth.isBoss ? '/boss' : '/employee'
  router.push(`${prefix}/${segment}`)
}

function onAlertClick(params) {
  const id = resolvePlatformId(params)
  if (id) emit('select-platform', id)
}
</script>

<template>
  <AnalyticsStrip
    title="运营数据分析"
    hint="平台销售对比 · 待跟进结构 · 任务分布（点击柱状可高亮平台并进入模块）"
  >
    <el-row :gutter="12">
      <el-col :xs="24" :lg="12">
        <div class="chart-cell" :class="{ 'is-highlight': highlightPlatformId }">
          <div class="chart-cell__title">平台销售额 / 订单</div>
          <BaseChart :option="revenueOption" :height="280" @chart-click="onRevenueClick" />
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="chart-cell">
          <div class="chart-cell__title">待跟进问题结构</div>
          <BaseChart :option="alertsOption" :height="280" @chart-click="onAlertClick" />
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="chart-cell">
          <div class="chart-cell__title">任务状态分布</div>
          <BaseChart :option="taskOption" :height="280" />
        </div>
      </el-col>
    </el-row>
  </AnalyticsStrip>
</template>

<style scoped>
.chart-cell {
  padding: 8px 10px 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.chart-cell.is-highlight {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-7);
}

.chart-cell__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin-bottom: 4px;
}
</style>
