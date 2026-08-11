<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Link } from '@element-plus/icons-vue'
import {
  createBindCode,
  fetchMyAgentStatus,
  resolveHelperDownloadUrl,
} from '@/api/agentHelper'

const emit = defineEmits(['update:online', 'status'])

const loading = ref(false)
const status = ref({ online: false, agents: [], recommended_agent_id: '' })
const bindDialogVisible = ref(false)
const bindLoading = ref(false)
const bindInfo = ref(null)

let pollTimer = null

const online = computed(() => Boolean(status.value.online))
const downloadUrl = computed(() => resolveHelperDownloadUrl())
const recommendedAgent = computed(() => {
  const id = String(status.value.recommended_agent_id || '')
  const agents = Array.isArray(status.value.agents) ? status.value.agents : []
  return agents.find((a) => String(a.id) === id) || agents.find((a) => a.online) || null
})

const ttlLabel = computed(() => {
  const sec = Number(bindInfo.value?.expires_in_seconds || 0)
  if (!sec) return ''
  if (sec >= 60) return `${Math.round(sec / 60)} 分钟`
  return `${sec} 秒`
})

function publishStatus() {
  emit('update:online', online.value)
  emit('status', status.value)
}

async function loadStatus() {
  loading.value = true
  try {
    status.value = await fetchMyAgentStatus()
    publishStatus()
  } catch {
    status.value = { online: false, agents: [], recommended_agent_id: '' }
    publishStatus()
  } finally {
    loading.value = false
  }
}

function startStatusPoll() {
  stopStatusPoll()
  pollTimer = window.setInterval(() => {
    if (document.visibilityState === 'hidden') return
    void loadStatus()
  }, 15000)
}

function stopStatusPoll() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function onDownloadHelper() {
  const url = downloadUrl.value
  if (!url) {
    ElMessage.warning('请联系管理员获取安装包')
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
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

onMounted(async () => {
  await loadStatus()
  startStatusPoll()
})

onUnmounted(() => {
  stopStatusPoll()
})

defineExpose({ reload: loadStatus, online })
</script>

<template>
  <el-alert
    v-if="!loading && !online"
    type="warning"
    show-icon
    :closable="false"
    class="temu-helper-banner"
    title="本机同步助手未在线"
  >
    <template #default>
      <p class="banner-copy">
        请下载并安装 CrossHub Sync Helper，安装后在助手中填入绑定码
      </p>
      <div class="banner-actions">
        <el-button type="primary" size="small" :icon="Download" @click="onDownloadHelper">
          下载 Sync Helper
        </el-button>
        <el-button type="primary" size="small" plain :icon="Link" @click="openBindDialog">
          生成绑定码
        </el-button>
        <el-button size="small" :loading="loading" @click="loadStatus">刷新状态</el-button>
      </div>
    </template>
  </el-alert>

  <el-alert
    v-else-if="!loading && online"
    type="success"
    show-icon
    :closable="false"
    class="temu-helper-banner is-online"
    :title="recommendedAgent?.name ? `助手在线 · ${recommendedAgent.name}` : '助手在线'"
  >
    <template #default>
      <p class="banner-online-meta">
        可在本机完成 Temu 登录与数据同步。
        <el-button text type="primary" size="small" @click="openBindDialog">生成绑定码</el-button>
        <el-button text size="small" :loading="loading" @click="loadStatus">刷新</el-button>
      </p>
    </template>
  </el-alert>

  <el-dialog
    v-model="bindDialogVisible"
    title="生成绑定码"
    width="420px"
    append-to-body
    destroy-on-close
  >
    <div v-loading="bindLoading" class="bind-dialog-body">
      <template v-if="bindInfo?.code">
        <p class="bind-hint">请在本机 CrossHub Sync Helper 中填入以下绑定码完成绑定：</p>
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
</template>

<style scoped>
.temu-helper-banner {
  margin-bottom: 12px;
}

.banner-copy {
  margin: 0 0 10px;
  line-height: 1.6;
}

.banner-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.banner-online-meta {
  margin: 0;
  line-height: 1.6;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.bind-dialog-body {
  min-height: 88px;
}

.bind-hint {
  margin: 0 0 12px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}

.bind-code {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-align: center;
  padding: 14px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  user-select: all;
}

.bind-ttl {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-align: center;
}
</style>
