<template>
  <div class="dashboard">
    <PageHeader
      title="自媒体首页"
      eyebrow="自媒体"
      description="账号、平台与素材概览"
    />

    <PageSection flush class="dashboard-kpis">
      <div class="kpi-grid">
        <article class="kpi-card kpi-card--primary">
          <div class="kpi-card__icon"><el-icon :size="18"><User /></el-icon></div>
          <div>
            <div class="kpi-card__label">账号总数</div>
            <div class="kpi-card__value">{{ accountStats.total }}</div>
            <div class="kpi-card__hint">正常 {{ accountStats.normal }} · 异常 {{ accountStats.abnormal }}</div>
          </div>
        </article>
        <article class="kpi-card kpi-card--success">
          <div class="kpi-card__icon"><el-icon :size="18"><Platform /></el-icon></div>
          <div>
            <div class="kpi-card__label">已接入平台</div>
            <div class="kpi-card__value">{{ platformStats.total }}</div>
            <div class="kpi-card__tags">
              <el-tag size="small" type="success" effect="plain">快手 {{ platformStats.kuaishou }}</el-tag>
              <el-tag size="small" type="danger" effect="plain">抖音 {{ platformStats.douyin }}</el-tag>
              <el-tag size="small" type="warning" effect="plain">视频号 {{ platformStats.channels }}</el-tag>
              <el-tag size="small" type="info" effect="plain">小红书 {{ platformStats.xiaohongshu }}</el-tag>
              <el-tag size="small" effect="plain">TikTok {{ platformStats.tiktok }}</el-tag>
            </div>
          </div>
        </article>
        <article class="kpi-card kpi-card--info">
          <div class="kpi-card__icon"><el-icon :size="18"><Document /></el-icon></div>
          <div>
            <div class="kpi-card__label">素材总数</div>
            <div class="kpi-card__value">{{ contentStats.total }}</div>
            <div class="kpi-card__hint">
              视频 {{ contentStats.videos }} · 图片 {{ contentStats.images }} · 其他 {{ contentStats.others }}
            </div>
          </div>
        </article>
      </div>
    </PageSection>

    <PageSection title="快捷操作" description="常用入口">
      <div class="action-grid">
        <button type="button" class="action-card" @click="navigateTo(`${sauBasePath}/accounts`)">
          <span class="action-card__icon"><el-icon :size="18"><UserFilled /></el-icon></span>
          <strong>账号管理</strong>
          <span>管理各平台账号</span>
        </button>
        <button type="button" class="action-card" @click="navigateTo(`${sauBasePath}/materials`)">
          <span class="action-card__icon"><el-icon :size="18"><Upload /></el-icon></span>
          <strong>素材管理</strong>
          <span>上传视频 / 图片</span>
        </button>
        <button type="button" class="action-card" @click="navigateTo(`${sauBasePath}/publish`)">
          <span class="action-card__icon"><el-icon :size="18"><Timer /></el-icon></span>
          <strong>发布中心</strong>
          <span>多平台发布</span>
        </button>
        <button type="button" class="action-card" @click="navigateTo(`${sauBasePath}/about`)">
          <span class="action-card__icon"><el-icon :size="18"><DataAnalysis /></el-icon></span>
          <strong>关于系统</strong>
          <span>查看系统信息</span>
        </button>
      </div>
    </PageSection>

    <PageSection title="最近上传素材">
      <template #actions>
        <el-button text type="primary" @click="navigateTo(`${sauBasePath}/materials`)">查看全部</el-button>
      </template>
      <el-table :data="recentMaterials" v-loading="loading" size="small" empty-text="暂无素材数据">
        <el-table-column prop="filename" label="文件名" min-width="220" />
        <el-table-column prop="filesize" label="大小" width="110">
          <template #default="{ row }">{{ row.filesize }} MB</template>
        </el-table-column>
        <el-table-column prop="upload_time" label="上传时间" min-width="160" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getFileTypeTag(row.filename)" effect="plain" size="small">
              {{ getFileType(row.filename) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </PageSection>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  User, UserFilled, Platform, Document,
  Upload, Timer, DataAnalysis,
} from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import PageSection from '@/components/common/PageSection.vue'
import { accountApi } from '@sau/api/account'
import { materialApi } from '@sau/api/material'
import { useAccountStore } from '@sau/stores/account'
import { useAppStore } from '@sau/stores/app'

const route = useRoute()
const router = useRouter()
const accountStore = useAccountStore()
const appStore = useAppStore()
const loading = ref(false)

const sauBasePath = computed(() => {
  const path = route.path || ''
  if (path.startsWith('/boss/sau')) return '/boss/sau'
  return '/employee/sau'
})

const accountStats = computed(() => {
  const accounts = accountStore.accounts
  const normal = accounts.filter((a) => a.status === '正常').length
  const abnormal = accounts.filter((a) => a.status !== '正常' && a.status !== '验证中').length
  return { total: accounts.length, normal, abnormal }
})

const platformStats = computed(() => {
  const accounts = accountStore.accounts
  const kuaishou = accounts.filter((a) => a.platform === '快手').length
  const douyin = accounts.filter((a) => a.platform === '抖音').length
  const channels = accounts.filter((a) => a.platform === '视频号').length
  const xiaohongshu = accounts.filter((a) => a.platform === '小红书').length
  const tiktok = accounts.filter((a) => a.platform === 'TikTok').length
  const total = [kuaishou, douyin, channels, xiaohongshu, tiktok].filter((n) => n > 0).length
  return { total, kuaishou, douyin, channels, xiaohongshu, tiktok }
})

const videoExtensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']

const contentStats = computed(() => {
  const materials = appStore.materials
  const videos = materials.filter((m) => videoExtensions.some((ext) => m.filename.toLowerCase().endsWith(ext))).length
  const images = materials.filter((m) => imageExtensions.some((ext) => m.filename.toLowerCase().endsWith(ext))).length
  return {
    total: materials.length,
    videos,
    images,
    others: materials.length - videos - images,
  }
})

const recentMaterials = computed(() =>
  [...appStore.materials]
    .sort((a, b) => new Date(b.upload_time) - new Date(a.upload_time))
    .slice(0, 5),
)

const getFileType = (filename) => {
  if (videoExtensions.some((ext) => filename.toLowerCase().endsWith(ext))) return '视频'
  if (imageExtensions.some((ext) => filename.toLowerCase().endsWith(ext))) return '图片'
  return '其他'
}

const getFileTypeTag = (filename) => {
  const type = getFileType(filename)
  return { 视频: 'success', 图片: 'warning', 其他: 'info' }[type] || 'info'
}

const navigateTo = (path) => router.push(path)

const fetchDashboardData = async () => {
  loading.value = true
  try {
    const [accountRes, materialRes] = await Promise.allSettled([
      accountApi.getAccounts(),
      materialApi.getAllMaterials(),
    ])
    if (accountRes.status === 'fulfilled' && accountRes.value.code === 200) {
      accountStore.setAccounts(accountRes.value.data)
    }
    if (materialRes.status === 'fulfilled' && materialRes.value.code === 200) {
      appStore.setMaterials(materialRes.value.data)
    }
  } catch (error) {
    console.error('获取仪表盘数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboardData()
})
</script>

<style scoped>
.dashboard {
  display: grid;
  gap: 4px;
}

.dashboard-kpis {
  margin-bottom: 12px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  position: relative;
  display: grid;
  grid-template-columns: 42px 1fr;
  gap: 12px;
  align-items: start;
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
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
.kpi-card--info { --kpi-accent: var(--ch-info); --kpi-soft: var(--ch-primary-soft); }

.kpi-card__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: var(--kpi-soft);
  color: var(--kpi-accent);
}

.kpi-card__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ch-text-muted);
}

.kpi-card__value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--ch-text);
  font-variant-numeric: tabular-nums;
}

.kpi-card__hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ch-text-muted);
}

.kpi-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.action-card {
  display: grid;
  gap: 8px;
  justify-items: start;
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.action-card:hover {
  border-color: var(--ch-primary-muted);
  box-shadow: var(--ch-shadow-sm);
  transform: translateY(-1px);
}

.action-card__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--ch-primary-soft);
  color: var(--ch-primary);
}

.action-card strong {
  font-size: 14px;
  font-weight: 650;
  color: var(--ch-text);
}

.action-card span {
  font-size: 12px;
  color: var(--ch-text-muted);
}

@media (max-width: 1100px) {
  .kpi-grid,
  .action-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .kpi-grid,
  .action-grid {
    grid-template-columns: 1fr;
  }
}
</style>
