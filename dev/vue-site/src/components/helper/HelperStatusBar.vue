<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Download, Link, Refresh, Monitor } from '@element-plus/icons-vue'
import {
  createBindCode,
  fetchHelperUpdateInfo,
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
  fetchPddSession,
  enqueuePddLogin,
  pollPddSessionUntilReady,
} from '@/api/pddApi'
import {
  fetchTaobaoSession,
  enqueueTaobaoLogin,
  pollTaobaoSessionUntilReady,
} from '@/api/taobaoApi'
import {
  fetchAliExpressSessionStatus,
  openAliExpressSellerLogin,
  pollAliExpressSessionUntilReady,
} from '@/api/aliexpressApi'
import {
  enqueueDouyinLogin,
  fetchDouyinSession,
  pollDouyinSessionUntilReady,
} from '@/api/douyinApi'
import {
  enqueueAlibaba1688Login,
  fetchAlibaba1688Session,
  fetchAlibaba1688SyncLogs,
  pollAlibaba1688SessionUntilReady,
} from '@/api/alibaba1688Api'
import { getAppErrorMessage, resolveAppError } from '@/utils/appErrorCode'
import { isHelperOutdated } from '@/utils/helperVersion'
import {
  alignLocalDevHelperJava,
  fetchLocalHelperBind,
  fetchLocalInstallInfo,
  getHelperPanelUrl,
  helperApiMismatchHint,
} from '@/utils/agentProbe'
import { useAuthStore } from '@/stores/auth'
import HelperOpsGuideDialog from '@/components/helper/HelperOpsGuideDialog.vue'

const props = defineProps({
  /** temu | aliexpress | amazon | douyin | 1688 | pdd | taobao */
  platform: { type: String, default: 'temu' },
  /** 当前选中店铺（多店铺独立登录时透传给后端） */
  storeId: { type: String, default: null },
})

const emit = defineEmits(['update:online', 'status'])
const auth = useAuthStore()

const helperLoading = ref(false)
const sessionLoading = ref(false)
const openingKey = ref('')
const connecting = ref(false)
const helperStatus = ref({ online: false, agents: [], recommended_agent_id: '' })
const sessionStatus = ref({})
const helperUpdateInfo = ref({})
const localInstall = ref({})
/** 本机助手进程探测结果（与当前用户 Java 在线状态独立） */
const localBind = ref({
  reachable: false,
  bound: false,
  user_id: null,
  tenant_id: null,
  bound_account: '',
  java_api_url: '',
})

const bindDialogVisible = ref(false)
const bindLoading = ref(false)
const bindInfo = ref(null)
const stepsDialogVisible = ref(false)
const updateStepsVisible = ref(false)
const guideDialogVisible = ref(false)
const syncLogVisible = ref(false)
const syncLogs = ref([])
const syncLogLoading = ref(false)

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
  if (props.platform === 'douyin') return '抖店'
  if (props.platform === '1688') return '1688'
  if (props.platform === 'pdd') return '拼多多'
  if (props.platform === 'taobao') return '淘宝'
  return 'Temu'
})

const supportsSessionLogin = computed(
  () =>
    props.platform === 'temu'
    || props.platform === 'aliexpress'
    || props.platform === 'douyin'
    || props.platform === '1688'
    || props.platform === 'pdd'
    || props.platform === 'taobao',
)

const online = computed(() => Boolean(helperStatus.value.online))
const sessionReady = computed(() => {
  if (!supportsSessionLogin.value) return true
  return Boolean(sessionStatus.value.ready || sessionStatus.value.logged_in)
})
const downloadUrl = computed(() => resolveHelperDownloadUrl())
const canDownload = computed(() => Boolean(downloadUrl.value))

const recommendedAgent = computed(() => {
  const id = String(helperStatus.value.recommended_agent_id || '')
  const agents = Array.isArray(helperStatus.value.agents) ? helperStatus.value.agents : []
  return agents.find((a) => String(a.id) === id) || agents.find((a) => a.online) || null
})

const offlineErrorCode = computed(() => {
  if (props.platform === 'aliexpress') return 'AE_USER_HELPER_OFFLINE'
  if (props.platform === 'amazon') return 'AMAZON_USER_HELPER_OFFLINE'
  if (props.platform === 'douyin') return 'DY_AGENT_OFFLINE'
  if (props.platform === '1688') return 'A1688_AGENT_OFFLINE'
  if (props.platform === 'pdd') return 'PDD_AGENT_OFFLINE'
  if (props.platform === 'taobao') return 'TAOBAO_AGENT_OFFLINE'
  return 'TEMU_USER_HELPER_OFFLINE'
})

const currentTenantId = computed(() => {
  const tid = auth.tenantId ?? auth.tenant_id
  return tid != null && !Number.isNaN(Number(tid)) ? Number(tid) : null
})

const localTenantMismatch = computed(() => {
  const localTid = localBind.value.tenant_id
  const currentTid = currentTenantId.value
  return (
    localBind.value.bound
    && localTid != null
    && currentTid != null
    && Number(localTid) !== Number(currentTid)
  )
})

const apiMismatchHint = computed(() =>
  helperApiMismatchHint(localBind.value.live_java_api_url || localBind.value.java_api_url),
)

const barMode = computed(() => {
  if (updateRequired.value) return 'update-required'
  if (apiMismatchHint.value) return 'api-mismatch'
  if (!online.value) {
    // 本机已绑当前企业：不要再显示「未绑定」，只提示等心跳
    if (localBind.value.bound && !localTenantMismatch.value) return 'heartbeat-wait'
    return localBind.value.reachable ? 'rebind' : 'offline'
  }
  if (supportsSessionLogin.value && !sessionReady.value) return 'need-login'
  return 'ready'
})

const updateRequired = computed(() =>
  isHelperOutdated(localInstall.value.version, helperUpdateInfo.value.version),
)

const barTone = computed(() => {
  if (
    barMode.value === 'offline'
    || barMode.value === 'rebind'
    || barMode.value === 'api-mismatch'
    || barMode.value === 'update-required'
  ) return 'warn'
  if (barMode.value === 'need-login' || barMode.value === 'heartbeat-wait') return 'info'
  return 'ok'
})

const barTitle = computed(() => {
  if (barMode.value === 'update-required') return '本机 Sync Helper 需要更新'
  if (barMode.value === 'api-mismatch') return '助手后端地址与当前页面不一致'
  if (barMode.value === 'heartbeat-wait') return '本机助手已绑定，等待心跳同步…'
  if (barMode.value === 'rebind') {
    if (localTenantMismatch.value) return '本机助手已运行，但绑定的是其他企业'
    return '本机助手已运行，但当前企业尚未完成绑定/心跳'
  }
  if (barMode.value === 'offline') return '本机同步助手未在线'
  if (barMode.value === 'need-login') return `助手在线，待登录 ${platformLabel.value}`
  const name = recommendedAgent.value?.name
  return name ? `助手在线 · ${name}` : '助手在线 · 可同步'
})

const barMeta = computed(() => {
  if (barMode.value === 'update-required') {
    return `当前版本 ${localInstall.value.version || '未知'} · 最新版本 ${helperUpdateInfo.value.version || '—'}。请重新下载安装包覆盖安装后重启助手。`
  }
  if (barMode.value === 'api-mismatch') return apiMismatchHint.value
  if (barMode.value === 'heartbeat-wait') {
    return '绑定码已核销；若超过 1 分钟仍不变，请点「刷新状态」或用本地脚本重启助手'
  }
  if (barMode.value === 'rebind') {
    if (localTenantMismatch.value) {
      return `助手当前租户 #${localBind.value.tenant_id}，与登录企业 #${currentTenantId.value} 不一致。请清除绑定后用本企业账号重新填入绑定码（同企业多账号共享，无需每人各绑一次）`
    }
    return '同企业任意账号生成绑定码填入助手即可；绑定后本机同企业账号共享在线状态。若已绑定仍提示，请点「连接助手」或刷新状态'
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
    // Local Vite: auto-heal helper if it still points at www.yoto.work
    await alignLocalDevHelperJava(1500)
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
  void alignLocalDevHelperJava(1500).finally(() => {
    window.open(getHelperPanelUrl(), '_blank', 'noopener')
  })
}

async function loadSessionStatus({ notifyIfPending = false } = {}) {
  if (!supportsSessionLogin.value) {
    sessionStatus.value = { ready: true }
    return
  }
  sessionLoading.value = true
  try {
    if (props.platform === 'aliexpress') {
      sessionStatus.value = await fetchAliExpressSessionStatus()
    } else if (props.platform === 'douyin') {
      sessionStatus.value = await fetchDouyinSession()
    } else if (props.platform === '1688') {
      sessionStatus.value = await fetchAlibaba1688Session({ storeId: props.storeId })
    } else if (props.platform === 'pdd') {
      sessionStatus.value = await fetchPddSession({ storeId: props.storeId })
    } else if (props.platform === 'taobao') {
      sessionStatus.value = await fetchTaobaoSession()
    } else {
      sessionStatus.value = await fetchTemuSessionStatus()
    }
    if (notifyIfPending && !sessionReady.value) {
      ElMessage.warning(
        sessionStatus.value.message
          || getAppErrorMessage(
            props.platform === 'aliexpress'
              ? 'CRAWL_AE_NOT_LOGGED_IN'
              : props.platform === 'douyin'
                ? 'DY_NOT_LOGGED_IN'
                : props.platform === '1688'
                  ? 'A1688_NOT_LOGGED_IN'
                  : props.platform === 'pdd'
                    ? 'PDD_NOT_LOGGED_IN'
                    : props.platform === 'taobao'
                      ? 'TAOBAO_NOT_LOGGED_IN'
                  : 'CRAWL_NOT_LOGGED_IN',
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
  await Promise.all([loadHelperStatus(), loadSessionStatus(), loadUpdateInfo()])
  // Avoid auto live-probes on page load; poll only after「打开登录」/确认登录.
}

async function loadUpdateInfo() {
  try {
    helperUpdateInfo.value = (await fetchHelperUpdateInfo()) || {}
  } catch {
    helperUpdateInfo.value = {}
  }
  try {
    localInstall.value = (await fetchLocalInstallInfo(1500)) || {}
  } catch {
    localInstall.value = {}
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
    let session
    if (props.platform === 'aliexpress') {
      session = await pollAliExpressSessionUntilReady({ signal })
    } else if (props.platform === 'douyin') {
      session = await pollDouyinSessionUntilReady({
        timeoutMs: 90000,
        intervalMs: 2000,
        maxIntervalMs: 5000,
        signal,
        storeId: props.storeId,
      })
    } else if (props.platform === '1688') {
      session = await pollAlibaba1688SessionUntilReady({
        timeoutMs: 90000,
        intervalMs: 2000,
        maxIntervalMs: 5000,
        signal,
        storeId: props.storeId,
      })
    } else if (props.platform === 'pdd') {
      session = await pollPddSessionUntilReady({
        timeoutMs: 90000,
        intervalMs: 2000,
        maxIntervalMs: 5000,
        signal,
        storeId: props.storeId,
      })
    } else if (props.platform === 'taobao') {
      session = await pollTaobaoSessionUntilReady({
        timeoutMs: 90000,
        intervalMs: 2000,
        maxIntervalMs: 5000,
        signal,
        storeId: props.storeId,
      })
    } else {
      session = await pollTemuSessionUntilReady({
        timeoutMs: 90000,
        intervalMs: 2000,
        maxIntervalMs: 5000,
        maxAttempts: 20,
        signal,
      })
    }
    if (!signal.aborted) sessionStatus.value = session
  } catch {
    // timeout / cancel
  }
}

function onDownloadHelper() {
  if (!canDownload.value || !openHelperDownload(downloadUrl.value)) {
    ElMessage.warning('请联系管理员获取安装包')
    return
  }
  ElMessage.success({
    message: '开始下载。解压后请双击 SETUP.cmd 启动助手，再回本页生成绑定码并「打开登录」',
    duration: 8000,
  })
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
    let openRes = null
    if (props.platform === 'aliexpress') {
      openRes = await openAliExpressSellerLogin()
    } else if (props.platform === 'douyin') {
      openRes = await enqueueDouyinLogin({ storeId: props.storeId })
    } else if (props.platform === '1688') {
      openRes = await enqueueAlibaba1688Login({ storeId: props.storeId })
    } else if (props.platform === 'pdd') {
      openRes = await enqueuePddLogin({ storeId: props.storeId })
    } else if (props.platform === 'taobao') {
      openRes = await enqueueTaobaoLogin({ storeId: props.storeId })
    } else {
      openRes = await enqueueTemuLogin({
        tenantId: currentTenantId.value,
      })
    }
    if (openRes?.already_open || openRes?.queued === false) {
      ElMessage.warning(
        openRes?.message
          || '登录任务仍在进行；若本机没有弹出浏览器：请重启 Sync Helper（或双击 SETUP.cmd）后再点「打开登录」',
      )
    } else {
      ElMessage.success(openRes?.message || '请在本机弹出的浏览器中完成登录（看任务栏是否已打开 Chrome）')
    }
    if (props.platform === '1688' && openRes?.queued !== false) {
      void poll1688LoginProgress()
    }
    void loadSessionStatus()
    void startSessionPoll()
  } catch (err) {
    ElMessage.error(err.message || '打开登录窗口失败')
  } finally {
    openingKey.value = ''
  }
}

async function poll1688LoginProgress() {
  const { fetchAlibaba1688LoginStatus } = await import('@/api/alibaba1688Api')
  let warnedQueued = false
  const deadline = Date.now() + 5 * 60 * 1000
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 3000))
    try {
      const st = await fetchAlibaba1688LoginStatus()
      if (st?.status === 'running') {
        ElMessage.info('登录窗口正在打开…请在运行本机助手的电脑上完成登录（留意任务栏 Chrome）')
        return
      }
      if (st?.status === 'failed') {
        ElMessage.error(st.error_message || '登录窗口打开失败，请重新点击「打开登录」')
        return
      }
      if (st?.status === 'success' || sessionStatus.value?.logged_in) {
        ElMessage.success('1688 已登录')
        return
      }
      if (st?.status === 'pending' && !warnedQueued) {
        warnedQueued = true
        ElMessage.warning('登录任务排队中：前面有 1688 任务在执行，请稍候…')
      }
    } catch (err) {
      return
    }
  }
  ElMessage.warning('登录窗口打开较慢：请确认本机助手在运行；仍未弹出请重启 Sync Helper 后重试')
}

async function handleConfirmLogin() {
  if (!online.value) {
    ElMessage.warning(getAppErrorMessage(offlineErrorCode.value))
    return
  }
  await loadSessionStatus({ notifyIfPending: true })
  if (!sessionStatus.value.ready) void startSessionPoll()
}

async function openSyncLog() {
  if (props.platform !== '1688') return
  syncLogVisible.value = true
  await loadSyncLog()
}

async function loadSyncLog() {
  syncLogLoading.value = true
  try {
    const data = await fetchAlibaba1688SyncLogs({ limit: 30 })
    syncLogs.value = Array.isArray(data?.items) ? data.items : []
  } catch {
    syncLogs.value = []
  } finally {
    syncLogLoading.value = false
  }
}

function durationText(ms) {
  const value = Number(ms)
  if (!Number.isFinite(value) || value < 0) return '—'
  if (value < 1000) return `${value}ms`
  const sec = Math.round(value / 1000)
  if (sec < 60) return `${sec} 秒`
  return `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
}

function logStatusType(status) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}

function logSummaryText(summary) {
  if (!summary || typeof summary !== 'object') return ''
  const parts = []
  if (summary.orders_count != null) parts.push(`订单 ${summary.orders_count}`)
  if (summary.items_count != null) parts.push(`行 ${summary.items_count}`)
  if (summary.refunds_count != null) parts.push(`退款 ${summary.refunds_count}`)
  if (summary.products_count != null) parts.push(`商品 ${summary.products_count}`)
  if (summary.count != null) parts.push(`商品 ${summary.count}`)
  if (summary.category_failed != null && Number(summary.category_failed) > 0) {
    parts.push(`分类失败 ${summary.category_failed}`)
  }
  if (summary.partial === true) parts.push('部分完成')
  return parts.join(' · ')
}

watch(online, () => {
  // Online alone must not start live session probes.
})

watch(() => props.storeId, () => {
  // 切换店铺后重新加载该店铺的会话状态，避免状态栏停留在上一个店铺的登录态
  if (props.storeId == null) return
  sessionStatus.value = {}
  loadSessionStatus()
})

onMounted(async () => {
  await reload()
  startHelperPoll()
})

onUnmounted(() => {
  stopHelperPoll()
  stopSessionPoll()
})

defineExpose({ reload, online, sessionReady, openBindDialog })
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
      <template v-if="barMode === 'update-required'">
        <el-button type="primary" size="small" :icon="Download" @click="onDownloadHelper">
          立即下载更新
        </el-button>
        <el-button size="small" @click="updateStepsVisible = true">
          查看更新步骤
        </el-button>
        <el-button size="small" :icon="Refresh" :loading="helperLoading" @click="reload">
          刷新
        </el-button>
      </template>

      <template v-if="barMode === 'api-mismatch'">
        <el-button type="primary" size="small" @click="openHelperPanel">
          打开助手面板
        </el-button>
        <el-button type="primary" size="small" plain :icon="Link" @click="openBindDialog">
          生成绑定码
        </el-button>
        <el-button size="small" :icon="Refresh" :loading="helperLoading" @click="reload">
          刷新状态
        </el-button>
      </template>

      <template v-else-if="barMode === 'rebind' || barMode === 'heartbeat-wait'">
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
        <el-button text type="primary" size="small" :icon="Link" @click="openBindDialog">
          生成绑定码
        </el-button>
        <el-button text type="primary" size="small" @click="stepsDialogVisible = true">
          查看步骤
        </el-button>
      </template>

      <template v-else>
        <el-button
          v-if="supportsSessionLogin"
          type="primary"
          size="small"
          plain
          :icon="Monitor"
          :loading="Boolean(openingKey)"
          @click="handleOpenLogin"
        >
          重新登录
        </el-button>
        <el-button
          v-if="supportsSessionLogin"
          size="small"
          :loading="sessionLoading"
          @click="handleConfirmLogin"
        >
          刷新登录状态
        </el-button>
        <el-button text type="primary" size="small" :loading="connecting" @click="onConnectHelper">
          连接助手
        </el-button>
        <el-button text type="primary" size="small" :icon="Link" @click="openBindDialog">
          生成绑定码
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

      <el-button text type="primary" size="small" @click="guideDialogVisible = true">
        操作指南
      </el-button>
      <el-button v-if="platform === '1688'" text type="primary" size="small" @click="openSyncLog">
        同步日志
      </el-button>
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
          <span v-if="bindInfo.expires_at">（至 {{ formatUtc8(bindInfo.expires_at) }}）</span>
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
      <el-button @click="stepsDialogVisible = false">关闭</el-button>
      <el-button type="primary" @click="stepsDialogVisible = false; guideDialogVisible = true">
        完整操作指南
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="updateStepsVisible" title="更新本机 Sync Helper" width="460px" append-to-body>
    <ol class="guide-steps">
      <li>点击「立即下载更新」获取最新安装包（约 110MB）</li>
      <li>解压后覆盖原目录（确保旧文件全部替换）</li>
      <li>双击 <strong>SETUP.cmd</strong>（或 CrossHub-Sync-Helper.exe）启动</li>
      <li>回到本页点「刷新」，确认版本为最新后再使用 1688 新功能</li>
    </ol>
    <template #footer>
      <el-button @click="updateStepsVisible = false">关闭</el-button>
      <el-button type="primary" @click="onDownloadHelper">立即下载更新</el-button>
    </template>
  </el-dialog>

  <HelperOpsGuideDialog v-model="guideDialogVisible" />

  <el-drawer v-model="syncLogVisible" title="1688 同步日志" size="520px" append-to-body>
    <div class="sync-log-toolbar">
      <el-text type="info" size="small">最近 30 次商品/订单同步记录</el-text>
      <el-button size="small" :loading="syncLogLoading" @click="loadSyncLog">刷新</el-button>
    </div>
    <el-table v-loading="syncLogLoading" :data="syncLogs" size="small" empty-text="暂无同步记录">
      <el-table-column prop="label" label="类型" width="90" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="logStatusType(row.status)" size="small">
            {{ row.status === 'success' ? '成功' : row.status === 'failed' ? '失败' : row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="startedAt" label="开始时间" width="150" />
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">{{ durationText(row.durationMs) }}</template>
      </el-table-column>
      <el-table-column label="结果 / 错误" min-width="160">
        <template #default="{ row }">
          <span v-if="row.status === 'success'">{{ logSummaryText(row.summary) || '成功' }}</span>
          <span v-else>{{ row.errorMessage || row.errorCode || '失败' }}</span>
        </template>
      </el-table-column>
    </el-table>
  </el-drawer>
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
.sync-log-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
</style>
