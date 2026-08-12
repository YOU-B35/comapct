<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  CircleCheckFilled,
  Right,
  ShoppingCart,
  TrendCharts,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { loadOperationsOverview } from '@/api/operationsOverview'
import { calcTaskStats } from '@/utils/operations'
import MetricCards from '@/components/dashboard/MetricCards.vue'
import OpsAnalyticsCharts from '@/components/dashboard/OpsAnalyticsCharts.vue'
import PlatformIssuesOverview from '@/components/dashboard/PlatformIssuesOverview.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'

const auth = useAuthStore()
const router = useRouter()
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
const assignedStores = computed(() => {
  const stores = context.value?.stores
  if (!stores) return []
  return [
    ...(stores.temu || []),
    ...(stores.aliexpress || []),
    ...(stores.walmart || []),
    ...(stores.pdd || []),
    ...(stores.douyin || []),
    ...(stores.channels || []),
    ...(stores['1688'] || []),
    ...(stores.dtc || []),
  ]
})

const platformLabels = computed(() => {
  const labels = (auth.employee.platforms || []).map((p) => {
    if (p === 'temu') return 'Temu'
    if (p === 'aliexpress') return 'AliExpress'
    if (p === 'walmart') return 'Walmart'
    if (p === 'pdd') return '拼多多'
    if (p === 'douyin') return '抖音'
    if (p === 'channels') return '视频号'
    if (p === '1688') return '1688'
    if (p === 'shopify' || p === 'wordpress') return '独立站'
    return p
  })
  return [...new Set(labels)].join('、') || '未分配平台'
})

const metrics = computed(() => {
  const list = platformSales.value
  const revenue = list.reduce((s, p) => s + (p.revenue || 0), 0)
  const orders = list.reduce((s, p) => s + (p.orders || 0), 0)
  const alerts = list.reduce((s, p) => s + (p.alerts || 0), 0)
  const stats = calcTaskStats(tasks.value)

  return [
    {
      label: '我的销售额',
      value: revenue,
      isMoney: true,
      hint: platformLabels.value,
      tone: 'primary',
      icon: TrendCharts,
    },
    {
      label: '我的订单',
      value: orders,
      hint: '负责店铺汇总',
      tone: 'info',
      icon: ShoppingCart,
    },
    {
      label: '待处理预警',
      value: alerts,
      hint: '需今日跟进',
      tone: alerts ? 'danger' : 'success',
      icon: WarningFilled,
    },
    {
      label: '任务完成率',
      value: stats.completionRate,
      suffix: '%',
      hint: `${stats.completed}/${stats.total} 已完成`,
      tone: 'success',
      icon: CircleCheckFilled,
    },
  ]
})

const platformCards = computed(() =>
  platformSales.value.map((row) => {
    const platform = overview.value?.platforms?.find((p) => p.id === row.id)
    return {
      ...row,
      issueCount: platform?.issueCount ?? row.alerts ?? 0,
    }
  }),
)

const platformRouteMap = {
  temu: 'temu',
  aliexpress: 'aliexpress',
  walmart: 'walmart',
  pdd: 'pdd',
  douyin: 'douyin',
  channels: 'channels',
  amazon: 'amazon',
  '1688': '1688',
  dtc: 'dtc',
}

function goPlatform(platformId) {
  const segment = platformRouteMap[platformId]
  if (!segment) return
  router.push(`/employee/${segment}`)
}

async function loadContext() {
  loading.value = true
  try {
    const res = await loadOperationsOverview(auth)
    context.value = res.data
  } catch {
    context.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadContext)
</script>

<template>
  <PageScroll>
    <PageHeader
      :title="`${auth.employee.name} 的工作台`"
      eyebrow="员工"
      :description="`仅展示你负责的 ${platformLabels} 数据（${assignedStores.length} 家店铺）`"
    />

    <PageSection flush class="employee-kpi-section">
      <MetricCards v-loading="loading" :metrics="metrics" />
    </PageSection>

    <PageSection title="经营分析">
      <OpsAnalyticsCharts
        :platform-sales="platformSales"
        :overview="overview"
        :tasks="tasks"
        :highlight-platform-id="highlightPlatformId"
        @select-platform="highlightPlatformId = $event"
      />
    </PageSection>

    <PageSection title="平台异常概览">
      <PlatformIssuesOverview />
    </PageSection>

    <PageSection title="我的平台" description="点击进入对应运营模块">
      <div v-loading="loading">
        <el-empty
          v-if="!loading && !platformCards.length"
          description="暂无负责店铺数据，请联系企业管理员在运营绑定中分配店铺"
        />
        <div v-else class="platform-cards">
          <button
            v-for="card in platformCards"
            :key="card.id"
            type="button"
            class="platform-card"
            :class="{ 'is-highlighted': highlightPlatformId && highlightPlatformId === card.id }"
            @click="goPlatform(card.id)"
          >
            <div class="platform-card__top">
              <strong>{{ card.name }}</strong>
              <el-tag
                :type="card.issueCount ? 'danger' : 'success'"
                size="small"
                effect="plain"
              >
                {{ card.issueCount ? `${card.issueCount} 待跟进` : '正常' }}
              </el-tag>
            </div>
            <div class="platform-card__metrics">
              <span class="platform-card__metric">
                <em>销售额</em>
                {{ card.revenueText }}
              </span>
              <span class="platform-card__metric">
                <em>订单</em>
                {{ card.orders }}
              </span>
              <span class="platform-card__metric">
                <em>店铺</em>
                {{ card.storeCount }}
              </span>
            </div>
            <div class="platform-card__action">
              进入运营 <el-icon><Right /></el-icon>
            </div>
          </button>
        </div>
      </div>
    </PageSection>
  </PageScroll>
</template>

<style scoped>
.employee-kpi-section {
  margin-bottom: 12px;
}

.platform-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.platform-card {
  display: grid;
  gap: 10px;
  padding: 16px 16px 14px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.platform-card:hover {
  border-color: var(--ch-primary-muted);
  box-shadow: var(--ch-shadow-sm);
  transform: translateY(-1px);
}

.platform-card.is-highlighted {
  border-color: var(--ch-primary);
  box-shadow: 0 0 0 1px var(--ch-primary-muted), var(--ch-shadow-sm);
}

.platform-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.platform-card__top strong {
  font-size: 14px;
  font-weight: 650;
  color: var(--ch-text);
}

.platform-card__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding-top: 4px;
}

.platform-card__metric {
  display: grid;
  gap: 2px;
  min-width: 0;
  font-size: 13px;
  font-weight: 650;
  color: var(--ch-text);
  font-variant-numeric: tabular-nums;
}

.platform-card__metric em {
  font-style: normal;
  font-size: 11px;
  font-weight: 550;
  color: var(--ch-text-muted);
}

.platform-card__action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ch-primary);
}

@media (max-width: 640px) {
  .platform-card__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
