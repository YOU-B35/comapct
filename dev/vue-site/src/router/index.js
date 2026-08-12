import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { canAccessRoute, defaultLandingPath } from '@/utils/menuAuth'
import { clearAccessToken, getAccessToken } from '@/api/request'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      component: () => import('@/layouts/AuthLayout.vue'),
      children: [
        { path: '', name: 'login', component: () => import('@/views/auth/LoginView.vue') },
      ],
    },
    {
      path: '/register',
      component: () => import('@/layouts/AuthLayout.vue'),
      children: [
        { path: '', name: 'register', component: () => import('@/views/auth/RegisterView.vue') },
      ],
    },
    {
      path: '/boss',
      component: () => import('@/layouts/PortalLayout.vue'),
      meta: { role: 'boss' },
      children: [
        { path: '', redirect: '/boss/dashboard' },
        { path: 'ops-teams', name: 'boss-ops-teams', component: () => import('@/views/boss/OpsTeamsView.vue'), meta: { title: '运营小组', menuCode: 'boss.ops_teams' } },
        { path: 'employees', name: 'boss-employees', component: () => import('@/views/boss/EmployeeBindingView.vue'), meta: { title: '运营绑定', menuCode: 'boss.employees' } },
        { path: 'warehouse-sites', name: 'boss-warehouse-sites', component: () => import('@/views/boss/WarehouseSitesView.vue'), meta: { title: '仓库设置', menuCode: 'boss.warehouse_sites' } },
        { path: 'warehouse-staff', name: 'boss-warehouse-staff', component: () => import('@/views/warehouse/WarehouseStaffBindingView.vue'), meta: { title: '仓库人员', menuCode: 'boss.warehouse_staff' } },
        { path: 'dashboard', name: 'boss-dashboard', component: () => import('@/views/boss/BossDashboardView.vue'), meta: { title: '运营总览', menuCode: 'boss.dashboard' } },
        { path: 'ai-image', name: 'boss-ai-image', component: () => import('@/views/boss/AiImageView.vue'), meta: { title: 'AI 生图', menuCode: 'boss.ai_image' } },
        {
          path: 'sau',
          component: () => import('@/views/boss/SauModuleView.vue'),
          meta: { title: '自媒体运营', menuCode: 'boss.sau' },
          children: [
            { path: '', redirect: { name: 'boss-sau-home' } },
            { path: 'home', name: 'boss-sau-home', component: () => import('@sau/views/Dashboard.vue'), meta: { title: '自媒体运营', menuCode: 'boss.sau' } },
            { path: 'accounts', name: 'boss-sau-accounts', component: () => import('@sau/views/AccountManagement.vue'), meta: { title: '账号管理', menuCode: 'boss.sau' } },
            { path: 'materials', name: 'boss-sau-materials', component: () => import('@sau/views/MaterialManagement.vue'), meta: { title: '素材管理', menuCode: 'boss.sau' } },
            { path: 'publish', name: 'boss-sau-publish', component: () => import('@sau/views/PublishCenter.vue'), meta: { title: '发布中心', menuCode: 'boss.sau' } },
            { path: 'works', name: 'boss-sau-works', component: () => import('@sau/views/ContentWorks.vue'), meta: { title: '作品中心', menuCode: 'boss.sau' } },
            { path: 'about', name: 'boss-sau-about', component: () => import('@sau/views/About.vue'), meta: { title: '关于', menuCode: 'boss.sau' } },
          ],
        },
        {
          path: 'auto-upload',
          name: 'boss-auto-upload',
          component: () => import('@commander/views/AutoUploadView.vue'),
          meta: { title: '自动上货', menuCode: 'boss.auto_upload' },
        },
        { path: 'tasks', name: 'boss-tasks', component: () => import('@/views/boss/TaskAssignmentView.vue'), meta: { title: '任务分配', menuCode: 'boss.tasks' } },
        { path: 'temu', name: 'boss-temu', component: () => import('@/views/temu/TemuModuleView.vue'), meta: { title: 'Temu 运营', menuCode: 'boss.platform.temu' } },
        { path: 'aliexpress', name: 'boss-aliexpress', component: () => import('@/views/aliexpress/AliExpressModuleView.vue'), meta: { title: 'AliExpress 运营', menuCode: 'boss.platform.aliexpress' } },
        { path: 'amazon', name: 'boss-amazon', component: () => import('@/views/amazon/AmazonModuleView.vue'), meta: { title: 'Amazon 运营', menuCode: 'boss.platform.amazon' } },
        { path: 'walmart', name: 'boss-walmart', component: () => import('@/views/walmart/WalmartModuleView.vue'), meta: { title: 'Walmart 运营', menuCode: 'boss.platform.walmart' } },
        { path: 'pdd', name: 'boss-pdd', component: () => import('@/views/pdd/PddModuleView.vue'), meta: { title: '拼多多运营', menuCode: 'boss.platform.pdd' } },
        { path: 'douyin', name: 'boss-douyin', component: () => import('@/views/douyin/DouyinModuleView.vue'), meta: { title: '抖音运营', menuCode: 'boss.platform.douyin' } },
        { path: 'channels', name: 'boss-channels', component: () => import('@/views/channels/ChannelsModuleView.vue'), meta: { title: '视频号运营', menuCode: 'boss.platform.channels' } },
        { path: '1688', name: 'boss-1688', component: () => import('@/views/alibaba1688/Alibaba1688ModuleView.vue'), meta: { title: '1688 运营', menuCode: 'boss.platform.1688' } },
        { path: 'dtc', name: 'boss-dtc', component: () => import('@/views/dtc/DtcModuleView.vue'), meta: { title: '独立站运营', menuCode: 'boss.platform.dtc' } },
        { path: 'accounts', name: 'boss-accounts', component: () => import('@/views/boss/AccountBindingView.vue'), meta: { title: '账户绑定', menuCode: 'boss.accounts' } },
        { path: 'agent-nodes', name: 'boss-agent-nodes', component: () => import('@/views/boss/AgentNodesView.vue'), meta: { title: '本机同步助手', menuCode: 'boss.agent_nodes' } },
        { path: 'features', name: 'boss-features', component: () => import('@/views/boss/TenantFeaturesView.vue'), meta: { title: '功能开关', menuCode: 'boss.features' } },
        { path: 'warehouse-orders', name: 'boss-warehouse-orders', component: () => import('@/views/warehouse/WarehouseOrdersView.vue'), meta: { title: '仓库下单', menuCode: 'boss.warehouse' } },
      ],
    },
    {
      path: '/warehouse',
      component: () => import('@/layouts/PortalLayout.vue'),
      meta: { role: 'warehouse' },
      children: [
        { path: '', redirect: '/warehouse/pending-review' },
        { path: 'orders', redirect: '/warehouse/pending-review' },
        {
          path: 'pending-review',
          name: 'warehouse-pending-review',
          component: () => import('@/views/warehouse/WarehouseOrdersView.vue'),
          meta: {
            title: '待审核',
            menuCode: 'warehouse.pending_review',
            orderStatusFilter: ['pending_review'],
          },
        },
        {
          path: 'pending-shipment',
          name: 'warehouse-pending-shipment',
          component: () => import('@/views/warehouse/WarehouseOrdersView.vue'),
          meta: {
            title: '待发货',
            menuCode: 'warehouse.pending_shipment',
            orderStatusFilter: ['pending_shipment', 'blocked'],
          },
        },
        {
          path: 'shipped',
          name: 'warehouse-shipped',
          component: () => import('@/views/warehouse/WarehouseOrdersView.vue'),
          meta: {
            title: '已发货',
            menuCode: 'warehouse.shipped',
            orderStatusFilter: ['shipped'],
          },
        },
        {
          path: 'tasks',
          name: 'warehouse-tasks',
          component: () => import('@/views/warehouse/WarehouseTasksView.vue'),
          meta: { title: '任务中心', menuCode: 'warehouse.tasks' },
        },
      ],
    },
    {
      path: '/employee',
      component: () => import('@/layouts/PortalLayout.vue'),
      meta: { role: 'employee' },
      children: [
        { path: '', redirect: '/employee/dashboard' },
        { path: 'dashboard', name: 'employee-dashboard', component: () => import('@/views/employee/DashboardView.vue'), meta: { title: '我的工作台', menuCode: 'employee.dashboard' } },
        { path: 'ops-team', name: 'employee-ops-team', component: () => import('@/views/employee/OpsTeamView.vue'), meta: { title: '我的小组', menuCode: 'employee.ops_team' } },
        { path: 'team-tasks', name: 'employee-team-tasks', component: () => import('@/views/employee/TeamTasksView.vue'), meta: { title: '任务分配', menuCode: 'employee.team_tasks' } },
        { path: 'team-binding', name: 'employee-team-binding', component: () => import('@/views/employee/TeamBindingView.vue'), meta: { title: '运营绑定', menuCode: 'employee.team_binding' } },
        { path: 'tasks', name: 'employee-tasks', component: () => import('@/views/employee/TasksView.vue'), meta: { title: '任务中心', menuCode: 'employee.tasks' } },
        {
          path: 'auto-upload',
          name: 'employee-auto-upload',
          component: () => import('@commander/views/AutoUploadView.vue'),
          meta: { title: '自动上货', menuCode: 'employee.auto_upload' },
        },
        { path: 'temu', name: 'employee-temu', component: () => import('@/views/temu/TemuModuleView.vue'), meta: { title: 'Temu 运营', menuCode: 'employee.platform.temu' } },
        { path: 'aliexpress', name: 'employee-aliexpress', component: () => import('@/views/aliexpress/AliExpressModuleView.vue'), meta: { title: 'AliExpress 运营', menuCode: 'employee.platform.aliexpress' } },
        { path: 'amazon', name: 'employee-amazon', component: () => import('@/views/amazon/AmazonModuleView.vue'), meta: { title: 'Amazon 运营', menuCode: 'employee.platform.amazon' } },
        { path: 'walmart', name: 'employee-walmart', component: () => import('@/views/walmart/WalmartModuleView.vue'), meta: { title: 'Walmart 运营', menuCode: 'employee.platform.walmart' } },
        { path: 'pdd', name: 'employee-pdd', component: () => import('@/views/pdd/PddModuleView.vue'), meta: { title: '拼多多运营', menuCode: 'employee.platform.pdd' } },
        { path: 'douyin', name: 'employee-douyin', component: () => import('@/views/douyin/DouyinModuleView.vue'), meta: { title: '抖音运营', menuCode: 'employee.platform.douyin' } },
        { path: 'channels', name: 'employee-channels', component: () => import('@/views/channels/ChannelsModuleView.vue'), meta: { title: '视频号运营', menuCode: 'employee.platform.channels' } },
        { path: '1688', name: 'employee-1688', component: () => import('@/views/alibaba1688/Alibaba1688ModuleView.vue'), meta: { title: '1688 运营', menuCode: 'employee.platform.1688' } },
        { path: 'dtc', name: 'employee-dtc', component: () => import('@/views/dtc/DtcModuleView.vue'), meta: { title: '独立站运营', menuCode: 'employee.platform.dtc' } },
        { path: 'warehouse-orders', name: 'employee-warehouse-orders', component: () => import('@/views/warehouse/WarehouseOrdersView.vue'), meta: { title: '仓库下单', menuCode: 'employee.warehouse' } },
        {
          path: 'sau',
          component: () => import('@/views/employee/SauModuleView.vue'),
          meta: { title: '自媒体运营', menuCode: 'employee.sau' },
          children: [
            { path: '', redirect: { name: 'employee-sau-home' } },
            { path: 'home', name: 'employee-sau-home', component: () => import('@sau/views/Dashboard.vue'), meta: { title: '自媒体运营', menuCode: 'employee.sau' } },
            { path: 'accounts', name: 'employee-sau-accounts', component: () => import('@sau/views/AccountManagement.vue'), meta: { title: '账号管理', menuCode: 'employee.sau' } },
            { path: 'materials', name: 'employee-sau-materials', component: () => import('@sau/views/MaterialManagement.vue'), meta: { title: '素材管理', menuCode: 'employee.sau' } },
            { path: 'publish', name: 'employee-sau-publish', component: () => import('@sau/views/PublishCenter.vue'), meta: { title: '发布中心', menuCode: 'employee.sau' } },
            { path: 'works', name: 'employee-sau-works', component: () => import('@sau/views/ContentWorks.vue'), meta: { title: '作品中心', menuCode: 'employee.sau' } },
            { path: 'about', name: 'employee-sau-about', component: () => import('@sau/views/About.vue'), meta: { title: '关于', menuCode: 'employee.sau' } },
          ],
        },
        { path: 'ai', name: 'employee-ai', component: () => import('@/views/employee/AiOfficeView.vue'), meta: { title: 'AI 办公', menuCode: 'employee.ai' } },
        { path: 'ai-image', name: 'employee-ai-image', component: () => import('@/views/employee/AiImageView.vue'), meta: { title: 'AI 生图', menuCode: 'employee.ai_image' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/login' },
  ],
})

let sessionRefreshPromise = null

async function ensureBackendSession(auth) {
  if (!auth.backendLinked || !getAccessToken()) return
  if (!sessionRefreshPromise) {
    sessionRefreshPromise = auth.refreshSession().catch((err) => {
      const message = String(err?.message || '')
      if (/后端服务未启动|ECONNREFUSED|Network Error/i.test(message)) {
        return
      }
      auth.logout()
      clearAccessToken()
      throw err
    }).finally(() => {
      sessionRefreshPromise = null
    })
  }
  await sessionRefreshPromise
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.path === '/login' || to.path === '/register') {
    if (auth.isLoggedIn) {
      await ensureBackendSession(auth)
      return defaultLandingPath(auth)
    }
    return true
  }

  if (!auth.isLoggedIn) return '/login'

  await ensureBackendSession(auth)

  const requiredRole = to.matched.find((r) => r.meta.role)?.meta.role
  if (requiredRole && requiredRole !== auth.role) {
    return defaultLandingPath(auth)
  }

  if (!canAccessRoute(auth, to)) {
    ElMessage.warning('当前账号无权访问该页面')
    return defaultLandingPath(auth)
  }

  return true
})

export default router
