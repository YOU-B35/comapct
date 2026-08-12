<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  DataAnalysis,
  DataBoard,
  HomeFilled,
  Picture,
  Upload,
  User,
} from '@element-plus/icons-vue'
import { ensureSauSession } from '@sau/utils/ensureSession'
import { useSauShellStore } from '@sau/stores/shell'

const route = useRoute()
const shell = useSauShellStore()

const booting = ref(true)
const bootError = ref('')

const basePath = computed(() => {
  const path = route.path || ''
  if (path.startsWith('/boss/sau')) return '/boss/sau'
  return '/employee/sau'
})

const navItems = computed(() => {
  const root = basePath.value
  return [
    { path: `${root}/home`, label: '首页', icon: HomeFilled },
    { path: `${root}/accounts`, label: '账号管理', icon: User },
    { path: `${root}/materials`, label: '素材管理', icon: Picture },
    { path: `${root}/publish`, label: '发布中心', icon: Upload },
    { path: `${root}/works`, label: '作品中心', icon: DataBoard },
    { path: `${root}/about`, label: '关于', icon: DataAnalysis },
  ]
})

const activeMenu = computed(() => {
  const path = route.path || ''
  const hit = navItems.value.find((item) => path === item.path || path.startsWith(`${item.path}/`))
  return hit?.path || `${basePath.value}/home`
})

onMounted(async () => {
  try {
    await ensureSauSession({ force: true })
    bootError.value = ''
  } catch (err) {
    bootError.value = err?.message || '无法连接自媒体服务'
    ElMessage.error(bootError.value)
  } finally {
    booting.value = false
  }
})
</script>

<template>
  <div class="sau-shell">
    <el-alert
      v-if="bootError"
      class="sau-shell__alert"
      type="error"
      show-icon
      :closable="false"
      :title="bootError"
      description="请确认可访问线上自媒体服务（automedia.yoto.work），且当前账号已开通自媒体权限。"
    />

    <div v-if="booting" class="sau-shell__hint">正在绑定自媒体会话…</div>

    <div v-else-if="!bootError" class="sau-shell__layout">
      <aside class="sau-shell__aside" :style="{ width: shell.asideWidth }">
        <el-menu
          :router="true"
          :default-active="activeMenu"
          :collapse="shell.isCollapse"
          class="sau-shell__menu"
        >
          <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.label }}</template>
          </el-menu-item>
        </el-menu>
      </aside>

      <main class="sau-shell__main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.sau-shell {
  display: flex;
  flex-direction: column;
  margin: -16px -20px -20px;
  height: calc(100vh - 72px);
  min-height: 480px;
  overflow: hidden;
  background: var(--ch-layout-bg);
}

.sau-shell__alert,
.sau-shell__hint {
  margin: 16px;
  flex-shrink: 0;
}

.sau-shell__layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.sau-shell__aside {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
  overflow: hidden;
  background: var(--ch-surface);
  border-right: 1px solid var(--ch-sidebar-border);
  box-shadow: none;
  transition: width 0.25s ease;
}

.sau-shell__menu {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 8px;
  border-right: none !important;
  background: transparent !important;
}

.sau-shell__menu:not(.el-menu--collapse) {
  width: 200px;
}

.sau-shell__menu :deep(.el-menu-item) {
  position: relative;
  height: 40px;
  margin-bottom: 2px;
  border-radius: 8px;
  color: var(--ch-sidebar-text);
  font-size: 13.5px;
  font-weight: 450;
  line-height: 40px;
  transition: color 0.15s ease, background 0.15s ease;
}

.sau-shell__menu :deep(.el-menu-item:hover) {
  color: var(--ch-sidebar-text-hover);
  background: var(--ch-surface-muted);
}

.sau-shell__menu :deep(.el-menu-item:hover::before) {
  display: none;
}

.sau-shell__menu :deep(.el-menu-item.is-active) {
  color: var(--ch-sidebar-text-active);
  font-weight: 600;
  background: var(--ch-sidebar-active-bg);
}

.sau-shell__menu :deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--ch-primary);
}

.sau-shell__menu :deep(.el-menu-item .el-icon) {
  font-size: 16px;
  color: inherit;
}

.sau-shell__main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  background: var(--ch-layout-bg);
  padding: 16px 20px;
}
</style>
