<script setup>
import { Refresh, Setting } from '@element-plus/icons-vue'

defineProps({
  refreshing: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh', 'settings', 'agent', 'guide'])
</script>

<template>
  <div class="ai-toolbar">
    <div class="ai-toolbar__left">
      <span class="ai-toolbar__title">GPT Image Playground</span>
      <span class="ai-toolbar__badge">NEW</span>
      <el-button link type="primary" class="ai-toolbar__guide" @click="emit('guide')">操作指南</el-button>
    </div>
    <div class="ai-toolbar__right">
      <el-button :icon="Refresh" :loading="refreshing" @click="emit('refresh')">刷新</el-button>
      <el-button class="ai-toolbar__agent" @click="emit('agent')">Agent</el-button>
      <el-button :icon="Setting" circle title="设置" @click="emit('settings')" />
    </div>
  </div>
</template>

<style scoped>
.ai-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 44px;
  padding: 8px 12px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
}

.ai-toolbar__left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.ai-toolbar__title {
  font-size: 14px;
  font-weight: 650;
  color: var(--ch-text);
}

.ai-toolbar__badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--ch-primary-soft);
  color: var(--ch-primary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.ai-toolbar__guide {
  margin-left: 4px;
  font-size: 13px;
}

.ai-toolbar__right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.ai-toolbar__agent {
  border-color: var(--ch-primary-muted) !important;
  color: var(--ch-primary) !important;
  background: var(--ch-primary-soft) !important;
  border-radius: 8px !important;
  font-weight: 650;
}

.ai-toolbar__right :deep(.el-button.is-circle) {
  border-color: var(--ch-border);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
}

.ai-toolbar__right :deep(.el-button.is-circle:hover) {
  border-color: var(--ch-primary-muted);
  color: var(--ch-primary);
  background: var(--ch-primary-soft);
}
</style>
