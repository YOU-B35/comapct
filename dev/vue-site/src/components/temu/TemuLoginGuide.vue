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
const openingKey = ref('')
const status = ref({})

let pollAbort = null

const sessionReady = computed(() => Boolean(status.value.ready))
const agentOnline = computed(() => Boolean(status.value.agent_online))
const agentMode = computed(() => status.value.mode === 'agent')
const openLoginDisabled = computed(() => agentMode.value && !agentOnline.value)

const sellerRows = computed(() => {
  const bindings = status.value.seller_sessions || []
  const live = status.value.sessions || []
  const liveByKey = new Map(
    live.map((row) => [String(row.session_key || 'default'), row]),
  )
  if (bindings.length) {
    return bindings.map((binding) => {
      const key = String(binding.session_key || 'default')
      const liveRow = liveByKey.get(key) || {}
      return {
        sessionKey: key,
        account: binding.account || liveRow.account || key,
        platformAccountId: binding.platform_account_id || liveRow.platform_account_id || '',
        storeNames: binding.store_names || [],
        ready: Boolean(liveRow.ready),
        mallCount: Number(liveRow.mall_count || 0),
        malls: liveRow.malls || [],
        profileBusy: Boolean(liveRow.profile_busy),
        message: liveRow.message || '',
      }
    })
  }
  if (live.length) {
    return live.map((row) => ({
      sessionKey: String(row.session_key || 'default'),
      account: row.account || row.session_key || 'default',
      platformAccountId: row.platform_account_id || '',
      storeNames: row.store_names || [],
      ready: Boolean(row.ready),
      mallCount: Number(row.mall_count || 0),
      malls: row.malls || [],
      profileBusy: Boolean(row.profile_busy),
      message: row.message || '',
    }))
  }
  return [{
    sessionKey: 'default',
    account: '',
    platformAccountId: '',
    storeNames: [],
    ready: sessionReady.value,
    mallCount: Number(status.value.mall_count || 0),
    malls: status.value.malls || [],
    profileBusy: Boolean(status.value.profile_busy),
    message: status.value.message || '',
  }]
})

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
  if (sellerRows.value.length > 1) {
    return '同步前需为每个 Temu 卖家账号登录'
  }
  return '同步前需登录 Temu 卖家后台'
})

function mallLabel(row) {
  const names = (row.malls || [])
    .map((mall) => mall.mall_name || mall.mallName)
    .filter(Boolean)
  if (names.length) return names.join('、')
  if (row.mallCount > 0) return `${row.mallCount} 个店铺`
  return ''
}

async function loadStatus({ notifyIfPending = false } = {}) {
  loading.value = true
  try {
    status.value = await fetchTemuSessionStatus()
    if (notifyIfPending && !status.value.ready) {
      const hint = status.value.error_hint
      const message =
        status.value.message ||
        (hint ? getAppErrorMessage(hint) : '会话尚未就绪，请为每个卖家账号完成登录')
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
    // timeout / cancel
  }
}

async function handleOpenLogin(row) {
  if (openLoginDisabled.value) {
    ElMessage.warning(getAppErrorMessage('TEMU_AGENT_OFFLINE'))
    return
  }
  if (row.profileBusy) {
    ElMessage.warning('该卖家账号登录窗口已在运行，请在已弹出的 CrossHub 浏览器中完成登录')
    return
  }
  openingKey.value = row.sessionKey
  try {
    const res = await openTemuSellerLogin({
      platformAccountId: row.platformAccountId || undefined,
    })
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
    openingKey.value = ''
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
          每个 Temu 卖家账号需单独登录一次；同一账号下的多个店铺会在同步时自动切换。
          登录在<strong>本机弹出的 CrossHub 浏览器</strong>中完成。
        </p>
        <div v-if="sellerRows.length > 1" class="seller-session-list">
          <div v-for="row in sellerRows" :key="row.sessionKey" class="seller-session-row">
            <div class="seller-session-main">
              <strong>{{ row.account || row.sessionKey }}</strong>
              <span v-if="row.storeNames?.length" class="seller-stores">
                绑定：{{ row.storeNames.join('、') }}
              </span>
              <el-tag size="small" :type="row.ready ? 'success' : 'warning'">
                {{ row.ready ? '已登录' : '未登录' }}
              </el-tag>
              <span v-if="mallLabel(row)" class="seller-malls">店铺：{{ mallLabel(row) }}</span>
            </div>
            <el-button
              size="small"
              type="primary"
              :loading="openingKey === row.sessionKey"
              :disabled="openLoginDisabled"
              @click="handleOpenLogin(row)"
            >
              打开登录
            </el-button>
          </div>
        </div>
        <ol v-else class="guide-steps">
          <li>确认运维机已运行 <strong>CrossHub-Sync-Helper.exe</strong></li>
          <li>点击 <strong>打开登录窗口</strong></li>
          <li>在本机 CrossHub 浏览器中登录 Temu 卖家后台</li>
          <li>回到本页点击 <strong>我已完成登录</strong>，再点 <strong>刷新数据</strong></li>
        </ol>
      </template>
      <div class="guide-actions">
        <el-button
          v-if="sellerRows.length <= 1"
          size="small"
          type="primary"
          :loading="openingKey === 'default'"
          :disabled="openLoginDisabled"
          @click="handleOpenLogin(sellerRows[0])"
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
      <p v-if="status.ready_count != null && status.session_count > 1" class="guide-meta">
        已就绪 {{ status.ready_count }}/{{ status.session_count }} 个卖家账号
      </p>
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

.seller-session-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 10px 0 12px;
}

.seller-session-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.seller-session-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  line-height: 1.5;
}

.seller-stores,
.seller-malls {
  font-size: 13px;
  color: var(--el-text-color-secondary);
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
