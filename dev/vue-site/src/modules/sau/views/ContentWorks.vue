<template>
  <div class="content-works">
    <PageHeader
      title="作品中心"
      eyebrow="自媒体"
      description="同步与检索已发布作品"
    />

    <PageSection title="筛选">
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="toolbar-label">平台</span>
          <el-select
            v-model="selectedPlatform"
            placeholder="全部平台"
            style="width: 140px"
            @change="handlePlatformChange"
          >
            <el-option label="全部" value="all" />
            <el-option
              v-for="p in platformOptions"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
          <span class="toolbar-label">账号</span>
          <el-select
            v-model="selectedAccountId"
            placeholder="选择账号"
            clearable
            style="width: 240px"
            @change="handleAccountChange"
          >
            <el-option label="全部" value="all" />
            <el-option
              v-for="acc in filteredAccounts"
              :key="acc.id"
              :label="`${platformLabel(acc.type)} · ${acc.name}`"
              :value="acc.id"
            />
          </el-select>
          <span class="toolbar-label">搜索</span>
          <el-input
            v-model="searchQ"
            clearable
            placeholder="搜索标题"
            style="width: 200px"
            @input="onSearchInput"
            @clear="refetchListFromFilters"
          />
          <span class="toolbar-label">排序</span>
          <el-select v-model="sortBy" style="width: 120px" @change="onSortChange">
            <el-option
              v-for="opt in SORT_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-select v-model="sortOrder" style="width: 100px" @change="onSortChange">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button
            type="primary"
            :loading="syncing"
            :disabled="!canSync"
            @click="handleSync"
          >
            同步作品
          </el-button>
          <el-button :loading="refreshing" @click="handleRefresh">刷新</el-button>
        </div>
      </div>
    </PageSection>

    <PageSection title="作品">
      <ContentDashboardSummary
        :loading="dashboardLoading"
        :dashboard="dashboard"
        :is-mock="contentMockEnabled"
      />

      <div v-if="syncMessage" class="sync-status">
        <el-alert
          :title="syncMessage"
          :type="syncAlertType"
          :closable="true"
          show-icon
          @close="syncMessage = ''"
        />
      </div>

      <div class="works-table">
        <el-table
          v-loading="loading"
          :data="works"
          style="width: 100%"
          @row-click="openDetail"
        >
          <el-table-column label="封面" width="90">
            <template #default="{ row }">
              <el-image
                v-if="row.cover_url"
                :src="coverSrc(row.cover_url)"
                fit="cover"
                class="cover-thumb"
                :preview-src-list="[coverSrc(row.cover_url)]"
                preview-teleported
                referrerpolicy="no-referrer"
                @click.stop
              />
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
          <el-table-column label="平台" width="90">
            <template #default="{ row }">
              {{ platformNameByKey(row.platform) }}
            </template>
          </el-table-column>
          <el-table-column label="账号" width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.account_name || accountNameMap[row.account_id] || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="发布时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.publish_time) }}
            </template>
          </el-table-column>
          <el-table-column label="播放" width="90">
            <template #default="{ row }">
              {{ formatMetric(row.play_count) }}
            </template>
          </el-table-column>
          <el-table-column label="点赞" width="90">
            <template #default="{ row }">
              {{ formatMetric(row.like_count) }}
            </template>
          </el-table-column>
          <el-table-column label="评论" width="90">
            <template #default="{ row }">
              {{ formatMetric(row.comment_count) }}
            </template>
          </el-table-column>
          <el-table-column label="转发" width="90">
            <template #default="{ row }">
              {{ formatMetric(row.share_count) }}
            </template>
          </el-table-column>
          <el-table-column label="收藏" width="90">
            <template #default="{ row }">
              {{ formatMetric(row.collect_count) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              {{ row.status_text || row.status_code || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="同步时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.last_synced_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click.stop="openDetail(row)">详情</el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="!row.share_url"
                @click.stop="openShareUrl(row)"
              >
                打开
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[20]"
            layout="total, prev, pager, next"
            @current-change="fetchWorks"
          />
        </div>
      </div>
    </PageSection>

    <el-drawer
      v-model="drawerVisible"
      title="作品详情"
      size="480px"
      destroy-on-close
    >
      <ContentWorkDetailPanel
        :loading="detailLoading"
        :work="detailWork"
        :baseline="detailBaseline"
        :vs-prev-snapshot="vsPrevSnapshot"
        :vs-week="vsWeek"
        :snapshots="snapshots"
        :platform-name="detailPlatformName"
        :account-name="detailAccountName"
        :extra-fields="detailExtraFields"
      />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import PageSection from '@/components/common/PageSection.vue'
import { accountApi } from '@sau/api/account'
import { contentApi, useContentMock } from '@sau/api/content'
import { buildApiUrl } from '@sau/utils/apiBase'
import { formatMetric } from '@sau/utils/contentMetrics'
import ContentDashboardSummary from '@sau/components/ContentDashboardSummary.vue'
import ContentWorkDetailPanel from '@sau/components/ContentWorkDetailPanel.vue'

const PLATFORM_OPTIONS = [
  { value: 'xiaohongshu', label: '小红书', type: 1 },
  { value: 'tencent', label: '视频号', type: 2 },
  { value: 'douyin', label: '抖音', type: 3 },
  { value: 'kuaishou', label: '快手', type: 4 }
]

const platformOptions = PLATFORM_OPTIONS
const contentMockEnabled = useContentMock()

const accounts = ref([])
const selectedPlatform = ref('all')
const selectedAccountId = ref('all')
const works = ref([])
const loading = ref(false)
const refreshing = ref(false)
const dashboardLoading = ref(false)
const dashboard = ref(null)
const syncing = ref(false)
const syncMessage = ref('')
const syncAlertType = ref('info')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchQ = ref('')
const sortBy = ref('publish_time')
const sortOrder = ref('desc')
let searchDebounce = null

const SORT_OPTIONS = [
  { value: 'publish_time', label: '发布时间' },
  { value: 'like_count', label: '点赞' },
  { value: 'comment_count', label: '评论' }
]

const drawerVisible = ref(false)
const detailLoading = ref(false)
const detailWork = ref(null)
const detailBaseline = ref(null)
const vsPrevSnapshot = ref(null)
const vsWeek = ref(null)
const snapshots = ref([])

let pollTimer = null

const filteredAccounts = computed(() => {
  if (selectedPlatform.value === 'all') return accounts.value
  const opt = PLATFORM_OPTIONS.find((p) => p.value === selectedPlatform.value)
  if (!opt) return accounts.value
  const filtered = accounts.value.filter((acc) => Number(acc.type) === opt.type)
  // 后端 type 码与前端枚举不一致时，过滤可能得到空列表；此时回退显示所有账号，避免下拉只剩“全部”
  return filtered.length ? filtered : accounts.value
})

const accountNameMap = computed(() => {
  const map = {}
  accounts.value.forEach((acc) => {
    map[acc.id] = acc.name
  })
  return map
})

const pickSingleFilteredAccount = () => {
  if (selectedAccountId.value !== 'all' && selectedAccountId.value != null) return
  if (filteredAccounts.value.length === 1) {
    selectedAccountId.value = filteredAccounts.value[0].id
  }
}

const canSync = computed(() => {
  return selectedAccountId.value !== 'all' && selectedAccountId.value != null && !syncing.value
})

const detailPlatformName = computed(() => platformNameByKey(detailWork.value?.platform))
const detailAccountName = computed(() => {
  const w = detailWork.value
  if (!w) return '-'
  return w.account_name || accountNameMap.value[w.account_id] || '-'
})

/** 原生指标字段 → 中文标签；未列出的扩展字段默认不展示，避免技术字段名外露 */
const METRIC_LABEL_MAP = {
  aweme_id: '作品 ID',
  item_id: '作品 ID',
  play_count: '播放量',
  view_count: '播放量',
  viewCount: '播放量',
  readCount: '播放量',
  digg_count: '点赞数',
  like_count: '点赞数',
  likeCount: '点赞数',
  likes: '点赞数',
  comment_count: '评论数',
  commentCount: '评论数',
  comments_count: '评论数',
  share_count: '分享数',
  shareCount: '分享数',
  shared_count: '分享数',
  forward_count: '转发数',
  forwardCount: '转发数',
  collect_count: '收藏数',
  collected_count: '收藏数',
  collectCount: '收藏数',
  favCount: '收藏数',
  favorite_count: '收藏数',
  realLikeCount: '真实点赞',
  download_count: '下载数',
  live_watch_count: '直播观看',
  lose_count: '点踩数',
  lose_comment_count: '差评数',
  admire_count: '赞赏数',
  exposure_count: '曝光量',
  recommend_count: '推荐数'
}

/** 与主列重复的原始 key，不再出现在「更多数据」 */
const EXTRA_METRIC_SKIP = new Set([
  'play_count',
  'view_count',
  'viewCount',
  'readCount',
  'digg_count',
  'like_count',
  'likeCount',
  'likes',
  'comment_count',
  'commentCount',
  'comments_count',
  'share_count',
  'shareCount',
  'shared_count',
  'collect_count',
  'collected_count',
  'collectCount',
  'favCount',
  'favorite_count'
])

const platformLabel = (type) => {
  const opt = PLATFORM_OPTIONS.find((p) => p.type === Number(type))
  return opt ? opt.label : '未知'
}

const platformNameByKey = (key) => {
  const opt = PLATFORM_OPTIONS.find((p) => p.value === key)
  return opt ? opt.label : (key || '-')
}

/**
 * 封面地址：
 * - 快手新 CDN（wsukwai.com）服务器代理会被 403，改为浏览器直连（已设 referrerpolicy=no-referrer）
 * - 其它平台仍走后端代理，规避本机失效系统代理 / 防盗链
 */
const coverSrc = (url) => {
  if (!url) return ''
  try {
    const host = new URL(url).hostname.toLowerCase()
    if (host === 'wsukwai.com' || host.endsWith('.wsukwai.com')) {
      return url
    }
  } catch (_) {
    /* ignore bad url */
  }
  return buildApiUrl(`/content/cover?url=${encodeURIComponent(url)}`)
}

const formatMetricValue = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return value
}

const formatTime = (value) => {
  if (!value) return '-'
  return value
}

const detailExtraFields = computed(() => {
  const metrics = detailWork.value?.raw_metrics
  if (!metrics || typeof metrics !== 'object') return []
  const rows = []
  const seenLabels = new Set()
  for (const [key, value] of Object.entries(metrics)) {
    if (EXTRA_METRIC_SKIP.has(key)) continue
    const label = METRIC_LABEL_MAP[key]
    if (!label) continue
    if (seenLabels.has(label)) continue
    seenLabels.add(label)
    rows.push({ label, value: formatMetricValue(value) })
  }
  return rows
})

const normalizeAccounts = (rawList) => {
  return (rawList || [])
    .map((item) => {
      if (Array.isArray(item)) {
        return {
          id: item[0],
          type: item[1],
          name: item[3]
        }
      }
      return {
        id: item.id,
        type: item.type,
        name: item.name || item.userName
      }
    })
    .filter((acc) => PLATFORM_OPTIONS.some((p) => p.type === Number(acc.type)))
}

const fetchAccounts = async () => {
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      accounts.value = normalizeAccounts(res.data)
      pickSingleFilteredAccount()
    }
  } catch (error) {
    console.error('获取账号失败:', error)
  }
}

const buildFilterParams = () => {
  const params = {}
  if (selectedAccountId.value !== 'all' && selectedAccountId.value != null) {
    params.account_id = selectedAccountId.value
  }
  if (selectedPlatform.value !== 'all') {
    params.platform = selectedPlatform.value
  }
  return params
}

const buildListParams = () => {
  const params = {
    page: page.value,
    page_size: pageSize.value,
    ...buildFilterParams(),
    sort_by: sortBy.value,
    sort_order: sortOrder.value
  }
  const q = searchQ.value.trim()
  if (q) params.q = q
  return params
}

const clearSearchDebounce = () => {
  if (searchDebounce) {
    clearTimeout(searchDebounce)
    searchDebounce = null
  }
}

const refetchListFromFilters = () => {
  clearSearchDebounce()
  page.value = 1
  fetchWorks()
}

const onSearchInput = () => {
  clearSearchDebounce()
  searchDebounce = setTimeout(() => {
    page.value = 1
    fetchWorks()
  }, 300)
}

const onSortChange = () => {
  refetchListFromFilters()
}

const fetchDashboard = async () => {
  dashboardLoading.value = true
  try {
    const res = await contentApi.getDashboard(buildFilterParams())
    if (res.code === 200 && res.data) {
      dashboard.value = res.data
    }
  } catch (error) {
    console.error('获取看板失败:', error)
  } finally {
    dashboardLoading.value = false
  }
}

const fetchWorks = async () => {
  loading.value = true
  try {
    const res = await contentApi.listWorks(buildListParams())
    if (res.code === 200 && res.data) {
      works.value = res.data.list || []
      total.value = res.data.total || 0
      page.value = res.data.page || page.value
      pageSize.value = res.data.page_size || pageSize.value
    }
  } catch (error) {
    console.error('获取作品列表失败:', error)
  } finally {
    loading.value = false
  }
}

/** 刷新：只拉本地只读接口（dashboard + list），不触发同步 */
const handleRefresh = async () => {
  refreshing.value = true
  try {
    await Promise.all([fetchDashboard(), fetchWorks()])
  } finally {
    refreshing.value = false
  }
}

const handlePlatformChange = () => {
  selectedAccountId.value = 'all'
  pickSingleFilteredAccount()
  page.value = 1
  handleRefresh()
}

const handleAccountChange = () => {
  page.value = 1
  if (selectedAccountId.value !== 'all' && selectedAccountId.value != null) {
    const acc = accounts.value.find((a) => a.id === selectedAccountId.value)
    if (acc) {
      const opt = PLATFORM_OPTIONS.find((p) => p.type === Number(acc.type))
      if (opt) selectedPlatform.value = opt.value
    }
  }
  handleRefresh()
}

const clearPollTimer = () => {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

const sleep = (ms) => new Promise((resolve) => {
  pollTimer = setTimeout(resolve, ms)
})

const runtimeLabel = (runtime) => {
  const map = {
    local_agent: '助手本机',
    agent: '助手本机',
    server: '服务器',
    server_fallback: '服务器回退',
    server_cron: '定时服务器'
  }
  return map[runtime] || runtime || ''
}

const pollJobUntilDone = async (jobId) => {
  // 助手空结果后会服务器回退，Playwright 同步可能较久
  const deadline = Date.now() + 600000
  while (Date.now() < deadline) {
    await sleep(2000)
    const res = await contentApi.getJob(jobId)
    const job = res.data || {}
    const status = job.status
    const runtimeText = runtimeLabel(job.runtime)
    const trigger = job.trigger_source ? ` · ${job.trigger_source}` : ''
    if (status === 'success' || status === 'failed') {
      return job
    }
    const hint = job.message ? ` · ${job.message}` : ''
    syncMessage.value = runtimeText
      ? `同步中…（${status || 'pending'} · ${runtimeText}${trigger}${hint}）`
      : `同步中…（${status || 'pending'}${hint}）`
    syncAlertType.value = 'info'
  }
  throw new Error('同步超时，请稍后刷新列表查看结果')
}

const handleSync = async () => {
  if (selectedAccountId.value === 'all' || selectedAccountId.value == null) {
    ElMessage.warning('请先选择具体账号再同步')
    return
  }

  syncing.value = true
  syncMessage.value = '正在创建同步任务…'
  syncAlertType.value = 'info'

  try {
    const res = await contentApi.sync(selectedAccountId.value, 20)
    const jobId = res.data?.job_id
    if (!jobId) {
      throw new Error('未返回同步任务 ID')
    }

    syncMessage.value = '同步任务已创建，正在拉取作品…'
    const job = await pollJobUntilDone(jobId)
    const runtimeText = runtimeLabel(job.runtime)
    const runtimeSuffix = runtimeText ? `（${runtimeText}）` : ''

    if (job.status === 'success') {
      const count = job.fetched_count != null ? job.fetched_count : ''
      syncMessage.value = count !== ''
        ? `同步成功${runtimeSuffix}，共拉取 ${count} 条`
        : (job.message || `同步成功${runtimeSuffix}`)
      syncAlertType.value = 'success'
      ElMessage.success('同步成功')
      await handleRefresh()
    } else {
      syncMessage.value = `${job.message || '同步失败'}${runtimeSuffix}`
      syncAlertType.value = 'error'
      ElMessage.error(job.message || '同步失败')
    }
  } catch (error) {
    syncMessage.value = error.message || '同步失败'
    syncAlertType.value = 'error'
  } finally {
    clearPollTimer()
    syncing.value = false
  }
}

const openDetail = async (row) => {
  drawerVisible.value = true
  detailLoading.value = true
  detailWork.value = row
  detailBaseline.value = null
  vsPrevSnapshot.value = null
  vsWeek.value = null
  snapshots.value = []

  try {
    const [detailRes, snapRes] = await Promise.all([
      contentApi.getWork(row.id),
      contentApi.getWorkSnapshots(row.id, { limit: 60 })
    ])
    if (detailRes.code === 200 && detailRes.data) {
      detailWork.value = detailRes.data.work || row
      detailBaseline.value = detailRes.data.baseline || null
      vsPrevSnapshot.value = detailRes.data.vs_prev_snapshot || null
      vsWeek.value = detailRes.data.vs_week || null
    }
    if (snapRes.code === 200 && snapRes.data) {
      snapshots.value = snapRes.data.list || []
    }
  } catch (error) {
    console.error('获取作品详情失败:', error)
  } finally {
    detailLoading.value = false
  }
}

const openShareUrl = (row) => {
  if (!row.share_url) return
  window.open(row.share_url, '_blank')
}

onMounted(async () => {
  await fetchAccounts()
  await handleRefresh()
})

onUnmounted(() => {
  clearPollTimer()
  clearSearchDebounce()
})
</script>

<style lang="scss" scoped>
@use '@sau/styles/variables.scss' as *;

.content-works {
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;

    .toolbar-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .toolbar-label {
      color: $text-regular;
      white-space: nowrap;
    }

    .toolbar-right {
      display: flex;
      gap: 8px;
    }
  }

  .sync-status {
    margin-bottom: 16px;
  }

  .works-table {
    padding: 0;
  }

  .cover-thumb {
    width: 56px;
    height: 74px;
    border-radius: 4px;
  }

  .pagination-wrap {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
