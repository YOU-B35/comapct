<script setup>
defineProps({
  work: { type: Object, default: null },
})
defineEmits(['close'])
</script>

<template>
  <el-drawer :model-value="!!work" title="作品详情" size="420px" @close="$emit('close')">
    <pre v-if="work" class="sau-detail">{{ work }}</pre>
  </el-drawer>
</template>

<style scoped>
.sau-detail {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
}
</style>
