<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  /** 主说明；兼容历史 subtitle */
  description: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  eyebrow: { type: String, default: '' },
})

const resolvedDescription = computed(() => props.description || props.subtitle || '')
</script>

<template>
  <div class="page-header">
    <div class="page-header__main">
      <p v-if="eyebrow" class="page-header__eyebrow">{{ eyebrow }}</p>
      <h3 class="ch-page-title">{{ title }}</h3>
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

.page-header__main {
  min-width: 0;
  flex: 1;
}

.page-header__eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ch-text-muted);
}

.page-header__desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ch-text-muted);
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

  .page-header__actions {
    width: 100%;
  }
}
</style>
