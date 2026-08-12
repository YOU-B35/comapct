import { nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  TitleComponent,
  CanvasRenderer,
])

/**
 * @param {import('vue').Ref<HTMLElement|null>} elRef
 * @param {import('vue').Ref|import('vue').ComputedRef} optionRef
 * @param {{ onClick?: (params: any) => void }} [hooks]
 */
export function useEcharts(elRef, optionRef, hooks = {}) {
  const chart = shallowRef(null)
  let resizeObserver = null

  function ensureChart() {
    if (!elRef.value) return null
    if (!chart.value) {
      chart.value = echarts.init(elRef.value)
      if (hooks.onClick) {
        chart.value.on('click', (params) => hooks.onClick(params))
      }
    }
    return chart.value
  }

  function render() {
    const instance = ensureChart()
    if (!instance) return
    const option = optionRef.value
    if (option) {
      instance.setOption(option, { notMerge: true })
    }
    instance.resize()
  }

  function scheduleRender() {
    nextTick(() => {
      requestAnimationFrame(() => render())
    })
  }

  function resize() {
    chart.value?.resize()
  }

  onMounted(() => {
    scheduleRender()
    window.addEventListener('resize', resize)
    if (typeof ResizeObserver !== 'undefined' && elRef.value) {
      resizeObserver = new ResizeObserver(() => resize())
      resizeObserver.observe(elRef.value)
    }
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', resize)
    resizeObserver?.disconnect()
    resizeObserver = null
    chart.value?.dispose()
    chart.value = null
  })

  watch(optionRef, () => scheduleRender(), { deep: true })

  return { chart, resize, render }
}

export { echarts }
