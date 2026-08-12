<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { formatCaughtError } from '@/utils/appErrorCode'
import { loadOperationsOverview } from '@/api/operationsOverview'
import OperationsSummaryHeader from '@/components/dashboard/OperationsSummaryHeader.vue'
import OpsAnalyticsCharts from '@/components/dashboard/OpsAnalyticsCharts.vue'
import OperationsIssuesPanel from '@/components/dashboard/OperationsIssuesPanel.vue'
import OperationsTasksPanel from '@/components/dashboard/OperationsTasksPanel.vue'
import DailyOpsReportPanel from '@/components/dashboard/DailyOpsReportPanel.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'

const auth = useAuthStore()
const loading = ref(false)
const context = ref(null)
const highlightPlatformId = ref('')

const overview = computed(() => {
  if (!context.value) return null
  return {
    platforms: context.value.platforms,
    totalIssues: context.value.totalIssues,
    syncedAt: context.value.syncedAt,
  }
})

const platformSales = computed(() => context.value?.platformSales || [])
const tasks = computed(() => context.value?.tasks || [])
const dailyReport = computed(() => context.value?.dailyReport || null)

async function refresh() {
  loading.value = true
  try {
    const res = await loadOperationsOverview(auth)
    context.value = res.data
  } catch (err) {
    context.value = null
    ElMessage.warning(formatCaughtError(err, '运营总览加载失败，请稍后重试'))
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
onActivated(refresh)
</script>

<template>
  <PageScroll>
    <PageHeader
      title="运营工作台"
      eyebrow="Boss"
      description="数据来自账户绑定店铺与员工分配，按负责人汇总"
    >
      <template #actions>
        <el-button :icon="Refresh" size="small" :loading="loading" @click="refresh">
          刷新
        </el-button>
      </template>
    </PageHeader>

    <div v-loading="loading" class="ops-dashboard">
    <PageSection flush class="ops-summary-section">
      <OperationsSummaryHeader
        :overview="overview"
        :platform-sales="platformSales"
        :tasks="tasks"
        :highlight-platform-id="highlightPlatformId"
      />
    </PageSection>

      <PageSection title="运营数据分析">
        <OpsAnalyticsCharts
          :key="`ops-charts-${platformSales.length}-${tasks.length}`"
          :platform-sales="platformSales"
          :overview="overview"
          :tasks="tasks"
          :highlight-platform-id="highlightPlatformId"
          @select-platform="highlightPlatformId = $event"
        />
      </PageSection>

      <PageSection title="日报">
        <DailyOpsReportPanel :report="dailyReport" :loading="loading" />
      </PageSection>

      <PageSection title="异常与预警">
        <OperationsIssuesPanel :overview="overview" />
      </PageSection>

      <PageSection title="任务进展">
        <OperationsTasksPanel :tasks="tasks" />
      </PageSection>
    </div>
  </PageScroll>
</template>

<style scoped>
.ops-dashboard {
  display: grid;
  gap: 4px;
}
</style>
