<script setup>
import { computed } from 'vue'
import { summarizeTemuProducts } from '@/utils/temuStore'
import { formatMoneyDecimal } from '@/utils/format'
import { RESTOCK_CONFIG } from '@/constants/temu'
import TemuAnalyticsCharts from '@/components/temu/TemuAnalyticsCharts.vue'

const props = defineProps({
  products: { type: Array, required: true },
  stores: { type: Array, default: () => [] },
  salesTrend: { type: Object, default: () => ({ labels: [], values: [] }) },
  storeName: { type: String, default: '' },
})

const emit = defineEmits(['navigate', 'select-store'])

const summary = computed(() => {
  const overall = summarizeTemuProducts(props.products)
  const lossItems = props.products.filter((p) => p.isLoss)
  const slow15 = props.products.filter((p) => p.daysWithoutSale >= 15 && p.daysWithoutSale < 30)
  const slow30 = props.products.filter((p) => p.daysWithoutSale >= 30 && p.daysWithoutSale < 45)
  const slow45 = props.products.filter((p) => p.daysWithoutSale >= 45)
  const hotItems = props.products.filter((p) => p.isHot)
  const restockUrgent = props.products.filter((p) => p.restock.urgency === 'critical' || p.restock.urgency === 'warning')

  const totalLoss = lossItems.reduce((s, p) => s + Math.abs(p.unitProfit) * Math.max(p.officialStock, 1), 0)

  return [
    { label: '在线产品', value: overall.onlineCount, hint: overall.onlineHint, type: 'primary' },
    { label: '亏损 SKU', value: lossItems.length, hint: `潜在亏损 ${formatMoneyDecimal(totalLoss)}`, type: 'danger' },
    { label: '滞销预警', value: slow15.length + slow30.length + slow45.length, hint: `15/30/45 日：${slow15.length}/${slow30.length}/${slow45.length}`, type: 'warning' },
    { label: '爆款 SKU', value: hotItems.length, hint: '当日销量 ≥ 7 日均 × 1.5', type: 'success' },
    { label: '待备货 SKU', value: restockUrgent.length, hint: `官方仓覆盖 < 提前期+缓冲（${RESTOCK_CONFIG.leadTimeDays + RESTOCK_CONFIG.safetyBufferDays} 天）`, type: 'info' },
  ]
})

const accentByType = {
  primary: 'var(--ch-primary)',
  danger: 'var(--ch-error)',
  warning: 'var(--ch-warning)',
  success: 'var(--ch-success)',
  info: 'var(--ch-info)',
}
</script>

<template>
  <div class="employee-temu-overview">
    <div class="ch-kpi-grid">
      <article
        v-for="item in summary"
        :key="item.label"
        class="ch-kpi-card"
        :style="{ '--ch-kpi-accent': accentByType[item.type] || accentByType.primary }"
      >
        <div class="ch-kpi-card__label">{{ item.label }}</div>
        <div class="ch-kpi-card__value" :class="`is-${item.type}`">{{ item.value }}</div>
        <div class="ch-kpi-card__hint">{{ item.hint }}</div>
      </article>
    </div>

    <TemuAnalyticsCharts
      class="employee-charts"
      compact
      :products="products"
      :stores="stores"
      :sales-trend="salesTrend"
      :store-name="storeName"
      @navigate="emit('navigate', $event)"
      @select-store="emit('select-store', $event)"
    />
  </div>
</template>

<style scoped>
.employee-temu-overview {
  display: grid;
  gap: 16px;
}

.employee-charts {
  margin-top: 0;
}
</style>
