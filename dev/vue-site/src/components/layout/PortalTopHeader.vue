<script setup>
import { Bell, Fold, Menu } from '@element-plus/icons-vue'
import WarehouseScopePanel from '@/components/warehouse/WarehouseScopePanel.vue'

defineProps({
  pageTitle: { type: String, default: 'CrossHub' },
  portalLabel: { type: String, default: '' },
  isMobile: { type: Boolean, default: false },
  isWarehouse: { type: Boolean, default: false },
  isSauModule: { type: Boolean, default: false },
})

const emit = defineEmits(['open-mobile-menu', 'toggle-sau-collapse'])
</script>

<template>
  <el-header class="portal-top-header">
    <div class="portal-top-header__leading">
      <el-button
        v-if="isMobile"
        class="portal-top-header__menu-toggle"
        :icon="Menu"
        circle
        @click="emit('open-mobile-menu')"
      />
      <div class="portal-top-header__title">
        <p class="portal-top-header__eyebrow">
          <template v-if="isWarehouse">
            <WarehouseScopePanel variant="inline" />
          </template>
          <template v-else>{{ portalLabel }}</template>
        </p>
        <div class="portal-top-header__title-row">
          <h2>{{ pageTitle }}</h2>
          <button
            v-if="isSauModule"
            type="button"
            class="portal-top-header__sau-btn"
            title="收起/展开二级导航"
            @click="emit('toggle-sau-collapse')"
          >
            <el-icon><Fold /></el-icon>
          </button>
        </div>
      </div>
    </div>
    <div class="portal-top-header__actions">
      <el-button :icon="Bell" circle class="portal-top-header__icon-btn" />
    </div>
  </el-header>
</template>

<style scoped>
.portal-top-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 24px;
  background: color-mix(in srgb, var(--ch-surface) 92%, transparent);
  border-bottom: 1px solid var(--ch-border);
  box-shadow: var(--ch-shadow-header);
  backdrop-filter: blur(10px);
}

.portal-top-header__leading {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.portal-top-header__menu-toggle {
  flex-shrink: 0;
}

.portal-top-header__title {
  min-width: 0;
}

.portal-top-header__eyebrow {
  margin: 0 0 2px;
  font-size: 11px;
  font-weight: 500;
  color: var(--ch-text-muted);
  letter-spacing: 0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.portal-top-header__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.portal-top-header h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--ch-text);
}

.portal-top-header__sau-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: var(--ch-radius-sm);
  background: transparent;
  color: var(--ch-text-muted);
  cursor: pointer;
  flex-shrink: 0;
  font-size: 18px;
  line-height: 1;
}

.portal-top-header__sau-btn:hover {
  color: var(--ch-text);
  background: var(--ch-surface-muted);
}

.portal-top-header__actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.portal-top-header__icon-btn {
  font-size: 13px;
}

@media (max-width: 767px) {
  .portal-top-header {
    padding: 0 12px;
    padding-left: max(12px, env(safe-area-inset-left));
    padding-right: max(12px, env(safe-area-inset-right));
  }

  .portal-top-header h2 {
    font-size: 15px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
