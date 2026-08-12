<script setup>
import { computed } from 'vue'
import AnalyticsStrip from '@/components/charts/AnalyticsStrip.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import {
  buildHorizontalCompareOption,
  buildMetricBarsOption,
  buildStructurePieOption,
} from '@/utils/platformChartOptions'

const props = defineProps({
  title: { type: String, default: '数据分析' },
  hint: { type: String, default: '点击扇区可切换对应 Tab' },
  /** @type {{ name: string, value: number, tab?: string, color?: string }[]} */
  structureItems: { type: Array, default: () => [] },
  structureTitle: { type: String, default: '待办结构' },
  /** @type {{ name: string, value: number, id?: string }[]} */
  compareItems: { type: Array, default: () => [] },
  compareTitle: { type: String, default: '店铺对比' },
  compareValueLabel: { type: String, default: '' },
  /** @type {{ name: string, value: number }[]} */
  metricItems: { type: Array, default: () => [] },
  metricTitle: { type: String, default: '核心指标' },
})

const emit = defineEmits(['navigate', 'select-id'])

const structureOption = computed(() => buildStructurePieOption(props.structureItems))
const compareOption = computed(() =>
  buildHorizontalCompareOption(props.compareItems, props.compareValueLabel),
)
const metricOption = computed(() => buildMetricBarsOption(props.metricItems))

const showCompare = computed(() => props.compareItems.length > 0)
const showMetrics = computed(() => props.metricItems.length > 0)

function onStructureClick(params) {
  const tab = params?.data?.tab
  if (tab) emit('navigate', tab)
}

function onCompareClick(params) {
  const id = params?.data?.id
  if (id != null && id !== '') emit('select-id', id)
}
</script>

<template>
  <AnalyticsStrip :title="title" :hint="hint">
    <el-row :gutter="12">
      <el-col v-if="showMetrics" :xs="24" :lg="showCompare ? 8 : 12">
        <div class="chart-cell">
          <div class="chart-cell__title">{{ metricTitle }}</div>
          <BaseChart :option="metricOption" :height="260" />
        </div>
      </el-col>
      <el-col v-if="showCompare" :xs="24" :lg="showMetrics ? 8 : 12">
        <div class="chart-cell">
          <div class="chart-cell__title">{{ compareTitle }}</div>
          <BaseChart :option="compareOption" :height="260" @chart-click="onCompareClick" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="showCompare || showMetrics ? 8 : 24">
        <div class="chart-cell">
          <div class="chart-cell__title">{{ structureTitle }}</div>
          <BaseChart :option="structureOption" :height="260" @chart-click="onStructureClick" />
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
