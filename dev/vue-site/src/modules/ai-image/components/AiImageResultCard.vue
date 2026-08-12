<script setup>
import { DocumentCopy, Download, EditPen, MagicStick, Delete, Star, StarFilled } from '@element-plus/icons-vue'

defineProps({
  item: { type: Object, required: true },
})
defineEmits(['preview', 'copy', 'download', 'edit', 'optimize', 'favorite', 'remove'])
</script>

<template>
  <article class="ai-card">
    <button
      type="button"
      class="ai-card__media"
      :title="item.prompt || '预览大图'"
      @click="$emit('preview', item)"
    >
      <img v-if="item.url" :src="item.url" :alt="item.prompt || 'ai'" loading="lazy" />
      <span v-else class="ai-card__empty">无图</span>
    </button>

    <div class="ai-card__actions">
      <el-tooltip :content="item.favorite ? '取消收藏' : '收藏到收藏夹'" placement="top" :show-after="200">
        <button
          type="button"
          class="ai-card__btn"
          :class="{ 'ai-card__btn--fav': item.favorite }"
          :aria-label="item.favorite ? '取消收藏' : '收藏到收藏夹'"
          @click.stop="$emit('favorite', item)"
        >
          <el-icon :size="16">
            <StarFilled v-if="item.favorite" />
            <Star v-else />
          </el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="复制提示词" placement="top" :show-after="200">
        <button type="button" class="ai-card__btn" aria-label="复制提示词" @click.stop="$emit('copy', item)">
          <el-icon :size="16"><DocumentCopy /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="下载图片" placement="top" :show-after="200">
        <button type="button" class="ai-card__btn" aria-label="下载图片" @click.stop="$emit('download', item)">
          <el-icon :size="16"><Download /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="编辑提示词" placement="top" :show-after="200">
        <button type="button" class="ai-card__btn" aria-label="编辑提示词" @click.stop="$emit('edit', item)">
          <el-icon :size="16"><EditPen /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="优化（图生图）" placement="top" :show-after="200">
        <button type="button" class="ai-card__btn" aria-label="优化（图生图）" @click.stop="$emit('optimize', item)">
          <el-icon :size="16"><MagicStick /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="删除" placement="top" :show-after="200">
        <button type="button" class="ai-card__btn ai-card__btn--danger" aria-label="删除" @click.stop="$emit('remove', item)">
          <el-icon :size="16"><Delete /></el-icon>
        </button>
      </el-tooltip>
    </div>
  </article>
</template>

<style scoped>
.ai-card {
  display: flex;
  flex-direction: column;
  width: 100%;
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 18px;
  background:
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  overflow: hidden;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 8px 18px rgba(15, 23, 42, 0.06),
    0 2px 4px rgba(15, 23, 42, 0.04);
  transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}

.ai-card:hover {
  border-color: #bfdbfe;
  transform: translateY(-4px);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.95) inset,
    0 18px 36px rgba(37, 99, 235, 0.16),
    0 6px 12px rgba(15, 23, 42, 0.08);
}

.ai-card__media {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  padding: 0;
  border: 0;
  background:
    radial-gradient(120% 80% at 50% 0%, #e2e8f0 0%, #f1f5f9 55%, #e8eef7 100%);
  cursor: zoom-in;
  overflow: hidden;
}

.ai-card__media::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.35);
}

.ai-card__media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.3s ease;
}

.ai-card:hover .ai-card__media img {
  transform: scale(1.04);
}

.ai-card__empty {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  color: #94a3b8;
  font-size: 13px;
}

.ai-card__actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}

.ai-card__btn {
  width: 34px;
  height: 34px;
  display: inline-grid;
  place-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.ai-card__btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
  transform: translateY(-1px);
}

.ai-card__btn--danger {
  color: #dc2626;
  background: #fee2e2;
  border-color: #fecaca;
}

.ai-card__btn--danger:hover {
  color: #b91c1c;
  background: #fecaca;
  border-color: #fca5a5;
}

.ai-card__btn--fav {
  color: #eab308;
  border-color: #fde68a;
  background: #fffbeb;
}

.ai-card__btn--fav:hover {
  color: #ca8a04;
  background: #fef3c7;
  border-color: #fcd34d;
}
</style>
