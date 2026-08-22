<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Link, Refresh } from '@element-plus/icons-vue'
import {
  createBindCode,
  fetchMyAgentStatus,
  resolveHelperDownloadUrl,
} from '@/api/agentHelper'

const loading = ref(false)
const status = ref({ online: false, agents: [], recommended_agent_id: '' })
const bindDialogVisible = ref(false)
const bindLoading = ref(false)
const bindInfo = ref(null)

const agentOnline = computed(() => Boolean(status.value.online))
const downloadUrl = computed(() => resolveHelperDownloadUrl())
const agents = computed(() => (Array.isArray(status.value.agents) ? status.value.agents : []))
const recommendedAgent = computed(() => {
  const id = String(status.value.recommended_agent_id || '')
  return agents.value.find((a) => String(a.id) === id) || agents.value.find((a) => a.online) || null
})

const ttlLabel = computed(() => {
  const sec = Number(bindInfo.value?.expires_in_seconds || 0)
  if (!sec) return ''
  if (sec >= 60) return `${Math.round(sec / 60)} 分钟`
  return `${sec} 秒`
})

async function loadStatus() {
  loading.value = true
  try {
    status.value = await fetchMyAgentStatus()
  } catch (err) {
    ElMessage.error(err.message || '加载助手状态失败')
    status.value = { online: false, agents: [], recommended_agent_id: '' }
  } finally {
    loading.value = false
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

onMounted(loadStatus)

defineExpose({ reload: loadStatus, agentOnline })
</script>

<template>
  <el-card shadow="never" class="temu-agent-panel" v-loading="loading">
    <template #header>
      <div class="panel-header">
        <span>本机同步助手</span>
        <el-button text :icon="Refresh" @click="loadStatus">刷新状态</el-button>
      </div>
    </template>

    <div class="presence-row">
      <el-tag :type="agentOnline ? 'success' : 'warning'" size="small">
        {{ agentOnline ? '在线' : '离线' }}
      </el-tag>
      <span v-if="recommendedAgent?.name" class="node-meta">
        当前：{{ recommendedAgent.name }}
      </span>
      <span v-else-if="agents.length" class="node-meta">
        已绑定 {{ agents.length }} 台设备{{ agentOnline ? '' : '（当前离线）' }}
      </span>
      <span v-else class="node-meta">尚未绑定本机助手</span>
    </div>

    <p class="panel-lead">
      请下载并安装 CrossHub Sync Helper，安装后在助手中填入绑定码。
      登录与数据爬取在您本机执行，服务器只下发任务。
    </p>

    <ol class="panel-steps">
      <li>点击「下载 Sync Helper」安装本机助手</li>
      <li>点击「生成绑定码」，在助手中填入完成绑定</li>
      <li>本页显示「在线」后即可登录 / 刷新数据</li>
    </ol>

    <div class="panel-actions">
      <el-button type="primary" :icon="Download" @click="onDownloadHelper">
        下载 Sync Helper
      </el-button>
      <el-button :icon="Link" @click="openBindDialog">生成绑定码</el-button>
    </div>
  </el-card>

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
</template>

<style scoped>
.temu-agent-panel {
  margin-bottom: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.presence-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.node-meta {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.panel-lead {
  margin: 0 0 10px;
  line-height: 1.6;
}

.panel-steps {
  margin: 0 0 14px 18px;
  padding: 0;
  line-height: 1.7;
}

.panel-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.bind-dialog-body {
  min-height: 88px;
}

.bind-hint {
  margin: 0 0 12px;
  line-height: 1.6;
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
