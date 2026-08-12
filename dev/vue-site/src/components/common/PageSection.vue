<script setup>
defineProps({
  /** 标题栏（可选，也可只放默认 slot） */
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  /** flush：无外边距/边框，仅作语义容器 */
  flush: { type: Boolean, default: false },
  /** toolbar：店铺切换等紧凑工具条；panel：默认内容卡片 */
  tone: {
    type: String,
    default: 'panel',
    validator: (v) => ['panel', 'toolbar'].includes(v),
  },
})
</script>

<template>
  <section
    class="page-section"
    :class="{
      'page-section--flush': flush,
      'page-section--toolbar': !flush && tone === 'toolbar',
    }"
  >
    <header v-if="title || $slots.header || $slots.actions" class="page-section__head">
      <slot name="header">
        <div class="page-section__titles">
          <h4 v-if="title" class="page-section__title">{{ title }}</h4>
          <p v-if="description" class="page-section__desc">{{ description }}</p>
        </div>
      </slot>
      <div v-if="$slots.actions" class="page-section__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="page-section__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.page-section {
  margin-bottom: 12px;
  padding: 16px 18px 18px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-md);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
}

.page-section--toolbar {
  padding: 12px 16px;
  background: linear-gradient(180deg, #fbfcfe 0%, var(--ch-surface) 100%);
}

.page-section--toolbar .page-section__head {
  margin-bottom: 10px;
}

.page-section--flush {
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.page-section__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--ch-border);
}

.page-section--toolbar .page-section__head {
  padding-bottom: 0;
  border-bottom: 0;
}

.page-section__titles {
  min-width: 0;
}

.page-section__title {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--ch-text);
  letter-spacing: -0.01em;
}

.page-section__desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--ch-text-muted);
}

.page-section__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.page-section__body {
  min-width: 0;
}
</style>
