<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Download, Link, Refresh, Monitor } from '@element-plus/icons-vue'
import {
  createBindCode,
  enqueueTemuLogin,
  fetchMyAgentStatus,
  openHelperDownload,
  resolveHelperDownloadUrl,
} from '@/api/agentHelper'
import { connectLocalHelper } from '@/utils/agentConnect'
import {
  fetchTemuSessionStatus,
  pollTemuSessionUntilReady,
} from '@/api/temuApi'
import {
  fetchAliExpressSessionStatus,
  openAliExpressSellerLogin,
  pollAliExpressSessionUntilReady,
} from '@/api/aliexpressApi'
import { getAppErrorMessage, resolveAppError } from '@/utils/appErrorCode'
import { fetchLocalHelperBind, getHelperPanelUrl } from '@/utils/agentProbe'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  /** temu | aliexpress | amazon */
  platform: { type: String, default: 'temu' },
})

const emit = defineEmits(['update:online', 'status'])
const auth = useAuthStore()

const helperLoading = ref(false)
const sessionLoading = ref(false)
const openingKey = ref('')
const connecting = ref(false)
const helperStatus = ref({ online: false, agents: [], recommended_agent_id: '' })
const sessionStatus = ref({})
/** 本机助手进程探测结果（与当前用户 Java 在线状态独立） */
const localBind = ref({
  reachable: false,
  bound: false,
  user_id: null,
  tenant_id: null,
  bound_account: '',
})

const bindDialogVisible = ref(false)
const bindLoading = ref(false)
const bindInfo = ref(null)
const stepsDialogVisible = ref(false)

async function onConnectHelper() {
  if (connecting.value) return
  connecting.value = true
  try {
    const result = await connectLocalHelper()
    if (result.status === 'not_found') {
      ElMessage.warning(result.message)
    } else {
      ElMessage.success(result.message)
      await reload()
    }
  } catch (err) {
    ElMessage.error(err?.message || '连接助手失败，请重试')
  } finally {
    connecting.value = false
  }
}

let helperPollTimer = null
let sessionPollAbort = null

const platformLabel = computed(() => {
  if (props.platform === 'aliexpress') return 'AliExpress'
  if (props.platform === 'amazon') return 'Amazon'
  return 'Temu'
})

const supportsSessionLogin = computed(
  () => props.platform === 'temu' || props.platform === 'aliexpress',
)

const online = computed(() => Boolean(helperStatus.value.online))
const sessionReady = computed(() => {
  if (!supportsSessionLogin.value) return true
  return Boolean(sessionStatus.value.ready)
})
const downloadUrl = computed(() => resolveHelperDownloadUrl())
const canDownload = computed(() => Boolean(downloadUrl.value))

const recommendedAgent = computed(() => {
  const id = String(helperStatus.value.recommended_agent_id || '')
  const agents = Array.isArray(helperStatus.value.agents) ? helperStatus.value.agents : []
  return agents.find((a) => String(a.id) === id) || agents.find((a) => a.online) || null
})

const barMode = computed(() => {
  if (!online.value) {
    return localBind.value.reachable ? 'rebind' : 'offline'
  }
  if (supportsSessionLogin.value && !sessionReady.value) return 'need-login'
  return 'ready'
})

const barTone = computed(() => {
  if (barMode.value === 'offline' || barMode.value === 'rebind') return 'warn'
  if (barMode.value === 'need-login') return 'info'
  return 'ok'
})

const offlineErrorCode = computed(() => {
  if (props.platform === 'aliexpress') return 'AE_USER_HELPER_OFFLINE'
  if (props.platform === 'amazon') return 'AMAZON_USER_HELPER_OFFLINE'
  return 'TEMU_USER_HELPER_OFFLINE'
})

const boundUserLabel = computed(() => {
  const uid = localBind.value.user_id
  if (uid == null || Number.isNaN(Number(uid))) return ''
  const acct = localBind.value.bound_account
  return acct ? `用户 #${uid}（${acct}）` : `用户 #${uid}`
})

const barTitle = computed(() => {
  if (barMode.value === 'rebind') return '本机助手已运行，但未绑定当前账号'
  if (barMode.value === 'offline') return '本机同步助手未在线'
  if (barMode.value === 'need-login') return `助手在线，待登录 ${platformLabel.value}`
  const name = recommendedAgent.value?.name
  return name ? `助手在线 · ${name}` : '助手在线 · 可同步'
})

const barMeta = computed(() => {
  if (barMode.value === 'rebind') {
    const current = auth.backendUserId ? `当前登录用户 #${auth.backendUserId}` : '当前登录账号'
    if (localBind.value.bound && boundUserLabel.value) {
      return `助手绑定的是${boundUserLabel.value}，与${current}不一致。无需重新下载：清除绑定后生成新绑定码即可`
    }
    return `${current}尚未绑定本机助手。无需重新下载：生成绑定码后在助手中填入即可`
  }
  if (barMode.value === 'need-login' && sessionHint.value?.summary) {
    return sessionHint.value.summary
  }
  if (barMode.value === 'ready') {
    return `可在本机完成 ${platformLabel.value} 登录与数据同步`
  }
  return '下载安装 Sync Helper 后，在助手中填入绑定码'
})

const ttlLabel = computed(() => {
  const sec = Number(bindInfo.value?.expires_in_seconds || 0)
  if (!sec) return ''
  if (sec >= 60) return `${Math.round(sec / 60)} 分钟`
  return `${sec} 秒`
})

const sessionHint = computed(() => {
  if (!online.value) {
    return resolveAppError({
      errorCode: offlineErrorCode.value,
      message: sessionStatus.value.message || '',
    })
  }
  const hint = sessionStatus.value.error_hint || ''
  if (hint) {
    return resolveAppError({ errorCode: hint, message: sessionStatus.value.message || '' })
  }
  const message = String(sessionStatus.value.message || '').trim()
  if (message) return { title: '', summary: message, steps: [] }
  return null
})

function publishHelperStatus() {
  emit('update:online', online.value)
  emit('status', helperStatus.value)
}

async function loadHelperStatus() {
  helperLoading.value = true
  try {
    const [status, local] = await Promise.all([
      fetchMyAgentStatus(),
      fetchLocalHelperBind(),
    ])
    helperStatus.value = status
    localBind.value = local
    publishHelperStatus()
  } catch {
    helperStatus.value = { online: false, agents: [], recommended_agent_id: '' }
    try {
      localBind.value = await fetchLocalHelperBind()
    } catch {
      localBind.value = { reachable: false, bound: false, user_id: null, tenant_id: null, bound_account: '' }
    }
    publishHelperStatus()
  } finally {
    helperLoading.value = false
  }
}

function openHelperPanel() {
  window.open(getHelperPanelUrl(), '_blank', 'noopener')
}

async function loadSessionStatus({ notifyIfPending = false } = {}) {
  if (!supportsSessionLogin.value) {
    sessionStatus.value = { ready: true }
    return
  }
  sessionLoading.value = true
  try {
    sessionStatus.value = props.platform === 'aliexpress'
      ? await fetchAliExpressSessionStatus()
      : await fetchTemuSessionStatus()
    if (notifyIfPending && !sessionStatus.value.ready) {
      ElMessage.warning(
        sessionStatus.value.message
          || getAppErrorMessage(
            props.platform === 'aliexpress' ? 'CRAWL_AE_NOT_LOGGED_IN' : 'CRAWL_NOT_LOGGED_IN',
          ),
      )
    }
  } catch {
    sessionStatus.value = { ready: false, requires_auth: true, agent_online: false }
  } finally {
    sessionLoading.value = false
  }
}

async function reload() {
  await loadHelperStatus()
  await loadSessionStatus()
  if (online.value && supportsSessionLogin.value && !sessionReady.value) {
    void startSessionPoll()
  }
}

function startHelperPoll() {
  stopHelperPoll()
  helperPollTimer = window.setInterval(() => {
    if (document.visibilityState === 'hidden') return
    void loadHelperStatus()
  }, 15000)
}

function stopHelperPoll() {
  if (helperPollTimer != null) {
    clearInterval(helperPollTimer)
    helperPollTimer = null
  }
}

function stopSessionPoll() {
  if (sessionPollAbort) {
    sessionPollAbort.abort()
    sessionPollAbort = null
  }
}

async function startSessionPoll() {
  stopSessionPoll()
  if (!supportsSessionLogin.value || sessionReady.value || !online.value) return
  sessionPollAbort = new AbortController()
  const signal = sessionPollAbort.signal
  try {
    const session = props.platform === 'aliexpress'
      ? await pollAliExpressSessionUntilReady({ signal })
      : await pollTemuSessionUntilReady({
          timeoutMs: 90000,
          intervalMs: 2000,
          maxIntervalMs: 5000,
          maxAttempts: 20,
          signal,
        })
    if (!signal.aborted) sessionStatus.value = session
  } catch {
    // timeout / cancel
  }
}

function onDownloadHelper() {
  if (!canDownload.value || !openHelperDownload(downloadUrl.value)) {
    ElMessage.warning('请联系管理员获取安装包')
  }
}

async function openBindDialog() {
  bindDialogVisible.value = true
  bindLoading.value = true
  bindInfo.value = null
  try {
    bindInfo.value = await createBindCode()
  } catch (err) {
    ElMessage.error(err.message || '生成绑定码失败')
    bindDialogVisible.value = false
  } finally {
    bindLoading.value = false
  }
}

async function refreshBindCode() {
  bindLoading.value = true
  try {
    bindInfo.value = await createBindCode()
    ElMessage.success('已重新生成绑定码')
  } catch (err) {
    ElMessage.error(err.message || '生成绑定码失败')
  } finally {
    bindLoading.value = false
  }
}

async function copyBindCode() {
  const code = String(bindInfo.value?.code || '')
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('绑定码已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选中绑定码')
  }
}

async function handleOpenLogin() {
  if (!online.value) {
    ElMessage.warning(getAppErrorMessage(offlineErrorCode.value))
    return
  }
  openingKey.value = 'default'
  try {
    if (props.platform === 'aliexpress') {
      await openAliExpressSellerLogin()
    } else {
      await enqueueTemuLogin()
    }
    ElMessage.success('请在本机弹出的浏览器中完成登录')
    await loadSessionStatus()
    void startSessionPoll()
  } catch (err) {
    ElMessage.error(err.message || '打开登录窗口失败')
  } finally {
    openingKey.value = ''
  }
}

async function handleConfirmLogin() {
  if (!online.value) {
    ElMessage.warning(getAppErrorMessage(offlineErrorCode.value))
    return
  }
  await loadSessionStatus({ notifyIfPending: true })
  if (!sessionStatus.value.ready) void startSessionPoll()
}

watch(online, (val) => {
  if (val && supportsSessionLogin.value && !sessionReady.value) {
    void startSessionPoll()
  }
})

onMounted(async () => {
  await reload()
  startHelperPoll()
})

onUnmounted(() => {
  stopHelperPoll()
  stopSessionPoll()
})

defineExpose({ reload, online, sessionReady })
</script>

<template>
  <div class="helper-status-bar" :class="`is-${barTone}`">
    <div class="bar-main">
      <span class="bar-dot" aria-hidden="true" />
      <div class="bar-copy">
        <span class="bar-title">{{ barTitle }}</span>
        <span class="bar-meta">{{ barMeta }}</span>
      </div>
    </div>

    <div class="bar-actions">
      <template v-if="barMode === 'rebind'">
        <el-button
          type="primary"
          size="small"
          :icon="Connection"
          :loading="connecting"
          @click="onConnectHelper"
        >
          连接助手
        </el-button>
        <el-button type="primary" size="small" :icon="Link" @click="openBindDialog">
          生成绑定码
        </el-button>
        <el-button size="small" @click="openHelperPanel">
          打开助手面板
        </el-button>
        <el-button size="small" :icon="Refresh" :loading="helperLoading" @click="reload">
          刷新状态
        </el-button>
      </template>

      <template v-else-if="barMode === 'offline'">
        <el-button
          type="primary"
          size="small"
          :icon="Connection"
          :loading="connecting"
          @click="onConnectHelper"
        >
          连接助手
        </el-button>
        <el-button type="primary" size="small" :icon="Download" native-type="button" @click="onDownloadHelper">
          {{ canDownload ? '下载' : '获取安装包' }}
        </el-button>
        <el-button type="primary" size="small" plain :icon="Link" @click="openBindDialog">
          生成绑定码
        </el-button>
        <el-button size="small" :icon="Refresh" :loading="helperLoading" @click="reload">
          刷新状态
        </el-button>
      </template>

      <template v-else-if="barMode === 'need-login'">
        <el-button
          type="primary"
          size="small"
          :icon="Monitor"
          :loading="Boolean(openingKey)"
          @click="handleOpenLogin"
        >
          打开登录
        </el-button>
        <el-button size="small" :loading="sessionLoading" @click="handleConfirmLogin">
          我已完成登录
        </el-button>
        <el-button text type="primary" size="small" :loading="connecting" @click="onConnectHelper">
          连接助手
        </el-button>
        <el-button text type="primary" size="small" @click="stepsDialogVisible = true">
          查看步骤
        </el-button>
        <el-button text size="small" :icon="Link" @click="openBindDialog">绑定码</el-button>
      </template>

      <template v-else>
        <el-button text type="primary" size="small" :loading="connecting" @click="onConnectHelper">
          连接助手
        </el-button>
        <el-button text type="primary" size="small" :icon="Link" @click="openBindDialog">
          绑定码
        </el-button>
        <el-button
          text
          size="small"
          :icon="Refresh"
          :loading="helperLoading || sessionLoading"
          @click="reload"
        >
          刷新
        </el-button>
      </template>
    </div>
  </div>

  <el-dialog v-model="bindDialogVisible" title="生成绑定码" width="420px" append-to-body destroy-on-close>
    <div v-loading="bindLoading" class="bind-dialog-body">
      <template v-if="bindInfo?.code">
        <p v-if="barMode === 'rebind'" class="bind-hint">
          同一台电脑切换 CrossHub 账号时：先在助手面板点「清除绑定」，再填入下方新码（无需重新下载）。
        </p>
        <p v-else class="bind-hint">请在本机 CrossHub Sync Helper 中填入以下绑定码完成绑定：</p>
        <div class="bind-code">{{ bindInfo.code }}</div>
        <p class="bind-ttl">
          有效期约 {{ ttlLabel || '10 分钟' }}
          <span v-if="bindInfo.expires_at">（至 {{ bindInfo.expires_at }} UTC）</span>
        </p>
      </template>
      <p v-else class="bind-hint">正在生成绑定码…</p>
    </div>
    <template #footer>
      <el-button @click="bindDialogVisible = false">关闭</el-button>
      <el-button :disabled="!bindInfo?.code" @click="copyBindCode">复制绑定码</el-button>
      <el-button type="primary" :loading="bindLoading" @click="refreshBindCode">重新生成</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="stepsDialogVisible" :title="`${platformLabel} 登录步骤`" width="440px" append-to-body>
    <ol class="guide-steps">
      <li>确认本机已运行 <strong>CrossHub Sync Helper</strong> 且已绑定</li>
      <li>点击 <strong>打开登录</strong></li>
      <li>在本机弹出的浏览器中登录 {{ platformLabel }} 卖家后台</li>
      <li>回到本页点击 <strong>我已完成登录</strong>，再点 <strong>刷新数据</strong></li>
    </ol>
    <template #footer>
      <el-button type="primary" @click="stepsDialogVisible = false">知道了</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.helper-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
}
.helper-status-bar.is-warn {
  border-color: color-mix(in srgb, var(--el-color-warning) 35%, var(--el-border-color-lighter));
  background: color-mix(in srgb, var(--el-color-warning-light-9) 80%, white);
}
.helper-status-bar.is-info {
  border-color: color-mix(in srgb, var(--el-color-primary) 28%, var(--el-border-color-lighter));
  background: color-mix(in srgb, var(--el-color-primary-light-9) 70%, white);
}
.helper-status-bar.is-ok {
  border-color: color-mix(in srgb, var(--el-color-success) 30%, var(--el-border-color-lighter));
  background: color-mix(in srgb, var(--el-color-success-light-9) 65%, white);
}
.bar-main { display: flex; align-items: flex-start; gap: 10px; min-width: 0; flex: 1; }
.bar-dot {
  width: 8px; height: 8px; margin-top: 6px; border-radius: 50%; flex-shrink: 0;
  background: var(--el-text-color-secondary);
}
.is-warn .bar-dot { background: var(--el-color-warning); }
.is-info .bar-dot { background: var(--el-color-primary); }
.is-ok .bar-dot { background: var(--el-color-success); }
.bar-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.bar-title { font-size: 13px; font-weight: 600; line-height: 1.4; color: var(--el-text-color-primary); }
.bar-meta { font-size: 12px; line-height: 1.45; color: var(--el-text-color-secondary); }
.bar-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.bind-dialog-body { min-height: 88px; }
.bind-hint { margin: 0 0 12px; line-height: 1.6; color: var(--el-text-color-regular); }
.bind-code {
  font-size: 28px; font-weight: 700; letter-spacing: 0.12em; text-align: center;
  padding: 14px 12px; border-radius: 8px; background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter); user-select: all;
}
.bind-ttl { margin: 12px 0 0; font-size: 13px; color: var(--el-text-color-secondary); text-align: center; }
.guide-steps { margin: 0 0 0 18px; padding: 0; line-height: 1.8; }
</style>
