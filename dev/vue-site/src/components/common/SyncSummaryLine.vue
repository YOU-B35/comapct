<script setup>
defineProps({
  summaryText: { type: String, default: '' },
})
defineEmits(['open-history'])
</script>

<template>
  <div class="sync-summary-line">
    <el-text v-if="summaryText" size="small" type="info">{{ summaryText }}</el-text>
    <el-button link type="primary" size="small" @click="$emit('open-history')">同步记录</el-button>
  </div>
</template>

<style scoped>
.sync-summary-line {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
</style>
