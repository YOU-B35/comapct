<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Key, Lock, OfficeBuilding, User } from '@element-plus/icons-vue'
import { registerCompany, registerEmployee } from '@/api/auth'
import AuthSplitLayout from '@/components/auth/AuthSplitLayout.vue'
import { useYotoMascot } from '@/composables/useYotoMascot'

const router = useRouter()
const { onPasswordFocus, onPasswordBlur } = useYotoMascot()

/** company | employee */
const mode = ref('employee')
const loading = ref(false)
const form = ref({
  company: '',
  tenantCode: '',
  name: '',
  account: '',
  password: '',
  confirmPassword: '',
})

const isEmployee = computed(() => mode.value === 'employee')
const submitLabel = computed(() => (isEmployee.value ? '注册员工账号' : '注册并创建企业'))

async function handleRegister() {
  if (isEmployee.value) {
    if (!form.value.company.trim() && !form.value.tenantCode.trim()) {
      ElMessage.warning('请填写企业名称或企业邀请码')
      return
    }
    if (!form.value.name.trim()) {
      ElMessage.warning('请填写姓名')
      return
    }
  } else if (!form.value.company.trim()) {
    ElMessage.warning('请填写企业名称')
    return
  }
  if (!form.value.account.trim()) {
    ElMessage.warning('请填写登录账号')
    return
  }
  if (form.value.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    if (isEmployee.value) {
      await registerEmployee({
        company: form.value.company.trim(),
        tenantCode: form.value.tenantCode.trim(),
        name: form.value.name.trim(),
        account: form.value.account.trim(),
        password: form.value.password,
      })
      ElMessage.success('员工注册成功，请使用「员工端口」登录')
      router.push({
        path: '/login',
        query: { account: form.value.account.trim(), portal: 'employee' },
      })
    } else {
      const result = await registerCompany({
        company: form.value.company.trim(),
        account: form.value.account.trim(),
        password: form.value.password,
      })
      const code = result?.data?.tenant_code
      ElMessage.success(
        code
          ? `企业注册成功，邀请码 ${code}，可发给员工注册`
          : '注册成功，请登录',
      )
      router.push({ path: '/login', query: { account: form.value.account.trim(), portal: 'boss' } })
    }
  } catch (err) {
    ElMessage.error(err.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthSplitLayout>
    <header class="auth-head">
      <p class="auth-head__eyebrow">Get started</p>
      <h2>注册 CrossHub</h2>
      <p class="auth-head__sub">
        {{ isEmployee ? '加入已有企业，以员工身份使用运营工作台' : '创建企业账号，以企业管理员身份管理跨境业务' }}
      </p>
    </header>

    <el-segmented
      v-model="mode"
      class="register-mode"
      :options="[
        { label: '员工注册', value: 'employee' },
        { label: '企业注册', value: 'company' },
      ]"
    />

    <el-form label-position="top" class="auth-form" @submit.prevent="handleRegister">
      <template v-if="isEmployee">
        <el-form-item label="企业名称">
          <el-input
            v-model="form.company"
            :prefix-icon="OfficeBuilding"
            placeholder="如：杭州亿拓户外用品有限公司"
            size="large"
            clearable
          />
        </el-form-item>
        <el-form-item label="企业邀请码（可选）">
          <el-input
            v-model="form.tenantCode"
            :prefix-icon="Key"
            placeholder="有邀请码时可不填企业名称"
            size="large"
            clearable
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input
            v-model="form.name"
            :prefix-icon="User"
            placeholder="显示名称"
            size="large"
            clearable
          />
        </el-form-item>
      </template>
      <template v-else>
        <el-form-item label="企业名称">
          <el-input
            v-model="form.company"
            :prefix-icon="OfficeBuilding"
            placeholder="如：杭州亿拓户外用品有限公司"
            size="large"
            clearable
          />
        </el-form-item>
      </template>

      <el-form-item label="登录账号">
        <el-input
          v-model="form.account"
          :prefix-icon="User"
          placeholder="邮箱或登录账号"
          size="large"
          clearable
          autocomplete="username"
        />
      </el-form-item>

      <div class="password-row">
        <el-form-item label="登录密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :prefix-icon="Lock"
            placeholder="至少 6 位"
            size="large"
            autocomplete="new-password"
            @focus="onPasswordFocus"
            @blur="onPasswordBlur"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            :prefix-icon="Lock"
            placeholder="再次输入"
            size="large"
            autocomplete="new-password"
            @focus="onPasswordFocus"
            @blur="onPasswordBlur"
            @keyup.enter="handleRegister"
          />
        </el-form-item>
      </div>

      <el-button
        type="primary"
        size="large"
        class="auth-submit"
        :loading="loading"
        native-type="submit"
      >
        {{ submitLabel }}
        <el-icon><ArrowRight /></el-icon>
      </el-button>
    </el-form>

    <p class="auth-switch-link">
      已有账号？
      <button type="button" class="auth-text-link" @click="router.push('/login')">返回登录</button>
    </p>
  </AuthSplitLayout>
</template>

<style scoped>
.register-mode {
  width: 100%;
  margin-bottom: 1.25rem;
}
</style>
