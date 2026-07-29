<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchAmazonIntegrationStatus } from '@/api/agentApi'
import { probeLocalZiniao } from '@/utils/ziniaoProbe'
import { probeLocalAgent } from '@/utils/agentProbe'
import { resolveAgentPresence } from '@/utils/agentPresence'
import AgentPresenceStatus from '@/components/agent/AgentPresenceStatus.vue'

const props = defineProps({
  compact: { type: Boolean, default: false },
})

const router = useRouter()
const loading = ref(false)
const status = ref({})
const localZiniaoOnline = ref(false)
const localAgentOnline = ref(false)

const presence = computed(() =>
  resolveAgentPresence({
    tenantOnline: Boolean(status.value.agent_online),
    localProcessOnline: localAgentOnline.value,
  }),
)
const agentOnline = computed(() => presence.value.tenantOnline)
const ziniaoOnline = computed(() => localZiniaoOnline.value || Boolean(status.value.ziniao_online))
const allReady = computed(() => agentOnline.value && ziniaoOnline.value)

async function loadStatus() {
  loading.value = true
  try {
    const [res, ziniaoReady, agentReady] = await Promise.all([
      fetchAmazonIntegrationStatus(),
      probeLocalZiniao(),
      probeLocalAgent(),
    ])
    status.value = res.data || {}
    localZiniaoOnline.value = ziniaoReady
    localAgentOnline.value = agentReady
  } catch {
    status.value = {}
    localZiniaoOnline.value = false
    localAgentOnline.value = false
  } finally {
    loading.value = false
  }
}

function goAccountBinding() {
  router.push('/boss/accounts')
}

onMounted(loadStatus)

defineExpose({ reload: loadStatus, allReady })
</script>

<template>
  <div v-if="!loading && !allReady" class="amazon-integration-guide" :class="{ 'is-compact': compact }">
    <AgentPresenceStatus
      :tenant-online="Boolean(status.agent_online)"
      :local-process-online="localAgentOnline"
      compact
    />
    <el-alert
      :type="presence.tenantMismatch ? 'warning' : agentOnline ? 'warning' : 'error'"
      show-icon
      :closable="false"
      class="guide-alert"
    >
      <template #title>
        <template v-if="presence.tenantMismatch">本机同步程序与当前企业不匹配</template>
        <template v-else-if="agentOnline">紫鸟未就绪</template>
        <template v-else>本机同步程序未在线</template>
      </template>
      <template #default>
        <ol class="guide-steps">
          <li>联系运维确认已安装并启动 <code>CrossHub-Sync-Helper.exe</code>（运维机常驻，不在网页下载）</li>
          <li v-if="presence.tenantMismatch">
            关闭旧进程后，用<strong>当前企业</strong>对应的 config.json（含正确 agent_token）重启 exe
          </li>
          <li v-else>
            Amazon 另需紫鸟 WebDriver（exe 可自动拉起）；保持程序窗口不要关闭
          </li>
          <li>就绪后到 <el-link type="primary" @click="goAccountBinding">账户绑定</el-link> 从紫鸟导入店铺</li>
        </ol>
        <p class="guide-note">运营网页不再提供助手下载入口；日批同步由服务端 09:30 下发，本机 exe 执行浏览器任务。</p>
        <div class="guide-actions">
          <el-button size="small" @click="loadStatus">重新检测</el-button>
        </div>
      </template>
    </el-alert>
  </div>
</template>

<style scoped>
.amazon-integration-guide {
  margin-bottom: 16px;
}

.guide-alert {
  margin-top: 10px;
}

.guide-steps {
  margin: 8px 0 8px 18px;
  padding: 0;
  line-height: 1.7;
}

.guide-note {
  margin: 0 0 12px;
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
