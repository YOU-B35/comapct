<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import WarehouseScopePanel from '@/components/warehouse/WarehouseScopePanel.vue'
import PortalBrand from '@/components/layout/PortalBrand.vue'
import PortalSidebarMenu from '@/components/layout/PortalSidebarMenu.vue'
import PortalUserPanel from '@/components/layout/PortalUserPanel.vue'
import PortalTopHeader from '@/components/layout/PortalTopHeader.vue'
import { sidebarMenuOpenKeys } from '@/utils/menuAuth'
import { usePlatformSyncStore } from '@/stores/platformSync'
import { canUseOpsManualSync } from '@/utils/opsSyncPolicy'
import { useSauShellStore } from '@sau/stores/shell'

const MOBILE_BREAKPOINT = 768
const ASIDE_WIDTH = '240px'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const syncStore = usePlatformSyncStore()
const sauShell = useSauShellStore()

const isMobile = ref(false)
const mobileMenuOpen = ref(false)

const menus = computed(() => auth.sidebarMenus)

const isSauModule = computed(() => {
  const path = route.path || ''
  return path.startsWith('/employee/sau') || path.startsWith('/boss/sau')
})
const isAiImageModule = computed(() => {
  const path = route.path || ''
  return path === '/employee/ai-image' || path === '/boss/ai-image'
})

const activeMenu = computed(() => {
  const path = route.path || ''
  if (path.startsWith('/employee/sau')) return '/employee/sau'
  if (path.startsWith('/boss/sau')) return '/boss/sau'
  return path
})
const openedMenus = computed(() => sidebarMenuOpenKeys(route.path))
// Use module-stable key for SAU so child nav does not remount the portal sidebar.
const menuRenderKey = computed(() => `${activeMenu.value}:${openedMenus.value.join(',')}`)
const pageTitle = computed(() => {
  if (isSauModule.value) return '自媒体运营'
  return route.meta.title || 'CrossHub'
})
/** Nested module shells (e.g. 自媒体运营) must keep stable key so secondary sidebar survives child navigations. */
const pageKey = computed(() => {
  const path = route.path || ''
  if (path.startsWith('/employee/sau')) return 'employee-sau'
  if (path.startsWith('/boss/sau')) return 'boss-sau'
  return path
})

const userPanelTitle = computed(() => {
  if (auth.isBoss) return auth.company.name
  if (auth.isWarehouse) return auth.warehouse.name
  return auth.displayName
})

const userPanelRole = computed(() => {
  if (auth.isBoss) return '企业管理员'
  if (auth.isWarehouse) return auth.warehouse.role || '仓库人员'
  return auth.employee.role || '运营专员'
})

const userPanelMeta = computed(() => {
  if (auth.isBoss) return auth.company.account
  if (auth.isWarehouse) {
    const scope = auth.assignedWarehouseLabels.join('、')
    return scope ? `负责：${scope}` : auth.warehouse.account
  }
  return auth.employee.account
})

const userInitial = computed(() => {
  const name = userPanelTitle.value
  return (name || 'U').slice(0, 1)
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}

function syncMobileLayout() {
  isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
  if (!isMobile.value) mobileMenuOpen.value = false
}

function openMobileMenu() {
  mobileMenuOpen.value = true
}

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

onMounted(() => {
  syncMobileLayout()
  window.addEventListener('resize', syncMobileLayout)
  if (auth.backendLinked && !auth.isWarehouse) {
    syncStore.bindAuth(auth)
    void syncStore.seedFromBackend(auth)
    // 运营网页不触发爬取；仅读库展示日批状态。同步由肉机 + 09:30 日批完成。
    if (canUseOpsManualSync() && syncStore.shouldAutoSync(auth)) {
      void syncStore.runAutoSyncOnLogin(auth)
    }
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncMobileLayout)
})

watch(() => route.path, () => {
  closeMobileMenu()
})
</script>

<template>
  <el-container class="portal" :class="{ 'portal--mobile-menu-open': mobileMenuOpen }">
    <div
      v-if="isMobile && mobileMenuOpen"
      class="portal-overlay"
      aria-hidden="true"
      @click="closeMobileMenu"
    />

    <el-aside
      :width="ASIDE_WIDTH"
      class="portal-aside"
      :class="{ 'portal-aside--drawer': isMobile, 'portal-aside--open': mobileMenuOpen }"
    >
      <PortalBrand :portal-label="auth.portalLabel" />

      <WarehouseScopePanel v-if="auth.isWarehouse" variant="sidebar" />

      <PortalSidebarMenu
        :menus="menus"
        :active-menu="activeMenu"
        :opened-menus="openedMenus"
        :menu-render-key="menuRenderKey"
      />

      <PortalUserPanel
        :title="userPanelTitle"
        :role="userPanelRole"
        :meta="userPanelMeta"
        :initial="userInitial"
        :is-warehouse="auth.isWarehouse"
        :warehouse-labels="auth.assignedWarehouseLabels"
        @logout="handleLogout"
      />
    </el-aside>

    <el-container class="portal-body">
      <PortalTopHeader
        v-if="!isAiImageModule"
        :page-title="pageTitle"
        :portal-label="auth.portalLabel"
        :is-mobile="isMobile"
        :is-warehouse="auth.isWarehouse"
        :is-sau-module="isSauModule"
        @open-mobile-menu="openMobileMenu"
        @toggle-sau-collapse="sauShell.toggleCollapse()"
      />

      <el-main class="portal-main">
        <div class="portal-main-inner" :class="{ 'portal-main-inner--flush': isAiImageModule }">
          <router-view v-slot="{ Component }">
            <component :is="Component" :key="pageKey" class="portal-page" />
          </router-view>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.portal {
  height: 100vh;
  overflow: hidden;
  background: var(--ch-layout-bg);
}

.portal-aside {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--ch-sidebar-bg);
  border-right: 1px solid var(--ch-sidebar-border);
  box-shadow: none;
}

.portal > .el-container {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.portal-body {
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.portal-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 0 !important;
  background: transparent;
  display: flex;
  flex-direction: column;
}

.portal-main-inner {
  flex: 1;
  min-height: 0;
  padding: 16px 20px 20px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.portal-main-inner--flush {
  padding: 0;
}

.portal-main-inner :deep(.portal-page) {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.portal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1999;
  background: rgba(15, 23, 42, 0.45);
}

@media (max-width: 767px) {
  .portal-aside--drawer {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 2000;
    width: min(288px, 86vw) !important;
    transform: translateX(-100%);
    transition: transform 0.22s ease;
    box-shadow: var(--ch-shadow-lg);
  }

  .portal-aside--drawer.portal-aside--open {
    transform: translateX(0);
  }

  .portal-main-inner {
    padding: 12px;
    padding-bottom: max(12px, env(safe-area-inset-bottom));
  }
}
</style>
