<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useCommanderAuthStore } from '../stores/commanderAuth'

const auth = useCommanderAuthStore()
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
})

async function submit() {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入 Commander 账号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    ElMessage.success('Commander 登录成功')
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card shadow="never" class="commander-login">
    <template #header>
      <div class="head">
        <strong>登录 Commander（自动上货）</strong>
        <el-text type="info" size="small">
          使用原 www.yoto.work 上货站账号；与 CrossHub 登录相互独立
        </el-text>
      </div>
    </template>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="账号">
        <el-input v-model="form.username" autocomplete="username" placeholder="Commander 用户名" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          autocomplete="current-password"
          placeholder="密码"
          @keyup.enter="submit"
        />
      </el-form-item>
      <el-button type="primary" :loading="loading" style="width: 100%" @click="submit">
        登录并进入自动上货
      </el-button>
    </el-form>
  </el-card>
</template>

<style scoped>
.commander-login {
  max-width: 420px;
  margin: 24px auto;
}

.head {
  display: grid;
  gap: 4px;
}
</style>
