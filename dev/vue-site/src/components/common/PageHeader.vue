<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  /** 主说明；兼容历史 subtitle */
  description: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  eyebrow: { type: String, default: '' },
  /** 紧凑页头：更小标题、更少留白 */
  compact: { type: Boolean, default: false },
})

const resolvedDescription = computed(() => props.description || props.subtitle || '')
</script>

<template>
  <div class="page-header" :class="{ 'page-header--compact': compact }">
    <div class="page-header__main">
      <p v-if="eyebrow" class="page-header__eyebrow">{{ eyebrow }}</p>
      <h3 class="ch-page-title page-header__title">{{ title }}</h3>
      <p v-if="resolvedDescription" class="page-header__desc">{{ resolvedDescription }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  padding: 0 0 14px;
  border: 0;
  border-bottom: 1px solid var(--ch-border);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.page-header--compact {
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  padding: 0 0 8px;
}

.page-header__main {
  min-width: 0;
  flex: 1;
}

.page-header--compact .page-header__title {
  font-size: 16px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.page-header__eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ch-text-muted);
}

.page-header--compact .page-header__eyebrow {
  margin: 0 0 2px;
  font-size: 10px;
}

.page-header__desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ch-text-muted);
}

.page-header--compact .page-header__desc {
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 1.35;
}

.page-header__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

@media (max-width: 767px) {
  .page-header {
    flex-direction: column;
    padding: 0 0 12px;
  }

  .page-header--compact {
    padding: 0 0 8px;
  }

  .page-header__actions {
    width: 100%;
  }
}
</style>
