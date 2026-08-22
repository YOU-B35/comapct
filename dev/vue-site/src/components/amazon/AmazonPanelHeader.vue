<script setup>
import { formatUtc8 } from '@/utils/time'
import SyncSummaryLine from '@/components/common/SyncSummaryLine.vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
  secondaryActionLabel: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  secondaryLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['action', 'secondaryAction', 'open-history'])
</script>

<template>
  <div class="panel-header">
    <div class="panel-header__main">
      <div class="panel-header__title">{{ title }}</div>
      <div v-if="description" class="panel-header__desc">{{ description }}</div>
    </div>
    <div class="panel-header__side">
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
          :loading="loading"
          @click="emit('action')"
        >
          {{ actionLabel }}
        </el-button>
      </slot>
      <SyncSummaryLine
        v-if="summaryText"
        :summary-text="summaryText"
        @open-history="emit('open-history')"
      />
      <el-text v-else-if="syncedAt" size="small" type="info">最近同步 {{ formatUtc8(syncedAt) }}</el-text>
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
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.panel-header__side {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: center;
}

.panel-header__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.panel-header__desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
