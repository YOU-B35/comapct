<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed } from 'vue'
import { ArrowDown, ArrowUp, CircleCheck, CircleClose, Loading, Refresh, Warning } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { usePlatformSyncStore } from '@/stores/platformSync'
import { canUseOpsManualSync, OPS_SYNC_READONLY_HINT } from '@/utils/opsSyncPolicy'

const auth = useAuthStore()
const syncStore = usePlatformSyncStore()

const visible = computed(() => auth.backendLinked && !auth.isWarehouse)
const allowManualSync = computed(() => canUseOpsManualSync())

function statusType(status) {
  if (status === 'success' || status === 'partial') return 'success'
  if (status === 'syncing') return 'warning'
  if (status === 'failed' || status === 'empty') return 'danger'
  if (status === 'skipped') return 'info'
  return 'info'
}

function statusLabel(status) {
  if (status === 'success') return '已同步'
  if (status === 'partial') return '部分成功'
  if (status === 'syncing') return '同步中'
  if (status === 'failed') return '失败'
  if (status === 'empty') return '无数据'
  if (status === 'skipped') return '跳过'
  return '待同步'
}

function statusIcon(status) {
  if (status === 'success' || status === 'partial') return CircleCheck
  if (status === 'syncing') return Loading
  if (status === 'failed' || status === 'empty') return CircleClose
  if (status === 'skipped') return Warning
  return Loading
}
</script>

<template>
  <section v-if="visible" class="sync-log-panel">
    <button type="button" class="sync-log-panel__head" @click="syncStore.expanded = !syncStore.expanded">
      <div class="sync-log-panel__title-wrap">
        <strong>数据同步</strong>
        <el-text size="small" type="info">{{ syncStore.summaryText }}</el-text>
      </div>
      <el-icon class="sync-log-panel__toggle">
        <component :is="syncStore.expanded ? ArrowDown : ArrowUp" />
      </el-icon>
    </button>

    <div v-show="syncStore.expanded" class="sync-log-panel__body">
      <div v-if="syncStore.scheduleText" class="sync-log-panel__schedule">
        <el-text size="small" type="info">计划：{{ syncStore.scheduleText }}</el-text>
        <el-text size="small" type="info">范围：Temu · 速卖通 · Amazon</el-text>
        <el-tag
          v-if="syncStore.platformSyncStatus"
          size="small"
          effect="plain"
          :type="syncStore.platformSyncStatus.agent_online ? 'success' : 'info'"
        >
          运维节点{{ syncStore.platformSyncStatus.agent_online ? '在线' : '离线' }}
        </el-tag>
        <div
          v-for="row in syncStore.platformStatusRows"
          :key="row.key"
          class="sync-log-panel__platform-row"
        >
          <el-text size="small" :type="row.hasError ? 'danger' : 'info'">
            {{ row.label }}：{{ row.hasError ? (row.errorMessage || '同步失败') : row.lastJobText }}
          </el-text>
        </div>
        <el-text
          v-if="syncStore.platformSyncStatus?.data_report_time"
          size="small"
          type="info"
        >
          Temu 数据日：{{ syncStore.platformSyncStatus.data_report_time }}
        </el-text>
        <el-text v-if="!allowManualSync" size="small" type="info">
          {{ OPS_SYNC_READONLY_HINT }}
        </el-text>
      </div>

      <div v-if="allowManualSync" class="sync-log-panel__actions">
        <el-button
          size="small"
          text
          :icon="Refresh"
          :loading="syncStore.running"
          @click="syncStore.retry(auth)"
        >
          重新同步
        </el-button>
        <el-text v-if="syncStore.lastFinishedAt" size="small" type="info">
          {{ formatUtc8(syncStore.lastFinishedAt) }}
        </el-text>
      </div>
      <div v-else-if="syncStore.lastFinishedAt" class="sync-log-panel__actions">
        <el-text size="small" type="info">
          最近状态更新：{{ formatUtc8(syncStore.lastFinishedAt) }}
        </el-text>
      </div>

      <el-text
        v-if="allowManualSync && syncStore.inCooldown && !syncStore.running"
        size="small"
        type="info"
        class="sync-log-panel__cooldown"
      >
        {{ syncStore.cooldownHint }}（可点「重新同步」强制刷新）
      </el-text>

      <el-alert
        v-if="syncStore.lastError"
        :type="syncStore.platformSyncStatus?.has_error ? 'error' : 'warning'"
        :closable="false"
        show-icon
        :title="syncStore.lastError"
        class="sync-log-panel__alert"
      />

      <el-empty
        v-if="!syncStore.hasItems && !syncStore.running"
        description="暂无绑定店铺"
        :image-size="48"
      />

      <ul v-else class="sync-log-list">
        <li v-for="item in syncStore.items" :key="item.key" class="sync-log-item">
          <div class="sync-log-item__main">
            <el-icon class="sync-log-item__icon" :class="`is-${item.status}`">
              <component :is="statusIcon(item.status)" />
            </el-icon>
            <div class="sync-log-item__text">
              <span class="sync-log-item__name" :title="item.storeName">{{ item.storeName }}</span>
              <span class="sync-log-item__platform">{{ item.platformLabel }}</span>
            </div>
            <el-tag :type="statusType(item.status)" size="small" effect="plain">
              {{ statusLabel(item.status) }}
            </el-tag>
          </div>
          <p v-if="item.message" class="sync-log-item__message">{{ item.message }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.sync-log-panel {
  margin: 8px 8px 0;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-md);
  background: var(--ch-surface);
  overflow: hidden;
  flex-shrink: 0;
}

.sync-log-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.sync-log-panel__title-wrap {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.sync-log-panel__title-wrap strong {
  font-size: 13px;
  color: var(--ch-text);
}

.sync-log-panel__toggle {
  flex-shrink: 0;
  color: var(--ch-text-muted);
}

.sync-log-panel__body {
  padding: 0 10px 10px;
  border-top: 1px solid var(--ch-border);
}

.sync-log-panel__schedule {
  display: grid;
  gap: 4px;
  padding-top: 8px;
}

.sync-log-panel__platform-row {
  min-width: 0;
}

.sync-log-panel__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 8px;
}

.sync-log-panel__cooldown {
  display: block;
  margin-top: 6px;
  line-height: 1.45;
}

.sync-log-panel__alert {
  margin-top: 8px;
}

.sync-log-list {
  display: grid;
  gap: 8px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  max-height: 220px;
  overflow-y: auto;
}

.sync-log-item {
  padding: 8px;
  border-radius: var(--ch-radius-sm);
  background: var(--ch-fill-color-light, #f5f7fa);
}

.sync-log-item__main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sync-log-item__icon {
  flex-shrink: 0;
  font-size: 14px;
}

.sync-log-item__icon.is-success {
  color: var(--el-color-success);
}

.sync-log-item__icon.is-failed,
.sync-log-item__icon.is-empty {
  color: var(--el-color-danger);
}

.sync-log-item__icon.is-syncing {
  color: var(--el-color-warning);
  animation: spin 1s linear infinite;
}

.sync-log-item__icon.is-skipped {
  color: var(--el-color-info);
}

.sync-log-item__text {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 2px;
}

.sync-log-item__name {
  font-size: 12px;
  font-weight: 500;
  color: var(--ch-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sync-log-item__platform {
  font-size: 11px;
  color: var(--ch-text-muted);
}

.sync-log-item__message {
  margin: 6px 0 0 22px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--ch-text-muted);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
