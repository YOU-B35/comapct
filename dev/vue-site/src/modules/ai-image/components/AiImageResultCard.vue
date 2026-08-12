<script setup>
defineProps({
  item: { type: Object, required: true },
})
defineEmits(['preview', 'copy', 'download', 'edit', 'share', 'remove'])
</script>

<template>
  <div class="ai-card">
    <button type="button" class="ai-card__thumb" @click="$emit('preview', item)">
      <img v-if="item.url" :src="item.url" :alt="item.prompt || 'ai'" />
      <span v-else class="ai-card__empty">无图</span>
    </button>
    <div class="ai-card__body">
      <p class="ai-card__prompt">{{ item.prompt || '（无提示词）' }}</p>
      <div class="ai-card__actions">
        <el-button link type="primary" size="small" @click="$emit('copy', item)">复制</el-button>
        <el-button link type="primary" size="small" @click="$emit('download', item)">下载</el-button>
        <el-button link type="primary" size="small" @click="$emit('edit', item)">编辑</el-button>
        <el-button link type="primary" size="small" @click="$emit('share', item)">分享</el-button>
        <el-button link type="danger" size="small" @click="$emit('remove', item)">删除</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--ch-border, #e5e7eb);
  border-radius: var(--ch-radius-md, 10px);
  background: var(--ch-surface, #fff);
}
.ai-card__thumb {
  flex: 0 0 96px;
  width: 96px;
  height: 96px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  overflow: hidden;
  background: var(--ch-layout-bg, #f3f5f9);
  cursor: pointer;
}
.ai-card__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ai-card__empty {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--ch-text-secondary, #64748b);
  font-size: 12px;
}
.ai-card__body {
  flex: 1;
  min-width: 0;
}
.ai-card__prompt {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--ch-text, #1c2434);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ai-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
