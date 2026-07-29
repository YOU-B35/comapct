<script setup>
import { computed } from 'vue'
import { summarizeTemuProducts } from '@/utils/temuStore'
import { formatMoneyDecimal } from '@/utils/format'

const props = defineProps({
  products: { type: Array, required: true },
})

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
    { label: '待备货 SKU', value: restockUrgent.length, hint: '官方仓覆盖不足 14 天', type: 'info' },
  ]
})
</script>

<template>
  <el-row :gutter="16">
    <el-col v-for="item in summary" :key="item.label" :xs="24" :sm="12" :lg="8" :xl="4">
      <el-card shadow="never">
        <el-statistic :title="item.label" :value="item.value">
          <template #suffix>
            <el-tag :type="item.type" size="small" effect="plain">Temu</el-tag>
          </template>
        </el-statistic>
        <el-text size="small" type="info">{{ item.hint }}</el-text>
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
.el-card :deep(.el-statistic__head) {
  margin-bottom: 8px;
}
</style>
