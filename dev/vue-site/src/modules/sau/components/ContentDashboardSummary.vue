<script setup>
defineProps({
  summary: { type: Object, default: () => ({}) },
})
</script>

<template>
  <div class="sau-summary">
    <span>作品概览</span>
  </div>
</template>

<style scoped>
.sau-summary {
  padding: 8px 0;
  color: var(--ch-text-secondary, #64748b);
  font-size: 13px;
}
</style>
