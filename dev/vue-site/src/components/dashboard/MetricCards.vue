<script setup>
import { TrendCharts, ShoppingCart, WarningFilled, CircleCheckFilled } from '@element-plus/icons-vue'
import { formatMoney } from '@/utils/format'

defineProps({
  metrics: { type: Array, required: true },
})

const fallbackIcons = [TrendCharts, ShoppingCart, WarningFilled, CircleCheckFilled]
</script>

<template>
  <div class="kpi-grid">
    <article
      v-for="(item, index) in metrics"
      :key="item.label"
      class="kpi-card"
      :class="`kpi-card--${item.tone || 'primary'}`"
    >
      <div class="kpi-card__icon" aria-hidden="true">
        <el-icon :size="18">
          <component :is="item.icon || fallbackIcons[index % fallbackIcons.length]" />
        </el-icon>
      </div>
      <div class="kpi-card__body">
        <div class="kpi-card__label">{{ item.label }}</div>
        <div class="kpi-card__value">
          <template v-if="item.isMoney">{{ formatMoney(item.value) }}</template>
          <template v-else-if="item.suffix">{{ item.value }}{{ item.suffix }}</template>
          <template v-else>{{ Number(item.value || 0).toLocaleString() }}</template>
        </div>
        <div v-if="item.hint" class="kpi-card__hint">{{ item.hint }}</div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  position: relative;
  display: grid;
  grid-template-columns: 42px 1fr;
  gap: 12px;
  align-items: start;
  padding: 16px 16px 15px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background:
    linear-gradient(165deg, rgba(255, 255, 255, 0.92) 0%, var(--ch-surface) 55%),
    var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
  overflow: hidden;
}

.kpi-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--kpi-accent, var(--ch-primary));
}

.kpi-card--primary { --kpi-accent: var(--ch-primary); --kpi-soft: var(--ch-primary-soft); }
.kpi-card--success { --kpi-accent: var(--ch-success); --kpi-soft: #e8f7f1; }
.kpi-card--warning { --kpi-accent: var(--ch-warning); --kpi-soft: #fff8eb; }
.kpi-card--danger { --kpi-accent: var(--ch-error); --kpi-soft: #fff1f3; }
.kpi-card--info { --kpi-accent: var(--ch-info); --kpi-soft: var(--ch-primary-soft); }

.kpi-card__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: var(--kpi-soft, var(--ch-primary-soft));
  color: var(--kpi-accent, var(--ch-primary));
}

.kpi-card__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ch-text-muted);
  letter-spacing: 0.01em;
}

.kpi-card__value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: var(--ch-text);
}

.kpi-card--danger .kpi-card__value { color: var(--ch-error); }
.kpi-card--warning .kpi-card__value { color: var(--ch-warning); }
.kpi-card--success .kpi-card__value { color: var(--ch-success); }
.kpi-card--primary .kpi-card__value { color: var(--ch-primary); }

.kpi-card__hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--ch-text-muted);
}

@media (max-width: 1100px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
