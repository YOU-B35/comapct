<script setup>
import { SwitchButton } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '' },
  role: { type: String, default: '' },
  meta: { type: String, default: '' },
  initial: { type: String, default: 'U' },
  isWarehouse: { type: Boolean, default: false },
  warehouseLabels: { type: Array, default: () => [] },
})

const emit = defineEmits(['logout'])

function onCommand(command) {
  if (command === 'logout') emit('logout')
}
</script>

<template>
  <div class="portal-user-panel">
    <el-dropdown
      trigger="click"
      placement="top-start"
      :show-arrow="false"
      popper-class="portal-user-panel-popper"
      @command="onCommand"
    >
      <div class="portal-user-panel__trigger">
        <el-avatar :size="36" class="portal-user-panel__avatar">{{ initial }}</el-avatar>
        <div class="portal-user-panel__body">
          <span class="portal-user-panel__role">{{ role }}</span>
          <p class="portal-user-panel__name" :title="title">{{ title }}</p>
          <p
            v-if="isWarehouse && warehouseLabels.length"
            class="portal-user-panel__scope"
            :title="warehouseLabels.join('、')"
          >
            {{ warehouseLabels.join('、') }}
          </p>
        </div>
        <el-icon class="portal-user-panel__chevron"><SwitchButton /></el-icon>
      </div>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item disabled class="portal-user-panel-menu__head">
            <div class="portal-user-panel-menu__head-inner">
              <p class="portal-user-panel-menu__name">{{ title }}</p>
              <p class="portal-user-panel-menu__meta">{{ meta }}</p>
              <div v-if="isWarehouse && warehouseLabels.length" class="portal-user-panel-menu__tags">
                <el-tag
                  v-for="name in warehouseLabels"
                  :key="name"
                  size="small"
                  effect="plain"
                  type="primary"
                >
                  {{ name }}
                </el-tag>
              </div>
            </div>
          </el-dropdown-item>
          <el-dropdown-item divided command="logout">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style scoped>
.portal-user-panel {
  padding: 10px 12px 12px;
  border-top: 1px solid var(--ch-border);
  flex-shrink: 0;
  background: var(--ch-surface);
}

.portal-user-panel__trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.portal-user-panel__trigger:hover {
  border-color: var(--ch-primary-muted);
  background: var(--ch-primary-soft);
  box-shadow: var(--ch-shadow-xs);
}

.portal-user-panel__body {
  flex: 1;
  min-width: 0;
}

.portal-user-panel__avatar {
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--ch-primary) 0%, #4080ff 100%);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}

.portal-user-panel__role {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--ch-radius-xs);
  font-size: 10px;
  font-weight: 500;
  line-height: 1.6;
  color: var(--ch-primary);
  background: var(--ch-primary-soft);
}

.portal-user-panel__name {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
  color: var(--ch-text);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  word-break: break-all;
}

.portal-user-panel__scope {
  margin: 2px 0 0;
  font-size: 11px;
  line-height: 1.35;
  color: var(--ch-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.portal-user-panel__chevron {
  flex-shrink: 0;
  font-size: 15px;
  color: var(--ch-text-muted);
  transition: color 0.15s ease;
}

.portal-user-panel__trigger:hover .portal-user-panel__chevron {
  color: var(--ch-primary);
}
</style>

<style>
.portal-user-panel-popper .portal-user-panel-menu__head {
  height: auto !important;
  padding: 8px 16px 4px !important;
  cursor: default !important;
  opacity: 1 !important;
}

.portal-user-panel-popper .portal-user-panel-menu__head-inner {
  max-width: 200px;
}

.portal-user-panel-popper .portal-user-panel-menu__name {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.45;
  color: var(--ch-text);
  word-break: break-all;
}

.portal-user-panel-popper .portal-user-panel-menu__meta {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--ch-text-muted);
  word-break: break-all;
}

.portal-user-panel-popper .portal-user-panel-menu__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.portal-user-panel-popper .el-dropdown-menu__item:not(.is-disabled) {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
