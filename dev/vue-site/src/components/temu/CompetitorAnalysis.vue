<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Link, Refresh, Search, Setting } from '@element-plus/icons-vue'
import SearchableTable from '@/components/common/SearchableTable.vue'
import { resolveAppError } from '@/utils/appErrorCode'
import {
  isTemuMallUrl,
  temuMallUrlErrorMessage,
  temuMallUrlExample,
  temuMallUrlGuideLines,
} from '@/utils/temuMonitorUrl'
import { openTemuFrontendLogin } from '@/api/temuApi'
import {
  analyzeCompetitors,
  deleteCompetitor,
  discoverCompetitors,
  exportCompetitorReport,
  fetchCompetitorReports,
  fetchCompetitors,
  saveCompetitor,
} from '@/api/temuCompetitors'

defineProps({
  useBackendData: { type: Boolean, default: false },
})

const loading = ref(false)
const analyzing = ref(false)
const discovering = ref(false)
const openingFrontendLogin = ref(false)
const competitors = ref([])
const reports = ref([])
const settingsOpen = ref(true)
const analysisError = ref(null)
const discoveryCandidates = ref([])
const selectingCandidateUrl = ref('')
const exportingReportId = ref('')
const reportPollingGeneration = ref(0)
const reportPollingTimer = ref(0)

const form = reactive({
  id: '',
  label: '',
  url: '',
})

function resetForm() {
  form.id = ''
  form.label = ''
  form.url = ''
}

function hasActiveReport(report) {
  return ['pending', 'running'].includes(report?.latestJobStatus)
}

function clearReportPollingTimer() {
  if (reportPollingTimer.value) {
    window.clearTimeout(reportPollingTimer.value)
    reportPollingTimer.value = 0
  }
}

function stopReportPolling() {
  reportPollingGeneration.value += 1
  clearReportPollingTimer()
}

function summarizeReports(reportList = []) {
  return reportList.reduce(
    (summary, report) => {
      if (report.latestJobStatus === 'failed') summary.failed += 1
      summary.newToday += Number(report.summary?.newToday || 0)
      summary.salesSpikes += Number(report.summary?.salesSpikes || 0)
      return summary
    },
    { failed: 0, newToday: 0, salesSpikes: 0 },
  )
}

function notifyAnalysisOutcome(reportList = reports.value) {
  const summary = summarizeReports(reportList)
  if (summary.failed > 0) {
    ElMessage.warning(`状态已同步，其中 ${summary.failed} 个竞店抓取失败，请查看卡片失败原因`)
    return
  }
  ElMessage.success(`爬取完成：发现 ${summary.newToday} 个今日上新，${summary.salesSpikes} 个销量异常`)
}

async function loadCompetitors() {
  loading.value = true
  try {
    const res = await fetchCompetitors()
    competitors.value = res.data || []
  } catch {
    competitors.value = []
  } finally {
    loading.value = false
  }
}

async function loadReports() {
  try {
    const res = await fetchCompetitorReports(competitors.value)
    if (res.competitors?.length) {
      competitors.value = res.competitors
    }
    reports.value = res.data || []
  } catch {
    reports.value = []
  }
}

async function pollReportsUntilSettled({ maxAttempts = 20, delayMs = 3000, notifyOnSettle = false } = {}) {
  const generation = reportPollingGeneration.value + 1
  reportPollingGeneration.value = generation
  clearReportPollingTimer()

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (attempt > 0) {
      await new Promise((resolve) => {
        reportPollingTimer.value = window.setTimeout(resolve, delayMs)
      })
      if (reportPollingGeneration.value !== generation) return
    }

    await loadReports()
    if (reportPollingGeneration.value !== generation) return

    if (!reports.value.some(hasActiveReport)) {
      clearReportPollingTimer()
      if (notifyOnSettle) notifyAnalysisOutcome(reports.value)
      return
    }
  }

  clearReportPollingTimer()
  if (notifyOnSettle) {
    ElMessage.warning('任务仍在执行中，可稍后刷新页面查看最终结果')
  }
}

function editCompetitor(row) {
  form.id = row.id
  form.label = row.label
  form.url = row.url
  settingsOpen.value = true
}

async function submitCompetitor() {
  if (!form.label.trim()) {
    ElMessage.warning('请填写店铺备注')
    return
  }
  if (!form.url.trim()) {
    ElMessage.warning('请填写竞店链接')
    return
  }
  if (!isTemuMallUrl(form.url.trim())) {
    ElMessage.warning(temuMallUrlErrorMessage)
    return
  }

  loading.value = true
  try {
    await saveCompetitor({
      id: form.id || undefined,
      label: form.label.trim(),
      url: form.url.trim(),
    })
    ElMessage.success(form.id ? '竞店已更新' : '竞店已添加')
    resetForm()
    await loadCompetitors()
    await loadReports()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    loading.value = false
  }
}

async function removeCompetitor(row) {
  try {
    await ElMessageBox.confirm(`确定移除竞店「${row.label}」吗？相关抓取记录也会删除。`, '确认移除', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
    await deleteCompetitor(row.id)
    reports.value = reports.value.filter((item) => item.id !== row.id)
    ElMessage.success('竞店已移除')
    await loadCompetitors()
    await loadReports()
  } catch {
    // ignore
  }
}

async function discoverFishingCompetitors() {
  discovering.value = true
  analysisError.value = null
  try {
    const res = await discoverCompetitors({
      keyword: 'fishing tackle',
      region: 'za',
      limit: 10,
    })
    discoveryCandidates.value = res.data?.candidates || []
    if (!discoveryCandidates.value.length) {
      ElMessage.warning('当前没有发现可抓取的渔具候选竞店')
      return
    }
    ElMessage.success(`已发现 ${discoveryCandidates.value.length} 个候选竞店`)
  } catch (err) {
    analysisError.value = resolveAppError(
      { errorCode: err.errorCode, message: err.message },
      null,
    )
    ElMessage.error(analysisError.value.title || err.message || '候选竞店发现失败')
  } finally {
    discovering.value = false
  }
}

async function openBuyerFrontendLogin() {
  openingFrontendLogin.value = true
  try {
    await openTemuFrontendLogin({
      url: 'https://www.temu.com/za/search_result.html?search_key=fishing%20tackle',
    })
    ElMessage.success('已打开普通 Chrome 买家前台登录窗口，完成后请关闭该窗口再点「发现渔具 Top10」')
  } catch (err) {
    analysisError.value = resolveAppError(
      { errorCode: err.errorCode, message: err.message },
      null,
    )
    ElMessage.error(analysisError.value.title || err.message || '打开前台登录失败')
  } finally {
    openingFrontendLogin.value = false
  }
}

async function selectCandidateAndAnalyze(candidate) {
  if (!candidate?.crawlable) {
    ElMessage.warning('该候选当前不可抓取，请选择其他候选')
    return
  }
  selectingCandidateUrl.value = candidate.url
  analysisError.value = null
  try {
    let target = competitors.value.find((item) => item.url === candidate.url)
    if (!target) {
      const saved = await saveCompetitor({
        label: candidate.label,
        url: candidate.url,
      })
      target = saved.data
      await loadCompetitors()
    }
    const res = await analyzeCompetitors([target])
    competitors.value = res.competitors || []
    reports.value = res.data || []
    if (!reports.value.length) {
      ElMessage.warning('竞店已保存，但暂未生成分析结果')
      return
    }
    if (reports.value.some(hasActiveReport)) {
      ElMessage.info(`已入队抓取「${candidate.label}」，正在同步结果`)
      void pollReportsUntilSettled({ notifyOnSettle: true })
      return
    }
    notifyAnalysisOutcome(reports.value)
  } catch (err) {
    analysisError.value = resolveAppError(
      { errorCode: err.errorCode, message: err.message },
      null,
    )
    ElMessage.error(analysisError.value.title || err.message || '候选竞店分析失败')
  } finally {
    selectingCandidateUrl.value = ''
  }
}

async function applyAnalysisResult(res) {
  competitors.value = res.competitors || []
  reports.value = res.data || []
  if (!reports.value.length) {
    ElMessage.warning('未生成分析结果，请稍后重试')
    return
  }
  if (reports.value.some(hasActiveReport)) {
    ElMessage.info('任务已入队，正在同步竞店抓取结果')
    void pollReportsUntilSettled({ notifyOnSettle: true })
    return
  }
  notifyAnalysisOutcome(reports.value)
}

async function runAnalysis({ force = false } = {}) {
  analyzing.value = true
  analysisError.value = null
  const list = competitors.value
  const invalidUrlCount = list.filter((item) => !isTemuMallUrl(item.url)).length
  if (invalidUrlCount > 0) {
    if (invalidUrlCount === list.length) {
      ElMessage.warning('所选竞店链接均非 Temu 店铺（需含 mall_id），无法执行爬取分析')
    } else {
      ElMessage.warning(`已跳过 ${invalidUrlCount} 个非店铺链接，仅对有效竞店执行爬取分析`)
    }
  }
  try {
    stopReportPolling()
    const res = await analyzeCompetitors(
      list,
      force ? { force: true, bypassCooldown: true } : undefined,
    )
    await applyAnalysisResult(res)
  } catch (err) {
    if (!force && err?.errorCode === 'CRAWL_COOLDOWN') {
      try {
        await ElMessageBox.confirm('该竞店冷却中，是否强制刷新？', '确认强制刷新', {
          type: 'warning',
          confirmButtonText: '强制刷新',
          cancelButtonText: '取消',
        })
        analyzing.value = false
        await runAnalysis({ force: true })
        return
      } catch {
        ElMessage.info('已取消强制刷新')
        return
      }
    }
    analysisError.value = resolveAppError(
      { errorCode: err.errorCode, message: err.message },
      null,
    )
    ElMessage.error(analysisError.value.title || err.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

async function handleExport(report) {
  exportingReportId.value = report.id
  try {
    await exportCompetitorReport(report)
    ElMessage.success('Excel 报表开始下载')
  } catch (err) {
    ElMessage.error(err.message || 'Excel 导出失败')
  } finally {
    exportingReportId.value = ''
  }
}

function sourceTypeText(type) {
  return type === 'shop' ? '店铺' : '候选源'
}

function sampleProductText(product) {
  const price = Number(product.price || 0)
  const priceText = price > 0 ? `¥${price.toFixed(2)}` : ''
  const sales = Number(product.salesSignal || 0)
  const salesText = sales > 0 ? `${sales} sold` : ''
  return [product.name, priceText, salesText].filter(Boolean).join(' | ')
}

function jobStatusType(status) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}

function jobStatusText(status) {
  if (status === 'success') return '已生成'
  if (status === 'failed') return '抓取失败'
  if (status === 'running') return '执行中'
  if (status === 'pending') return '已入队'
  return '待执行'
}

function jobErrorDisplay(row = {}) {
  return resolveAppError(
    { errorCode: row.error_code || row.errorCode, message: row.error_message || row.errorMessage },
    null,
  )
}

function reportCrawlDateText(report) {
  return report.crawlDate || 'No snapshot'
}

function recentListingsEmptyText(report, backendMode) {
  if (!backendMode) return '最近 7 天暂无新上架商品'
  if (!report.snapshotCount) return 'No monitor snapshot yet'
  return 'No recent-launch rows in current snapshot'
}

function salesSpikesEmptyText(report, backendMode) {
  if (!backendMode) return '暂无销量异常商品'
  if (!report.snapshotCount) return 'No monitor snapshot yet'
  return 'No sales-outlier rows in current snapshot'
}

function canExportReport(report) {
  return Boolean(report?.artifacts?.report_xlsx_path)
}

onMounted(async () => {
  await loadCompetitors()
  await loadReports()
  if (reports.value.some(hasActiveReport)) {
    void pollReportsUntilSettled()
  }
})

onBeforeUnmount(() => {
  stopReportPolling()
})
</script>

<template>
  <div class="competitor-analysis">
    <el-alert
      v-if="useBackendData"
      type="info"
      :closable="false"
      show-icon
      title="竞店分析已接入后端保存"
      description="支持页面直接查看竞店结果，也支持导出后端生成的 Excel 报表。"
    />

    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="settings-head">
          <el-space>
            <el-icon><Setting /></el-icon>
            <span>竞店设置</span>
            <el-text size="small" type="info">
              系统每日自动爬取竞店商品，对比历史数据识别上新与销量异常
            </el-text>
          </el-space>
          <el-button text @click="settingsOpen = !settingsOpen">
            {{ settingsOpen ? '收起' : '展开' }}
          </el-button>
        </div>
      </template>

      <div v-show="settingsOpen">
        <div class="discovery-panel">
          <div class="discovery-head">
            <div>
              <strong>渔具 Top10 候选</strong>
              <el-text size="small" type="info">
                固定 Temu ZA，按前台搜索实时顺序发现可抓取候选
              </el-text>
            </div>
            <el-button
              type="primary"
              plain
              :icon="Search"
              :loading="discovering"
              @click="discoverFishingCompetitors"
            >
              发现渔具 Top10
            </el-button>
            <el-button
              plain
              :loading="openingFrontendLogin"
              @click="openBuyerFrontendLogin"
            >
              打开买家前台登录
            </el-button>
          </div>

          <el-alert
            v-if="analysisError && ['COMPETITOR_LOGIN_REQUIRED', 'COMPETITOR_FRONTEND_LOGIN_REQUIRED'].includes(analysisError.errorCode)"
            class="discovery-login-alert"
            type="warning"
            :closable="false"
            show-icon
            :title="analysisError.title"
            :description="analysisError.summary"
          />

          <SearchableTable
            v-if="discoveryCandidates.length"
            :data="discoveryCandidates"
            :fields="['label', 'url', 'host']"
            placeholder="搜索候选名称 / 链接"
            empty-text="暂无候选"
            :page-size="10"
            :page-sizes="[10, 20]"
            size="small"
            class="discovery-table"
          >
            <el-table-column label="排名" width="72" align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">#{{ row.rank }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="候选名称" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="candidate-name">
                  <strong>{{ row.label }}</strong>
                  <el-tag size="small" :type="row.sourceType === 'shop' ? 'success' : 'info'" effect="plain">
                    {{ sourceTypeText(row.sourceType) }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="样例商品" min-width="260">
              <template #default="{ row }">
                <div class="sample-products">
                  <el-text size="small" type="info">
                    {{ row.sampleProductCount }} 个样例
                  </el-text>
                  <div
                    v-for="product in row.sampleProducts?.slice(0, 2)"
                    :key="product.url || product.name"
                    class="sample-product"
                  >
                    {{ sampleProductText(product) }}
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="链接" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <el-link :href="row.url" target="_blank" type="primary" :underline="false">
                  {{ row.host || row.url }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.crawlable ? 'success' : 'danger'" size="small">
                  {{ row.crawlable ? '可抓取' : '不可抓取' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  :disabled="!row.crawlable"
                  :loading="selectingCandidateUrl === row.url"
                  @click="selectCandidateAndAnalyze(row)"
                >
                  选择并分析
                </el-button>
              </template>
            </el-table-column>
          </SearchableTable>
        </div>

        <el-divider content-position="left">手动添加竞店</el-divider>

        <el-alert
          type="warning"
          :closable="false"
          show-icon
          class="mall-url-guide"
          title="店铺链接格式（必填 mall_id）"
        >
          <ul class="mall-url-guide-list">
            <li v-for="(line, idx) in temuMallUrlGuideLines" :key="idx">
              <template v-if="idx === 1">
                正确示例：
                <el-link :href="temuMallUrlExample" target="_blank" type="primary" :underline="false">
                  {{ temuMallUrlExample }}
                </el-link>
              </template>
              <template v-else>{{ line }}</template>
            </li>
          </ul>
        </el-alert>

        <el-form label-width="100px" class="settings-form" @submit.prevent="submitCompetitor">
          <el-form-item label="店铺备注">
            <el-input
              v-model="form.label"
              placeholder="如：美国站头部竞店 A"
              maxlength="40"
              show-word-limit
              clearable
            />
          </el-form-item>
          <el-form-item label="店铺网址">
            <el-input
              v-model="form.url"
              :placeholder="temuMallUrlExample"
              clearable
            >
              <template #prefix>
                <el-icon><Link /></el-icon>
              </template>
            </el-input>
            <el-text
              v-if="form.url.trim() && !isTemuMallUrl(form.url.trim())"
              size="small"
              type="danger"
              class="url-inline-hint"
            >
              {{ temuMallUrlErrorMessage }}
            </el-text>
          </el-form-item>
          <el-form-item>
            <el-space>
              <el-button type="primary" :loading="loading" @click="submitCompetitor">
                {{ form.id ? '保存修改' : '添加竞店' }}
              </el-button>
              <el-button v-if="form.id" @click="resetForm">取消编辑</el-button>
            </el-space>
          </el-form-item>
        </el-form>

        <SearchableTable
          v-loading="loading"
          :data="competitors"
          :fields="['label', 'url']"
          placeholder="搜索备注 / 店铺链接"
          empty-text="暂未添加竞店，请先补充店铺链接"
          :page-size="10"
          size="small"
          class="competitor-table"
        >
          <el-table-column prop="label" label="备注名称" min-width="120" />
          <el-table-column label="店铺网址" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="url-cell">
                <el-link :href="row.url" target="_blank" type="primary" :underline="false">
                  {{ row.url }}
                </el-link>
                <el-tag
                  v-if="!isTemuMallUrl(row.url)"
                  size="small"
                  type="warning"
                  effect="plain"
                >
                  链接非店铺
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="最近爬取" width="160">
            <template #default="{ row }">
              <el-text v-if="row.lastAnalyzedAt" size="small">{{ row.lastAnalyzedAt }}</el-text>
              <el-text v-else size="small" type="info">未爬取</el-text>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="editCompetitor(row)">编辑</el-button>
              <el-button link type="danger" @click="removeCompetitor(row)">移除</el-button>
            </template>
          </el-table-column>
        </SearchableTable>

        <div class="settings-actions">
          <el-button
            type="primary"
            :icon="Search"
            :loading="analyzing"
            :disabled="!competitors.length"
            @click="runAnalysis"
          >
            执行今日爬取分析
          </el-button>
          <el-text size="small" type="info">
            默认遵守冷却；冷却时可强制刷新。每日爬取一次，自动对比昨日快照，抽取竞店新品与销量激增商品
          </el-text>
        </div>
      </div>
    </el-card>

    <el-alert
      v-if="analysisError"
      type="warning"
      closable
      show-icon
      :title="analysisError.title"
      @close="analysisError = null"
    >
      <template #default>
        <p class="analysis-alert-text">{{ analysisError.summary }}</p>
        <ol v-if="analysisError.steps?.length" class="analysis-steps">
          <li v-for="(step, index) in analysisError.steps" :key="index">{{ step }}</li>
        </ol>
      </template>
    </el-alert>

    <el-empty
      v-if="!reports.length"
      description="执行竞店分析后，这里会直接展示结果，并支持导出 Excel"
      :image-size="96"
    />

    <div v-else class="report-list">
      <el-card
        v-for="report in reports"
        :key="report.id"
        shadow="never"
        class="report-card"
      >
        <template #header>
          <div class="report-head">
            <div>
              <strong>{{ report.label }}</strong>
              <el-text size="small" type="info">{{ report.host }}</el-text>
            </div>
            <el-space wrap>
              <el-tag size="small" effect="plain">
                <el-icon style="vertical-align: -2px"><Refresh /></el-icon>
                {{ reportCrawlDateText(report) }}
              </el-tag>
              <el-text size="small" type="info">已存 {{ report.snapshotCount }} 天快照</el-text>
              <el-link :href="report.url" target="_blank" type="primary">访问店铺</el-link>
              <el-button
                v-if="useBackendData && canExportReport(report)"
                size="small"
                type="primary"
                plain
                :icon="Download"
                :loading="exportingReportId === report.id"
                @click="handleExport(report)"
              >
                导出 Excel
              </el-button>
            </el-space>
          </div>
        </template>

        <div class="summary-row">
          <div class="summary-item">
            <span>在售商品</span>
            <strong>{{ report.summary.totalProducts }}</strong>
          </div>
          <div class="summary-item highlight">
            <span>今日上新</span>
            <strong>{{ report.summary.newToday }}</strong>
          </div>
          <div class="summary-item">
            <span>近 7 日上新</span>
            <strong>{{ report.summary.recentListings }}</strong>
          </div>
          <div class="summary-item warn">
            <span>销量异常</span>
            <strong>{{ report.summary.salesSpikes }}</strong>
          </div>
        </div>

        <div v-if="useBackendData" class="monitor-meta">
          <el-space wrap>
            <el-tag :type="report.hasFreshData ? 'success' : 'warning'" size="small" effect="dark">
              {{ report.hasFreshData ? 'Fresh Snapshot' : 'Latest Miss' }}
            </el-tag>
            <el-tag v-if="report.latestJobStatus" :type="jobStatusType(report.latestJobStatus)" size="small" effect="plain">
              {{ jobStatusText(report.latestJobStatus) }}
            </el-tag>
            <el-text v-if="report.reason" size="small" type="info">
              {{ report.reason }}
            </el-text>
            <el-text v-if="report.latestJobId" size="small" type="info">
              Job: {{ report.latestJobId }}
            </el-text>
          </el-space>

          <el-text
            v-if="report.latestJobStatus === 'failed' && report.latestJobError"
            size="small"
            type="danger"
            class="job-error-text"
          >
            {{ report.latestJobError.title }}：{{ report.latestJobError.summary || report.latestJobErrorMessage }}
          </el-text>

          <div v-if="report.artifacts?.report_md_path || report.artifacts?.report_xlsx_path" class="artifact-list">
            <el-text size="small" type="info">
              Markdown: {{ report.artifacts.report_md_path || '未生成' }}
            </el-text>
            <el-text size="small" type="info">
              Excel: {{ report.artifacts.report_xlsx_path || '未生成' }}
            </el-text>
          </div>
        </div>

        <div class="section">
          <div class="section-head">
            <strong>上新明细</strong>
            <el-text size="small" type="info">
              对比 {{ report.previousCrawlDate || '历史快照' }} 识别出的新品
            </el-text>
          </div>
          <SearchableTable
            v-if="report.recentListings.length"
            :data="report.recentListings"
            :fields="['name', 'category']"
            placeholder="搜索商品 / 品类"
            empty-text="暂无上新明细"
            size="small"
            stripe
          >
            <el-table-column prop="name" label="商品名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="category" label="品类" width="110" />
            <el-table-column prop="priceText" label="售价" width="100" align="right" />
            <el-table-column prop="dailySales" label="日销" width="80" align="center" />
            <el-table-column prop="totalSales" label="累计销量" width="100" align="center" />
            <el-table-column prop="listedLabel" label="上架日期" width="120" />
            <el-table-column label="链接" width="90" align="center">
              <template #default="{ row }">
                <el-link :href="row.url" target="_blank" type="primary" size="small">查看</el-link>
              </template>
            </el-table-column>
          </SearchableTable>
          <el-empty v-else :description="recentListingsEmptyText(report, useBackendData)" :image-size="64" />
        </div>

        <div class="section">
          <div class="section-head">
            <strong>销量异常明细</strong>
            <el-text size="small" type="info">
              展示当前快照中识别出的销量异常商品
            </el-text>
          </div>
          <SearchableTable
            v-if="report.salesSpikes.length"
            :data="report.salesSpikes"
            :fields="['name', 'category', 'anomalyType']"
            placeholder="搜索商品 / 品类 / 异常类型"
            empty-text="暂无销量异常"
            size="small"
            stripe
          >
            <el-table-column prop="name" label="商品名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="category" label="品类" width="110" />
            <el-table-column label="异常类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.severity === 'high' ? 'danger' : 'warning'" size="small" effect="dark">
                  {{ row.anomalyType }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="priceText" label="售价" width="100" align="right" />
            <el-table-column prop="dailySales" label="日销" width="80" align="center" />
            <el-table-column prop="totalSales" label="累计销量" width="100" align="center" />
            <el-table-column prop="listedLabel" label="上架日期" width="120" />
            <el-table-column label="链接" width="90" align="center">
              <template #default="{ row }">
                <el-link :href="row.url" target="_blank" type="primary" size="small">查看</el-link>
              </template>
            </el-table-column>
          </SearchableTable>
          <el-empty v-else :description="salesSpikesEmptyText(report, useBackendData)" :image-size="64" />
        </div>

        <div v-if="useBackendData" class="section">
          <div class="section-head">
            <strong>抓取任务结果</strong>
            <el-text size="small" type="info">
              展示最近任务状态，便于运营确认是否已经抓到最新数据
            </el-text>
          </div>
          <SearchableTable
            v-if="report.history?.jobs?.length"
            :data="report.history.jobs"
            :fields="['job_id', 'status', 'trigger_type', 'error_message']"
            placeholder="搜索 Job / 状态"
            empty-text="暂无抓取任务记录"
            size="small"
            stripe
          >
            <el-table-column prop="job_id" label="Job ID" min-width="180" show-overflow-tooltip />
            <el-table-column prop="trigger_type" label="触发方式" width="100" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="jobStatusType(row.status)" size="small" effect="plain">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="queued_at" label="排队时间" min-width="160" />
            <el-table-column prop="finished_at" label="结束时间" min-width="160" />
            <el-table-column label="失败原因" min-width="300" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.error_code">
                  {{ jobErrorDisplay(row).title }}
                </span>
                <span v-else>{{ row.error_message }}</span>
              </template>
            </el-table-column>
          </SearchableTable>
          <el-empty v-else description="暂无抓取任务记录" :image-size="64" />
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.competitor-analysis {
  display: grid;
  gap: 16px;
}

.settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mall-url-guide {
  margin-bottom: 12px;
}

.mall-url-guide-list {
  margin: 0;
  padding-left: 1.2em;
  line-height: 1.65;
}

.mall-url-guide-list li + li {
  margin-top: 4px;
}

.settings-form {
  max-width: 720px;
  margin-bottom: 8px;
}

.url-inline-hint {
  display: block;
  margin-top: 6px;
  line-height: 1.5;
}

.discovery-panel {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
}

.discovery-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.discovery-login-alert {
  margin-bottom: 4px;
}

.discovery-head strong {
  display: block;
  margin-bottom: 4px;
}

.discovery-table {
  margin-bottom: 4px;
}

.candidate-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.candidate-name strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sample-products {
  display: grid;
  gap: 2px;
}

.sample-product {
  overflow: hidden;
  max-width: 100%;
  color: var(--el-text-color-regular);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.competitor-table {
  margin-bottom: 16px;
}

.url-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.url-cell .el-link {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding-top: 4px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.report-list {
  display: grid;
  gap: 16px;
}

.report-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-head strong {
  display: block;
  margin-bottom: 4px;
}

.summary-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.summary-item {
  padding: 12px;
  border-radius: 8px;
  text-align: center;
  background: var(--el-fill-color-light);
}

.summary-item.highlight strong {
  color: var(--el-color-success);
}

.summary-item.warn strong {
  color: var(--el-color-danger);
}

.summary-item span {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.summary-item strong {
  font-size: 22px;
}

.section {
  margin-bottom: 20px;
}

.section:last-child {
  margin-bottom: 0;
}

.section-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.monitor-meta {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.artifact-list {
  display: grid;
  gap: 4px;
}

.job-error-text {
  line-height: 1.6;
}

.analysis-alert-text {
  margin: 0;
  line-height: 1.6;
}

.analysis-steps {
  margin: 8px 0 0;
  padding-left: 20px;
  line-height: 1.7;
}

@media (max-width: 768px) {
  .summary-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .discovery-head,
  .report-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
