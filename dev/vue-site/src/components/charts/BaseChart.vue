<script setup>
import { computed, ref } from 'vue'
import { useEcharts } from '@/composables/useEcharts'
import { emptyOption } from '@/utils/chartTheme'

const props = defineProps({
  option: { type: Object, default: null },
  height: { type: [Number, String], default: 260 },
  emptyText: { type: String, default: '暂无数据' },
})

const emit = defineEmits(['chart-click'])

const elRef = ref(null)
const heightStyle = computed(() =>
  typeof props.height === 'number' ? `${props.height}px` : props.height,
)

const resolvedOption = computed(() => {
  if (!props.option || props.option.__empty) {
    return emptyOption(props.emptyText)
  }
  return props.option
})

useEcharts(elRef, resolvedOption, {
  onClick: (params) => emit('chart-click', params),
})
</script>

<template>
  <div ref="elRef" class="base-chart" :style="{ height: heightStyle }" />
</template>

<style scoped>
.base-chart {
  width: 100%;
  min-height: 160px;
}
</style>
