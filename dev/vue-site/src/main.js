import './assets/main.css'
import 'element-plus/dist/index.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import { isTemuBackendEnabled } from './api/config'
import { clearAccessToken } from './api/request'

async function prepareDemoMode() {
  clearAccessToken()
  localStorage.setItem('backend_linked', '0')
  const [
    { ensureDefaultUser },
    { ensureDemoStores },
    { ensureDemoEmployees },
    { ensureDemoWarehouseStaff },
    { ensureDemoCompetitors },
  ] = await Promise.all([
    import('./api/authLocal'),
    import('./api/platformAccountsLocal'),
    import('./api/employeesLocal'),
    import('./api/warehouseStaffLocal'),
    import('./api/temuCompetitorsLocal'),
  ])
  ensureDefaultUser()
  ensureDemoStores()
  ensureDemoEmployees()
  ensureDemoWarehouseStaff()
  ensureDemoCompetitors()
}

if (!isTemuBackendEnabled()) {
  await prepareDemoMode()
} else if (localStorage.getItem('crosshub_logged_in') === '1' && !localStorage.getItem('accessToken')) {
  localStorage.setItem('crosshub_logged_in', '0')
  localStorage.setItem('backend_linked', '0')
}

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
