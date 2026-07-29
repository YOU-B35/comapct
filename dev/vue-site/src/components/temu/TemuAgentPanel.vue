<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import { fetchTemuIntegrationStatus } from '@/api/temuApi'
import { setupLocalAgent } from '@/api/agentApi'
import {
  CROSSHUB_SYNC_HELPER_FILENAME,
  downloadCrossHubSyncHelper,
  getLauncherRootHint,
} from '@/utils/agentLauncher'
import { probeLocalAgent } from '@/utils/agentProbe'
import { resolveAgentPresence } from '@/utils/agentPresence'
import AgentPresenceStatus from '@/components/agent/AgentPresenceStatus.vue'
import { canUseOpsManualSync } from '@/utils/opsSyncPolicy'

const loading = ref(false)
const downloading = ref(false)
const agentName = ref('本机 Temu 助手')
const integration = ref({})
const localAgentOnline = ref(false)
const allowHelperDownload = computed(() => canUseOpsManualSync())

const presence = computed(() =>
  resolveAgentPresence({
    tenantOnline: Boolean(integration.value.agent_online),
    localProcessOnline: localAgentOnline.value,
  }),
)
/** 业务在线 = 当前企业心跳，不用本机端口冒充 */
const agentOnline = computed(() => presence.value.tenantOnline)

async function loadStatus() {
  loading.value = true
  try {
    const [statusRes, agentReady] = await Promise.all([
      fetchTemuIntegrationStatus(),
      probeLocalAgent(),
    ])
    integration.value = statusRes.data || {}
    localAgentOnline.value = agentReady
  } catch (err) {
    ElMessage.error(err.message || '加载助手状态失败')
  } finally {
    loading.value = false
  }
}

async function onDownloadLauncher() {
  downloading.value = true
  try {
    const res = await setupLocalAgent(agentName.value.trim() || '本机 Temu 助手')
    downloadCrossHubSyncHelper(res.data)
    ElMessage.success(
      `已下载「${CROSSHUB_SYNC_HELPER_FILENAME}」。请先关闭旧的助手黑窗口，再双击新文件并保持打开`,
    )
    await loadStatus()
  } catch (err) {
    ElMessage.error(err.message || '下载同步助手失败')
  } finally {
    downloading.value = false
  }
}

onMounted(loadStatus)

defineExpose({ reload: loadStatus, agentOnline })
</script>

<template>
  <el-card shadow="never" class="temu-agent-panel" v-loading="loading">
    <template #header>
      <div class="panel-header">
        <span>本机同步助手（肉鸡）</span>
        <el-button text :icon="Refresh" @click="loadStatus">刷新状态</el-button>
      </div>
    </template>

    <AgentPresenceStatus
      :tenant-online="Boolean(integration.agent_online)"
      :local-process-online="localAgentOnline"
    >
      <template #extra>
        <span v-if="integration.node_name" class="node-meta">
          节点：{{ integration.node_name }}
        </span>
      </template>
    </AgentPresenceStatus>

    <p v-if="!allowHelperDownload" class="panel-lead">
      同步助手仅部署在运维肉机，由服务端每天定时下发任务。运营网页不提供下载或手动同步入口。
    </p>
    <template v-else>
    <p class="panel-lead">
      Temu / Amazon 等平台共用<strong>同一助手进程</strong>，但启动文件里的凭证绑定<strong>当前登录企业</strong>。
      登录与数据爬取在您本机 Windows 执行，服务器只下发任务。
    </p>

    <ol class="panel-steps">
      <li>点击下方按钮下载 <code>{{ CROSSHUB_SYNC_HELPER_FILENAME }}</code>（凭证已写入，无需复制 Token）</li>
      <li>先关闭本机已有助手黑窗口，再双击<strong>刚下载</strong>的文件，并保持打开</li>
      <li>回到本页点「刷新状态」，显示「当前企业助手 在线」后即可登录 / 刷新数据</li>
    </ol>

    <div class="panel-actions">
      <el-input
        v-model="agentName"
        placeholder="助手名称（可选）"
        style="max-width: 220px"
      />
      <el-button type="primary" :icon="Download" :loading="downloading" @click="onDownloadLauncher">
        下载并安装本机助手
      </el-button>
    </div>

    <p class="panel-hint">
      项目路径参考：{{ getLauncherRootHint() }}（若路径不对，请联系 IT 调整环境变量
      <code>VITE_AGENT_LAUNCHER_ROOT</code>）
    </p>
    </template>
  </el-card>
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

.temu-agent-panel :deep(.agent-presence-status) {
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

.panel-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
</style>
