<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchTemuSessionStatus,
  openTemuSellerLogin,
  pollTemuSessionUntilReady,
} from '@/api/temuApi'
import { getAppErrorMessage, resolveAppError } from '@/utils/appErrorCode'

const props = defineProps({
  compact: { type: Boolean, default: false },
})

const loading = ref(false)
const opening = ref(false)
const status = ref({})

let pollAbort = null

const sessionReady = computed(() => Boolean(status.value.ready))
const agentOnline = computed(() => Boolean(status.value.agent_online))
const agentMode = computed(() => status.value.mode === 'agent')
const openLoginDisabled = computed(() => agentMode.value && !agentOnline.value)

const mallNames = computed(() =>
  (status.value.malls || [])
    .map((mall) => mall.mall_name || mall.mallName)
    .filter(Boolean)
    .join('、'),
)

const sessionHint = computed(() => {
  if (openLoginDisabled.value) {
    return resolveAppError({
      errorCode: 'TEMU_AGENT_OFFLINE',
      message: status.value.message || '',
    })
  }
  const hint = status.value.error_hint || ''
  if (hint) {
    return resolveAppError({ errorCode: hint, message: status.value.message || '' })
  }
  const message = String(status.value.message || '').trim()
  if (message) {
    return { title: '', summary: message, steps: [] }
  }
  return null
})

const alertTitle = computed(() => {
  if (sessionHint.value?.title) return sessionHint.value.title
  return '同步前需登录 Temu 卖家后台'
})

async function loadStatus({ notifyIfPending = false } = {}) {
  loading.value = true
  try {
    status.value = await fetchTemuSessionStatus()
    if (notifyIfPending && !status.value.ready) {
      const hint = status.value.error_hint
      const message =
        status.value.message ||
        (hint ? getAppErrorMessage(hint) : '会话尚未就绪，请完成登录并选择店铺')
      ElMessage.warning(message)
    }
  } catch {
    status.value = { ready: false, requires_auth: true, agent_online: false }
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

/** TM-P3：引导可见时轻量轮询（2s→5s，最多 20 次），登录完成后自动收起 */
async function startGuidePoll() {
  stopGuidePoll()
  if (sessionReady.value || (agentMode.value && !agentOnline.value)) return
  pollAbort = new AbortController()
  const signal = pollAbort.signal
  try {
    const session = await pollTemuSessionUntilReady({
      timeoutMs: 90000,
      intervalMs: 2000,
      maxIntervalMs: 5000,
      maxAttempts: 20,
      signal,
    })
    if (!signal.aborted) {
      status.value = session
    }
  } catch {
    // 超时 / 取消：保持引导可见，由用户手动点「我已完成登录」
  }
}

async function handleOpenLogin() {
  if (openLoginDisabled.value) {
    ElMessage.warning(getAppErrorMessage('TEMU_AGENT_OFFLINE'))
    return
  }
  if (status.value.profile_busy) {
    ElMessage.warning('登录窗口已在运行，请在已弹出的 CrossHub 浏览器中完成登录')
    return
  }
  opening.value = true
  try {
    const res = await openTemuSellerLogin()
    if (res.already_open) {
      ElMessage.warning(res.message || '登录窗口已在运行')
    } else if (res.queued) {
      ElMessage.success(res.message || '已通知本机助手打开登录窗口')
    } else {
      ElMessage.success(res.message || '已打开 Temu 登录窗口')
    }
    await loadStatus()
    void startGuidePoll()
  } catch (err) {
    ElMessage.error(err.message || '打开登录窗口失败')
  } finally {
    opening.value = false
  }
}

async function handleConfirmLogin() {
  if (openLoginDisabled.value) {
    ElMessage.warning(getAppErrorMessage('TEMU_AGENT_OFFLINE'))
    return
  }
  await loadStatus({ notifyIfPending: true })
  if (!status.value.ready) {
    void startGuidePoll()
  }
}

onMounted(async () => {
  await loadStatus()
  if (!sessionReady.value) {
    void startGuidePoll()
  }
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
    class="temu-login-guide"
    :class="{ 'is-compact': compact }"
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
          登录在<strong>本机弹出的 CrossHub 浏览器</strong>中完成（不是普通 Chrome）。
        </p>
        <ol class="guide-steps">
          <li>确认运维机已运行 <strong>CrossHub-Sync-Helper.exe</strong></li>
          <li>点击 <strong>打开登录窗口</strong></li>
          <li>在本机 CrossHub 浏览器中登录 Temu 卖家后台并选择店铺</li>
          <li>回到本页点击 <strong>我已完成登录</strong>，再点 <strong>刷新数据</strong></li>
        </ol>
      </template>
      <p v-if="mallNames" class="guide-meta">已识别店铺：{{ mallNames }}</p>
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
.temu-login-guide {
  margin-bottom: 16px;
}

.guide-status {
  margin: 0 0 8px;
  line-height: 1.6;
  color: var(--el-color-warning-dark-2);
  font-weight: 500;
}

.guide-lead {
  margin: 0 0 8px;
  line-height: 1.6;
}

.guide-steps {
  margin: 8px 0 12px 18px;
  padding: 0;
  line-height: 1.7;
}

.guide-meta {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.guide-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.is-compact .guide-steps {
  font-size: 13px;
}
</style>
