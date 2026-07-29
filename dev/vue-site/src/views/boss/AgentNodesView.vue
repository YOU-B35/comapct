<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import { fetchAmazonIntegrationStatus } from '@/api/agentApi'
import { probeLocalAgent } from '@/utils/agentProbe'
import { resolveAgentPresence } from '@/utils/agentPresence'
import AgentPresenceStatus from '@/components/agent/AgentPresenceStatus.vue'

const loading = ref(false)
const integration = ref({})
const localAgentOnline = ref(false)

async function loadAll() {
  loading.value = true
  try {
    const [statusRes, agentReady] = await Promise.all([
      fetchAmazonIntegrationStatus(),
      probeLocalAgent(),
    ])
    integration.value = statusRes.data || {}
    localAgentOnline.value = agentReady
    resolveAgentPresence({
      tenantOnline: Boolean(integration.value.agent_online),
      localProcessOnline: localAgentOnline.value,
    })
  } catch (err) {
    ElMessage.error(err.message || '加载状态失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="agent-nodes-page">
    <PageHeader title="本机同步程序（运维）">
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新状态</el-button>
      </template>
    </PageHeader>
    <PageScroll>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="已改为独立程序，不对运营前端开放下载"
        description="浏览器定时同步请在运维机安装并常驻运行 CrossHub-Sync-Helper.exe。打包：powershell -File scripts/build-sync-helper-exe.ps1。配置 token：scripts/setup-sync-helper-config.ps1。本页仅供运维查看心跳，菜单已对运营隐藏。"
        class="mb"
      />
      <el-card shadow="never" v-loading="loading">
        <AgentPresenceStatus
          :tenant-online="Boolean(integration.agent_online)"
          :local-process-online="localAgentOnline"
        />
        <p v-if="integration.node_name" class="meta">节点：{{ integration.node_name }}</p>
        <p v-if="integration.last_heartbeat_at" class="meta">最近心跳：{{ integration.last_heartbeat_at }}</p>
      </el-card>
    </PageScroll>
  </div>
</template>

<style scoped>
.mb { margin-bottom: 16px; }
.meta {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
