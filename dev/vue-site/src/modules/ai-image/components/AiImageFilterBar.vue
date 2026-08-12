<script setup>
defineProps({
  collection: { type: String, default: 'all' },
  keyword: { type: String, default: '' },
})
defineEmits(['update:collection', 'update:keyword'])
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
    <el-input
      :model-value="keyword"
      clearable
      size="small"
      placeholder="搜索提示词"
      class="ai-filter__kw"
      @update:model-value="$emit('update:keyword', $event)"
    />
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
.ai-filter__kw {
  width: min(280px, 100%);
}
</style>
