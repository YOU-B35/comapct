<script setup>
import { computed } from 'vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import {
  buildTemuHotTopOption,
  buildTemuLossTopOption,
  buildTemuRestockTopOption,
  buildTemuSlowDistOption,
} from '@/utils/temuChartOptions'

const props = defineProps({
  tab: { type: String, required: true },
  products: { type: Array, default: () => [] },
})

const emit = defineEmits(['highlight-sku'])

const title = computed(() => {
  if (props.tab === 'profit') return '亏损潜在金额 Top'
  if (props.tab === 'slow') return '滞销天数分布'
  if (props.tab === 'hot') return '爆款日销 Top'
  if (props.tab === 'restock') return '备货建议量 Top'
  return '数据分析'
})

const option = computed(() => {
  if (props.tab === 'profit') return buildTemuLossTopOption(props.products)
  if (props.tab === 'slow') return buildTemuSlowDistOption(props.products)
  if (props.tab === 'hot') return buildTemuHotTopOption(props.products)
  if (props.tab === 'restock') return buildTemuRestockTopOption(props.products)
  return { __empty: true }
})

function onClick(params) {
  const sku = params?.data?.sku
  if (sku) emit('highlight-sku', sku)
}
</script>

<template>
  <el-card shadow="never" class="tab-analytics">
    <template #header>
      <span>{{ title }}</span>
    </template>
    <BaseChart :option="option" :height="220" @chart-click="onClick" />
  </el-card>
</template>

<style scoped>
.tab-analytics {
  margin-bottom: 12px;
}
</style>
