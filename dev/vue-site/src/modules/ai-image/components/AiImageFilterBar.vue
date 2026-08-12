<script setup>
defineProps({
  collection: { type: String, default: 'all' },
})
defineEmits(['update:collection'])
</script>

<template>
  <div class="ai-filter">
    <el-radio-group
      :model-value="collection"
      size="small"
      @update:model-value="$emit('update:collection', $event)"
    >
      <el-radio-button value="all">全部</el-radio-button>
      <el-radio-button value="favorites">收藏</el-radio-button>
    </el-radio-group>
  </div>
</template>

<style scoped>
.ai-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 8px 0 12px;
}
</style>
