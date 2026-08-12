<script setup>
defineProps({
  /** 内容区是否贴边（AI 生图等全屏页） */
  flush: { type: Boolean, default: false },
})
</script>

<template>
  <div class="page-scroll" :class="{ 'page-scroll--flush': flush }">
    <div v-if="$slots.header" class="page-scroll__header">
      <slot name="header" />
    </div>
    <div class="page-scroll__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.page-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-scroll__header {
  flex-shrink: 0;
}

.page-scroll__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
}

.page-scroll--flush .page-scroll__body {
  overflow: hidden;
}
</style>
