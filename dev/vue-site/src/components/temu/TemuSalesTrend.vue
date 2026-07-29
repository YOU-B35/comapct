<script setup>
import { computed } from 'vue'

const props = defineProps({
  labels: { type: Array, default: () => [] },
  values: { type: Array, default: () => [] },
  estimated: { type: Array, default: () => [] },
  storeName: { type: String, default: '' },
})

const title = computed(() => (
  props.storeName
    ? `${props.storeName} · 近 7 日销量`
    : '近 7 日销量趋势'
))

const hasEstimated = computed(() => props.estimated.some(Boolean))

const maxValue = computed(() => Math.max(...props.values, 1))

function barHeight(value) {
  return `${Math.round((value / maxValue.value) * 100)}%`
}

function displayValue(index) {
  const value = props.values[index] || 0
  return props.estimated[index] ? `~${value}` : String(value)
}
</script>

<template>
  <el-card v-if="labels.length" shadow="never" class="trend-card">
    <template #header>
      <div class="trend-header">
        <span>{{ title }}</span>
        <el-text v-if="hasEstimated" type="info" size="small">
          ~ 为缺同步日按近 7 日销量回填
        </el-text>
      </div>
    </template>
    <div class="trend-chart">
      <div v-for="(label, index) in labels" :key="label" class="trend-bar-wrap">
        <div
          class="trend-bar"
          :class="{ 'is-estimated': estimated[index] }"
          :style="{ height: barHeight(values[index] || 0) }"
        />
        <span class="trend-value">{{ displayValue(index) }}</span>
        <span class="trend-label">{{ label }}</span>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.trend-card {
  margin-bottom: 16px;
}

.trend-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  min-height: 120px;
  padding: 8px 4px 0;
}

.trend-bar-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.trend-bar {
  width: 100%;
  max-width: 36px;
  min-height: 4px;
  background: linear-gradient(180deg, #409eff, #79bbff);
  border-radius: 4px 4px 0 0;
  transition: height 0.3s ease;
}

.trend-bar.is-estimated {
  background: linear-gradient(180deg, #a0cfff, #c6e2ff);
  opacity: 0.9;
}

.trend-value {
  font-size: 12px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.trend-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
