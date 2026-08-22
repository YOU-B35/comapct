<script setup>
import { formatUtc8 } from '@/utils/time'
import { Refresh } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  syncedAt: { type: String, default: '' },
  syncedPrefix: { type: String, default: '最近同步' },
  actionLabel: { type: String, default: '' },
  secondaryActionLabel: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  secondaryLoading: { type: Boolean, default: false },
  /** 主按钮默认带刷新图标；传 false 可关闭 */
  showActionIcon: { type: Boolean, default: true },
})

const emit = defineEmits(['action', 'secondaryAction'])
</script>

<template>
  <div class="panel-header">
    <div class="panel-header__main">
      <h4 class="panel-header__title">{{ title }}</h4>
      <p v-if="description" class="panel-header__desc">{{ description }}</p>
    </div>
    <div class="panel-header__side">
      <span v-if="syncedAt" class="panel-header__sync">
        <i class="panel-header__sync-dot" aria-hidden="true" />
        {{ syncedPrefix }} {{ formatUtc8(syncedAt) }}
      </span>
      <slot name="actions">
        <el-button
          v-if="secondaryActionLabel"
          size="small"
          :loading="secondaryLoading"
          @click="emit('secondaryAction')"
        >
          {{ secondaryActionLabel }}
        </el-button>
        <el-button
          v-if="actionLabel"
          size="small"
          type="primary"
          :icon="showActionIcon ? Refresh : undefined"
          :loading="loading"
          @click="emit('action')"
        >
          {{ actionLabel }}
        </el-button>
      </slot>
    </div>
  </div>
</template>

<style scoped>
.panel-header {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 14px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--ch-border);
}

.panel-header__main {
  min-width: 0;
  flex: 1;
}

.panel-header__title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--ch-text);
  line-height: 1.35;
}

.panel-header__desc {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ch-text-muted);
}

.panel-header__side {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
  align-items: center;
  flex-shrink: 0;
}

.panel-header__sync {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #d5efe6;
  background: #f0faf6;
  color: #0a6b4d;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.panel-header__sync-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ch-success);
}
</style>
