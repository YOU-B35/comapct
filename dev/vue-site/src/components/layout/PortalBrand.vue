<script setup>
defineProps({
  portalLabel: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <div class="portal-brand">
    <div class="portal-brand__mark" aria-hidden="true">
      <span>CH</span>
    </div>
    <div class="portal-brand__text">
      <strong>CrossHub</strong>
      <span>{{ portalLabel }}</span>
    </div>
  </div>
</template>

<style scoped>
.portal-brand {
  display: flex;
  gap: 11px;
  align-items: center;
  height: 60px;
  padding: 0 16px;
  border-bottom: 1px solid var(--ch-border);
  flex-shrink: 0;
  background: var(--ch-surface);
}

.portal-brand__mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: var(--ch-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: -0.02em;
  box-shadow: none;
}

.portal-brand__text {
  min-width: 0;
}

.portal-brand__text strong {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: var(--ch-text);
  line-height: 1.25;
  letter-spacing: -0.02em;
}

.portal-brand__text span {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  font-weight: 500;
  color: var(--ch-text-muted);
  letter-spacing: 0.02em;
}
</style>
