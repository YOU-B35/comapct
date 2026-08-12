<script setup>
import PanelHeader from '@/components/common/PanelHeader.vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  syncedAt: { type: String, default: '' },
  actionLabel: { type: String, default: '刷新' },
  loading: { type: Boolean, default: false },
})

defineEmits(['action'])
</script>

<template>
  <PanelHeader
    :title="title"
    :description="description"
    :synced-at="syncedAt"
    :action-label="actionLabel"
    :loading="loading"
    @action="$emit('action')"
  />
</template>
