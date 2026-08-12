<script setup>
import { computed } from 'vue'
import { summarizeAmazonByStore, summarizeAmazonDaily } from '@/utils/amazon'
import { resolveStoreAssignee } from '@/utils/storeAssignment'
import AssigneeTag from '@/components/common/AssigneeTag.vue'

const props = defineProps({
  workflow: { type: Object, default: () => ({}) },
  stores: { type: Array, default: () => [] },
  assigneeMap: { type: Object, default: () => ({}) },
  showStoreList: { type: Boolean, default: true },
})

const emit = defineEmits(['navigate'])

const daily = computed(() => summarizeAmazonDaily(props.workflow))
const storeSummaries = computed(() => summarizeAmazonByStore(props.workflow, props.stores))

function stepType(item) {
  if (!item.count) return 'success'
  return item.urgent ? 'danger' : 'warning'
}
</script>

<template>
  <div class="daily-overview">
    <div class="progress-head">
      <div>
        <div class="progress-title">今日运营工作台</div>
        <div class="progress-hint">
          {{ daily.progressText }}
          <template v-if="daily.totalPending"> · 还有 {{ daily.totalPending }} 项待处理</template>
        </div>
      </div>
      <el-progress
        type="circle"
        :percentage="daily.progressPercent"
        :width="72"
        :status="daily.totalPending ? undefined : 'success'"
      />
    </div>

    <div class="checklist">
      <button
        v-for="(item, index) in daily.checklist"
        :key="item.key"
        type="button"
        class="check-item"
        :class="{ 'is-done': !item.count, 'is-urgent': item.urgent }"
        @click="emit('navigate', item.tab)"
      >
        <span class="check-step">{{ index + 1 }}</span>
        <span class="check-body">
          <strong>{{ item.label }}</strong>
          <small>{{ item.hint }}</small>
        </span>
        <el-badge v-if="item.count" :value="item.count" class="check-badge" />
        <el-tag v-else-if="item.urgent" type="danger" size="small" effect="plain">紧急</el-tag>
        <el-tag v-else :type="stepType(item)" size="small" effect="plain">{{ item.count }} 待办</el-tag>
      </button>
    </div>

    <el-table
      v-if="showStoreList && storeSummaries.length > 1"
      :data="storeSummaries"
      size="small"
      class="store-table"
    >
      <el-table-column label="店铺" min-width="140">
        <template #default="{ row }">
          <strong>{{ row.store.storeName }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="96">
        <template #default="{ row }">
          <AssigneeTag :name="resolveStoreAssignee(row.store.id, assigneeMap)" />
        </template>
      </el-table-column>
      <el-table-column label="待办合计" width="90" align="center">
        <template #default="{ row }">
          <el-text :type="row.totalPending ? 'danger' : 'success'" size="small">
            {{ row.totalPending }}
          </el-text>
        </template>
      </el-table-column>
      <el-table-column label="进度" min-width="120">
        <template #default="{ row }">
          <el-progress
            :percentage="row.progressPercent"
            :stroke-width="6"
            :status="row.totalPending ? undefined : 'success'"
          />
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.daily-overview {
  display: grid;
  gap: 20px;
}

.progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: var(--ch-radius-md);
  background: linear-gradient(180deg, #f8faff 0%, #fff 70%);
  border: 1px solid var(--ch-border);
}

.progress-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ch-text);
}

.progress-hint {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ch-text-muted);
}

.checklist {
  display: grid;
  gap: 8px;
}

.check-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
  width: 100%;
  padding: 12px 14px;
  text-align: left;
  border: 1px solid var(--ch-border);
  border-radius: 8px;
  background: var(--ch-surface);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}

.check-item:hover {
  border-color: var(--ch-primary-muted);
  background: var(--ch-surface-muted);
  box-shadow: var(--ch-shadow-xs);
}

.check-item.is-done {
  opacity: 0.88;
}

.check-item.is-urgent {
  border-left: 3px solid var(--ch-error);
}

.check-step {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: var(--ch-primary);
  flex-shrink: 0;
}

.check-item.is-done .check-step {
  background: var(--ch-success);
}

.check-item.is-urgent .check-step {
  background: var(--ch-error);
}

.check-body {
  flex: 1;
  min-width: 140px;
  display: grid;
  gap: 2px;
}

.check-body strong {
  font-size: 14px;
}

.check-body small {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.check-badge :deep(.el-badge__content) {
  position: relative;
  transform: none;
}
</style>
