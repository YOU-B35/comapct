<script setup>
import { computed } from 'vue'
import { resolveAgentPresence } from '@/utils/agentPresence'

const props = defineProps({
  tenantOnline: { type: Boolean, default: false },
  localProcessOnline: { type: Boolean, default: false },
  /** 紧凑：只显示标签，不显示说明段落 */
  compact: { type: Boolean, default: false },
  /** 是否展示不匹配黄条 */
  showMismatchAlert: { type: Boolean, default: true },
})

const presence = computed(() =>
  resolveAgentPresence({
    tenantOnline: props.tenantOnline,
    localProcessOnline: props.localProcessOnline,
  }),
)

defineExpose({ presence })
</script>

<template>
  <div class="agent-presence-status">
    <div class="status-row">
      <el-tag :type="presence.primaryType" effect="plain">
        {{ presence.primaryLabel }}
      </el-tag>
      <el-tag :type="presence.localType" effect="plain">
        {{ presence.localLabel }}
      </el-tag>
      <slot name="extra" />
    </div>

    <el-alert
      v-if="showMismatchAlert && presence.tenantMismatch"
      type="warning"
      show-icon
      :closable="false"
      class="mismatch-alert"
      :title="presence.mismatchTitle"
      :description="presence.mismatchDescription"
    />

    <p v-if="!compact && !presence.tenantOnline && !presence.tenantMismatch" class="hint">
      请联系运维确认肉机已启动 CrossHub-Sync-Helper.exe；数据由服务端定时下发，运营网页不提供助手下载。
    </p>
  </div>
</template>

<style scoped>
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.mismatch-alert {
  margin-top: 12px;
}

.hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
</style>
