<script setup>
defineProps({
  title: { type: String, default: '数据分析' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <el-card shadow="never" class="analytics-strip">
    <template #header>
      <div class="analytics-strip__header">
        <div>
          <strong>{{ title }}</strong>
          <el-text v-if="hint" type="info" size="small" class="analytics-strip__hint">
            {{ hint }}
          </el-text>
        </div>
        <slot name="actions" />
      </div>
    </template>
    <div class="analytics-strip__body">
      <slot />
    </div>
  </el-card>
</template>

<style scoped>
.analytics-strip {
  margin-bottom: 16px;
}

.analytics-strip__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.analytics-strip__hint {
  display: block;
  margin-top: 4px;
}

.analytics-strip__body {
  display: grid;
  gap: 12px;
}

.analytics-strip__body :deep(.chart-cell) {
  min-width: 0;
}
</style>
