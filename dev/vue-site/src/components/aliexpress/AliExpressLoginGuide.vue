<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchAliExpressSessionStatus,
  openAliExpressSellerLogin,
  pollAliExpressSessionUntilReady,
} from '@/api/aliexpressApi'
import { getAppErrorMessage, resolveAppError } from '@/utils/appErrorCode'

const loading = ref(false)
const opening = ref(false)
const status = ref({})
let pollAbort = null

const sessionReady = computed(() => Boolean(status.value.ready))
const agentOnline = computed(() => Boolean(status.value.agent_online))
const agentMode = computed(() => status.value.mode === 'agent')
const openLoginDisabled = computed(() => agentMode.value && !agentOnline.value)

const sessionHint = computed(() => {
  if (openLoginDisabled.value) {
    return resolveAppError({
      errorCode: 'AE_AGENT_OFFLINE',
      message: status.value.message || '',
    })
  }
  const message = String(status.value.message || '').trim()
  if (message) {
    return { title: '', summary: message, steps: [] }
  }
  return null
})

const alertTitle = computed(() => {
  if (sessionHint.value?.title) return sessionHint.value.title
  return '同步前需登录 AliExpress 卖家后台'
})

async function loadStatus({ notifyIfPending = false } = {}) {
  loading.value = true
  try {
    status.value = await fetchAliExpressSessionStatus()
    if (notifyIfPending && !status.value.ready) {
      ElMessage.warning(
        status.value.message || getAppErrorMessage('CRAWL_AE_NOT_LOGGED_IN'),
      )
    }
  } catch (err) {
    status.value = { ready: false, requires_auth: true, agent_online: false, mode: 'agent' }
    if (notifyIfPending) {
      ElMessage.warning(err?.message || getAppErrorMessage('AE_AGENT_OFFLINE'))
    }
  } finally {
    loading.value = false
  }
}

function stopGuidePoll() {
  if (pollAbort) {
    pollAbort.abort()
    pollAbort = null
  }
}

async function startGuidePoll() {
  stopGuidePoll()
  pollAbort = new AbortController()
  try {
    const session = await pollAliExpressSessionUntilReady({ signal: pollAbort.signal })
    status.value = session
    if (session.ready) {
      ElMessage.success('AliExpress 登录已就绪')
    }
  } catch (err) {
    if (err?.errorCode === 'CRAWL_INTERRUPTED') return
    await loadStatus()
  }
}

async function handleOpenLogin() {
  if (openLoginDisabled.value) {
    ElMessage.warning(getAppErrorMessage('AE_AGENT_OFFLINE'))
    return
  }
  opening.value = true
  try {
    await openAliExpressSellerLogin()
    ElMessage.success('已通知本机助手打开 AliExpress 登录窗口')
    void startGuidePoll()
  } catch (err) {
    ElMessage.error(err?.message || getAppErrorMessage('AE_AGENT_OFFLINE'))
  } finally {
    opening.value = false
  }
}

async function handleConfirmLogin() {
  if (openLoginDisabled.value) {
    ElMessage.warning(getAppErrorMessage('AE_AGENT_OFFLINE'))
    return
  }
  await loadStatus({ notifyIfPending: true })
  if (!status.value.ready) {
    void startGuidePoll()
  }
}

onMounted(() => {
  void loadStatus().then(() => {
    if (!sessionReady.value && agentOnline.value) {
      void startGuidePoll()
    }
  })
})

onUnmounted(() => {
  stopGuidePoll()
})

defineExpose({ reload: loadStatus, sessionReady })
</script>

<template>
  <el-alert
    v-if="!loading && !sessionReady"
    type="warning"
    show-icon
    :closable="false"
    class="ae-login-guide"
    :title="alertTitle"
  >
    <template #default>
      <p v-if="sessionHint?.summary" class="guide-status">
        {{ sessionHint.summary }}
      </p>
      <p v-if="openLoginDisabled" class="guide-lead">
        本机同步程序未在线，无法打开登录窗口。请联系运维确认已启动
        <strong>CrossHub-Sync-Helper.exe</strong> 并保持运行。
      </p>
      <template v-else>
        <p class="guide-lead">
          登录在<strong>本机弹出的 CrossHub 浏览器</strong>中完成（CSP / AliExpress 卖家后台）。
        </p>
        <ol class="guide-steps">
          <li>确认运维机已运行 <strong>CrossHub-Sync-Helper.exe</strong></li>
          <li>点击 <strong>打开登录窗口</strong></li>
          <li>在本机浏览器中完成 AliExpress 登录</li>
          <li>回到本页点击 <strong>我已完成登录</strong></li>
        </ol>
      </template>
      <div class="guide-actions">
        <el-button
          size="small"
          type="primary"
          :loading="opening"
          :disabled="openLoginDisabled"
          @click="handleOpenLogin"
        >
          打开登录窗口
        </el-button>
        <el-button
          size="small"
          :loading="loading"
          :disabled="openLoginDisabled"
          @click="handleConfirmLogin"
        >
          我已完成登录
        </el-button>
      </div>
    </template>
  </el-alert>
</template>

<style scoped>
.ae-login-guide {
  margin-bottom: 16px;
}
.guide-status,
.guide-lead {
  margin: 0 0 8px;
  line-height: 1.5;
}
.guide-steps {
  margin: 0 0 12px;
  padding-left: 18px;
  line-height: 1.6;
}
.guide-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
