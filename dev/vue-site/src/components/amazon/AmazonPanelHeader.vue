<script setup>
import PanelHeader from '@/components/common/PanelHeader.vue'
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

defineEmits(['action', 'secondaryAction', 'open-history'])
</script>

<template>
  <PanelHeader
    :title="title"
    :description="description"
    :synced-at="syncedAt"
    synced-prefix="同步于"
    :action-label="actionLabel"
    :secondary-action-label="secondaryActionLabel"
    :loading="loading"
    :secondary-loading="secondaryLoading"
    :show-action-icon="false"
    @action="$emit('action')"
    @secondary-action="$emit('secondaryAction')"
  >
    <template #actions>
      <SyncSummaryLine
        v-if="summaryText"
        :summary-text="summaryText"
        @open-history="$emit('open-history')"
      />
      <el-button
        v-if="secondaryActionLabel"
        size="small"
        :loading="secondaryLoading"
        @click="$emit('secondaryAction')"
      >
        {{ secondaryActionLabel }}
      </el-button>
      <el-button
        v-if="actionLabel"
        size="small"
        type="primary"
        :loading="loading"
        @click="$emit('action')"
      >
        {{ actionLabel }}
      </el-button>
      <slot name="actions" />
    </template>
  </PanelHeader>
</template>
