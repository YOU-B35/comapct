<script setup>
defineProps({
  menus: {
    type: Array,
    default: () => [],
  },
  activeMenu: {
    type: String,
    default: '',
  },
  openedMenus: {
    type: Array,
    default: () => [],
  },
  menuRenderKey: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <el-menu
    :key="menuRenderKey"
    :default-active="activeMenu"
    :default-openeds="openedMenus"
    unique-opened
    router
    class="portal-sidebar-menu"
  >
    <template v-for="item in menus" :key="item.code || item.index">
      <el-sub-menu v-if="item.children?.length" :index="item.code">
        <template #title>
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </template>
        <el-menu-item
          v-for="child in item.children"
          :key="child.index"
          :index="child.index"
        >
          <el-icon><component :is="child.icon" /></el-icon>
          <span>{{ child.label }}</span>
        </el-menu-item>
      </el-sub-menu>
      <el-menu-item v-else :index="item.index">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </template>
  </el-menu>
</template>

<style scoped>
.portal-sidebar-menu {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 10px 12px;
  border-right: none;
  background: transparent;
}

.portal-sidebar-menu :deep(.el-menu-item),
.portal-sidebar-menu :deep(.el-sub-menu__title) {
  position: relative;
  height: 40px;
  margin-bottom: 2px;
  border-radius: 7px;
  color: var(--ch-sidebar-text);
  font-size: 13.5px;
  font-weight: 500;
  line-height: 40px;
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.portal-sidebar-menu :deep(.el-menu-item:hover),
.portal-sidebar-menu :deep(.el-sub-menu__title:hover) {
  color: var(--ch-sidebar-text-hover);
  background: var(--ch-surface-muted);
}

.portal-sidebar-menu :deep(.el-menu-item.is-active) {
  color: var(--ch-sidebar-text-active);
  font-weight: 600;
  background: var(--ch-sidebar-active-bg);
}

.portal-sidebar-menu :deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  bottom: 9px;
  width: 2.5px;
  border-radius: 0 2px 2px 0;
  background: var(--ch-primary);
}

.portal-sidebar-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: var(--ch-sidebar-text-active);
  font-weight: 600;
}

.portal-sidebar-menu :deep(.el-menu) {
  background: transparent;
  border: none;
}

.portal-sidebar-menu :deep(.el-menu-item .el-icon),
.portal-sidebar-menu :deep(.el-sub-menu__title .el-icon) {
  font-size: 16px;
  color: inherit;
}

.portal-sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  padding-left: 44px !important;
  min-width: auto;
  height: 36px;
  line-height: 36px;
  font-size: 13px;
  font-weight: 450;
}

.portal-sidebar-menu :deep(.el-sub-menu__icon-arrow) {
  color: var(--ch-text-muted);
}
</style>
