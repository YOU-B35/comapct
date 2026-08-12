<script setup>
import PanelHeader from '@/components/common/PanelHeader.vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  syncedAt: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

defineEmits(['action'])
</script>

<template>
  <PanelHeader
    :title="title"
    :description="description"
    :synced-at="syncedAt"
    synced-prefix="同步于"
    :action-label="actionLabel"
    :loading="loading"
    :show-action-icon="false"
    @action="$emit('action')"
  />
</template>
