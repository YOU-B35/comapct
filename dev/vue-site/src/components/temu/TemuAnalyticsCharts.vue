<script setup>
import { computed } from 'vue'
import AnalyticsStrip from '@/components/charts/AnalyticsStrip.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import {
  buildTemuAlertStructureOption,
  buildTemuSalesTrendOption,
  buildTemuStoreSalesOption,
} from '@/utils/temuChartOptions'

const props = defineProps({
  products: { type: Array, default: () => [] },
  stores: { type: Array, default: () => [] },
  salesTrend: { type: Object, default: () => ({ labels: [], values: [] }) },
  storeName: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['select-store', 'navigate'])

const trendTitle = computed(() =>
  props.storeName ? `${props.storeName} · 近 7 日销量` : '近 7 日销量趋势',
)

const trendOption = computed(() => buildTemuSalesTrendOption(props.salesTrend))
const storeOption = computed(() => buildTemuStoreSalesOption(props.products, props.stores))
const alertOption = computed(() => buildTemuAlertStructureOption(props.products))

function onStoreClick(params) {
  const storeId = params?.data?.storeId
  if (storeId) emit('select-store', storeId)
}

function onAlertClick(params) {
  const tab = params?.data?.tab
  if (tab) emit('navigate', tab)
}
</script>

<template>
  <AnalyticsStrip
    title="Temu 数据分析"
    :hint="compact ? '点击异常扇区可切换 Tab' : '点击店铺条可选店；点击异常扇区切换 Tab'"
  >
    <el-row :gutter="12">
      <el-col :xs="24" :lg="compact ? 14 : 10">
        <div class="chart-cell">
          <div class="chart-cell__title">{{ trendTitle }}</div>
          <BaseChart :option="trendOption" :height="compact ? 240 : 280" />
        </div>
      </el-col>
      <el-col v-if="!compact" :xs="24" :lg="8">
        <div class="chart-cell">
          <div class="chart-cell__title">店铺日销对比</div>
          <BaseChart :option="storeOption" :height="280" @chart-click="onStoreClick" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="compact ? 10 : 6">
        <div class="chart-cell">
          <div class="chart-cell__title">异常结构</div>
          <BaseChart :option="alertOption" :height="compact ? 240 : 280" @chart-click="onAlertClick" />
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
}

.chart-cell__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin-bottom: 4px;
}
</style>
