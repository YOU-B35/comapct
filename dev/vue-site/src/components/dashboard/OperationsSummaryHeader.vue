<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  CircleCheckFilled,
  Right,
  Shop,
  WarningFilled,
  List,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { calcTaskStats } from '@/utils/operations'

const props = defineProps({
  overview: { type: Object, default: null },
  platformSales: { type: Array, default: () => [] },
  tasks: { type: Array, default: () => [] },
  highlightPlatformId: { type: String, default: '' },
})

const router = useRouter()
const auth = useAuthStore()

const taskStats = computed(() => calcTaskStats(props.tasks))

const totalStores = computed(() => {
  const fromSales = props.platformSales.reduce((sum, row) => sum + (row.storeCount || 0), 0)
  if (fromSales > 0) return fromSales
  return (props.overview?.platforms || []).reduce(
    (sum, platform) => sum + (platform.storeSummaries?.length || 0),
    0,
  )
})

const summaryItems = computed(() => [
  {
    key: 'issues',
    label: '待跟进问题',
    value: props.overview?.totalIssues ?? 0,
    tone: props.overview?.totalIssues ? 'danger' : 'success',
    hint: '各平台需今日处理',
    icon: WarningFilled,
  },
  {
    key: 'stores',
    label: '绑定店铺',
    value: totalStores.value,
    tone: 'primary',
    hint: `${props.platformSales.length} 个平台已接入`,
    icon: Shop,
  },
  {
    key: 'tasks',
    label: '待完成任务',
    value: Math.max(0, taskStats.value.total - taskStats.value.completed),
    tone: taskStats.value.overdue ? 'danger' : 'warning',
    hint: taskStats.value.overdue ? `${taskStats.value.overdue} 项已逾期` : '运营任务待跟进',
    icon: List,
  },
  {
    key: 'rate',
    label: '任务完成率',
    value: `${taskStats.value.completionRate}%`,
    tone: 'success',
    hint: `${taskStats.value.completed}/${taskStats.value.total} 已完成`,
    icon: CircleCheckFilled,
  },
])

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
  const prefix = auth.isBoss ? '/boss' : '/employee'
  router.push(`${prefix}/${segment}`)
}

function mergePlatformCard(row) {
  const platform = props.overview?.platforms?.find((p) => p.id === row.id)
  return {
    ...row,
    bound: platform?.bound ?? row.storeCount > 0,
    issueCount: platform?.issueCount ?? row.alerts ?? 0,
  }
}

const platformCards = computed(() => props.platformSales.map(mergePlatformCard))
</script>

<template>
  <div class="ops-summary">
    <div class="kpi-grid">
      <article
        v-for="item in summaryItems"
        :key="item.key"
        class="kpi-card"
        :class="`kpi-card--${item.tone}`"
      >
        <div class="kpi-card__icon" aria-hidden="true">
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
        </div>
        <div class="kpi-card__body">
          <div class="kpi-card__label">{{ item.label }}</div>
          <div class="kpi-card__value">{{ item.value }}</div>
          <div class="kpi-card__hint">{{ item.hint }}</div>
        </div>
      </article>
    </div>

    <div v-if="platformCards.length" class="platform-cards">
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
        <div class="platform-card__owner">负责人 · {{ card.owner }}</div>
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

    <el-empty
      v-else
      description="暂无绑定店铺，请先在账户绑定中配置"
      :image-size="72"
    />
  </div>
</template>

<style scoped>
.ops-summary {
  display: grid;
  gap: 16px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  position: relative;
  display: grid;
  grid-template-columns: 42px 1fr;
  gap: 12px;
  align-items: start;
  padding: 16px 16px 15px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background:
    linear-gradient(165deg, rgba(255, 255, 255, 0.92) 0%, var(--ch-surface) 55%),
    var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
  overflow: hidden;
}

.kpi-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--kpi-accent, var(--ch-primary));
}

.kpi-card--primary { --kpi-accent: var(--ch-primary); --kpi-soft: var(--ch-primary-soft); }
.kpi-card--success { --kpi-accent: var(--ch-success); --kpi-soft: #e8f7f1; }
.kpi-card--warning { --kpi-accent: var(--ch-warning); --kpi-soft: #fff8eb; }
.kpi-card--danger { --kpi-accent: var(--ch-error); --kpi-soft: #fff1f3; }

.kpi-card__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: var(--kpi-soft, var(--ch-primary-soft));
  color: var(--kpi-accent, var(--ch-primary));
}

.kpi-card__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ch-text-muted);
  letter-spacing: 0.01em;
}

.kpi-card__value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: var(--ch-text);
}

.kpi-card--danger .kpi-card__value { color: var(--ch-error); }
.kpi-card--warning .kpi-card__value { color: var(--ch-warning); }
.kpi-card--success .kpi-card__value { color: var(--ch-success); }
.kpi-card--primary .kpi-card__value { color: var(--ch-primary); }

.kpi-card__hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--ch-text-muted);
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

.platform-card__owner {
  font-size: 12px;
  color: var(--ch-text-muted);
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

@media (max-width: 1100px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .platform-card__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
