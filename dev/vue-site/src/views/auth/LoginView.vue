<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Box, Lock, User, UserFilled } from '@element-plus/icons-vue'
import { loginAccount } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { defaultLandingPath } from '@/utils/menuAuth'
import AuthSplitLayout from '@/components/auth/AuthSplitLayout.vue'
import { useYotoMascot } from '@/composables/useYotoMascot'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { onPasswordFocus, onPasswordBlur } = useYotoMascot()

const loading = ref(false)
const portalRole = ref('boss')
const password = ref('')
const account = ref('')
const formError = ref('')

const roleLabel = computed(() => {
  if (portalRole.value === 'boss') return '企业管理员'
  if (portalRole.value === 'warehouse') return '仓库端口'
  return '员工工作台'
})

onMounted(() => {
  const q = route.query.account
  if (typeof q === 'string' && q) {
    account.value = q
    password.value = ''
  }
  const portal = route.query.portal
  if (portal === 'employee' || portal === 'boss' || portal === 'warehouse') {
    portalRole.value = portal
  } else if (portal === 'admin') {
    portalRole.value = 'boss'
  } else if (typeof q === 'string' && q) {
    portalRole.value = 'employee'
  }
})

function clearFormError() {
  if (formError.value) formError.value = ''
}

function resolveLoginError(err) {
  const code = String(err?.errorCode || '').trim()
  const raw = String(err?.message || '').trim()
  if (
    code === 'AUTH_BAD_CREDENTIALS'
    || /账号或密码/.test(raw)
  ) {
    return '账号或密码不正确，请重新填写后重试'
  }
  if (code === 'AUTH_INACTIVE' || /已停用/.test(raw)) {
    return '该账号已停用，请联系企业管理员'
  }
  if (code === 'AUTH_NO_TENANT' || /未绑定/.test(raw)) {
    return '账号未绑定企业，请联系企业管理员开通'
  }
  if (code === 'AUTH_MULTI_TENANT' || /多个企业/.test(raw)) {
    return '该账号绑定多个企业，请使用企业专用账号登录'
  }
  if (/后端服务未启动|Java API|:18080|不可用|Network Error|timeout/i.test(raw)) {
    return '登录服务暂时不可用，请稍后重试'
  }
  return raw || '登录失败，请检查账号密码后重试'
}

async function handleLogin() {
  formError.value = ''
  if (!account.value.trim()) {
    formError.value = '请填写登录账号'
    ElMessage.warning(formError.value)
    return
  }
  if (!password.value) {
    formError.value = '请填写登录密码'
    ElMessage.warning(formError.value)
    return
  }

  loading.value = true
  try {
    // 选项卡仅作入口提示；后端按账号 per（0=boss / 1=员工 / 2=仓库）自动校准 portal / 落地页
    const res = await loginAccount({
      account: account.value.trim(),
      password: password.value,
      preferredPortal: portalRole.value,
    })
    const portal = res.portal || 'employee'
    if (portal === 'boss') {
      auth.setCompany(res.data)
    } else if (portal === 'warehouse') {
      auth.setWarehouse(res.data)
    } else {
      auth.setEmployee(res.data)
    }
    auth.login(portal)
    if (res.per != null && res.per !== '') {
      auth.setPer(String(res.per))
    }
    if (portal !== portalRole.value) {
      ElMessage.info(`已按账号权限进入${portal === 'boss' ? '企业管理员' : portal === 'warehouse' ? '仓库端口' : '员工工作台'}`)
      portalRole.value = portal
    }
    const landing = String(res.landingPath || '').trim()
    router.push(landing || defaultLandingPath(auth))
  } catch (err) {
    const msg = resolveLoginError(err)
    formError.value = msg
    ElMessage.error({ message: msg, duration: 4500, showClose: true })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthSplitLayout>
    <header class="auth-head">
      <p class="auth-head__eyebrow">Welcome back</p>
      <h2>登录 CrossHub</h2>
      <p class="auth-head__sub">选择身份入口；系统仍按账号权限自动校准工作台</p>
    </header>

    <div class="role-tabs">
      <button
        type="button"
        class="role-tab"
        data-per="0"
        :class="{ 'is-active': portalRole === 'boss' }"
        @click="portalRole = 'boss'"
      >
        <el-icon><UserFilled /></el-icon>
        <span class="role-tab__text">企业管理员</span>
      </button>
      <button
        type="button"
        class="role-tab"
        data-per="1"
        :class="{ 'is-active': portalRole === 'employee' }"
        @click="portalRole = 'employee'"
      >
        <el-icon><User /></el-icon>
        <span class="role-tab__text">员工端口</span>
      </button>
      <button
        type="button"
        class="role-tab"
        data-per="2"
        :class="{ 'is-active': portalRole === 'warehouse' }"
        @click="portalRole = 'warehouse'"
      >
        <el-icon><Box /></el-icon>
        <span class="role-tab__text">仓库端口</span>
      </button>
    </div>

    <el-form label-position="top" class="auth-form" @submit.prevent="handleLogin">
      <el-form-item label="账号">
        <el-input
          v-model="account"
          :prefix-icon="User"
          placeholder="请输入登录账号"
          size="large"
          clearable
          autocomplete="username"
          @input="clearFormError"
        />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="password"
          type="password"
          show-password
          :prefix-icon="Lock"
          placeholder="请输入密码"
          size="large"
          autocomplete="current-password"
          @focus="onPasswordFocus"
          @blur="onPasswordBlur"
          @input="clearFormError"
          @keyup.enter="handleLogin"
        />
      </el-form-item>

      <p v-if="formError" class="auth-form-error" role="alert">{{ formError }}</p>

      <el-button
        type="primary"
        size="large"
        class="auth-submit"
        :loading="loading"
        native-type="submit"
      >
        进入{{ roleLabel }}
        <el-icon><ArrowRight /></el-icon>
      </el-button>
    </el-form>

    <p class="auth-switch-link">
      还没有账号？
      <button type="button" class="auth-text-link" @click="router.push('/register')">员工/企业注册</button>
    </p>
  </AuthSplitLayout>
</template>

<style scoped>
.auth-form-error {
  margin: -0.25rem 0 0.75rem;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: color-mix(in srgb, #dc2626 10%, transparent);
  border: 1px solid color-mix(in srgb, #dc2626 28%, transparent);
  color: #b91c1c;
  font-size: 0.875rem;
  line-height: 1.45;
}
</style>
