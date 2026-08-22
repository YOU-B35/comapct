<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, onMounted, watch } from 'vue'
import {
  Document,
  Download,
  Monitor,
  Refresh,
  Shop,
  Upload,
} from '@element-plus/icons-vue'
import { useCommanderAuthStore } from '../stores/commanderAuth'
import { useCommanderAutoUploadStore } from '../stores/autoUpload'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'

const auth = useCommanderAuthStore()
const store = useCommanderAutoUploadStore()

const shopOptions = computed(() =>
  store.shopList
    .map((s) => ({
      value: String(s.id ?? s.shop_id ?? s.shopId ?? ''),
      label: s.name || s.shopName || String(s.id ?? ''),
    }))
    .filter((o) => o.value),
)

const canSubmit = computed(
  () => Boolean(store.selectedAgent) && Boolean(store.shopId) && Boolean(store.excelFile),
)

async function loadWorkspace() {
  if (!auth.isAuthenticated) return
  await store.fetchAgents()
  await store.fetchTasks()
}

onMounted(async () => {
  await auth.bootstrap()
  await loadWorkspace()
})

watch(
  () => auth.isAuthenticated,
  async (ok) => {
    if (ok) await loadWorkspace()
  },
)

watch(
  () => store.selectedPlatform,
  async () => {
    if (!auth.isAuthenticated) return
    store.shopId = ''
    if (store.selectedAgent) {
      await store.fetchShops()
      await store.fetchTasks(1)
    }
  },
)

async function refreshAll() {
  await store.fetchAgents()
  if (store.selectedAgent) {
    await store.fetchShops()
    await store.fetchTasks()
  } else {
    await store.fetchTasks()
  }
}

function onFileChange(uploadFile) {
  store.excelFile = uploadFile?.raw || null
}

function clearFile() {
  store.excelFile = null
}

/** 批量上货 Excel 模板（public/templates） */
const PLATFORM_TEMPLATES = {
  temu: {
    url: `${import.meta.env.BASE_URL}templates/temu-batch-upload.xlsx`,
    filename: 'Temu批量上货表单.xlsx',
  },
  douyin: {
    url: `${import.meta.env.BASE_URL}templates/douyin-publish-template.xlsx`,
    filename: '抖店Excel上货模板.xlsx',
  },
  1688: {
    url: `${import.meta.env.BASE_URL}templates/1688-publish-template.xlsx`,
    filename: '1688Excel上货模板.xlsx',
  },
}

const canDownloadTemplate = computed(() => Boolean(PLATFORM_TEMPLATES[store.selectedPlatform]))

function downloadTemplate() {
  const tpl = PLATFORM_TEMPLATES[store.selectedPlatform]
  if (!tpl) return
  const a = document.createElement('a')
  a.href = tpl.url
  a.download = tpl.filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
}

const uploadHint = computed(() => {
  if (store.selectedPlatform === 'douyin') {
    return '请按抖店 Excel 上货模板填写后上传；可点右上角「下载模板」获取空白表，并确保抖店 Agent 处于开启状态。'
  }
  if (store.selectedPlatform === '1688') {
    return '请按 1688 Excel 上货模板填写后上传；可点右上角「下载模板」获取空白表，并确保 1688 Agent 处于开启状态。'
  }
  if (store.selectedPlatform === 'temu') {
    return '请按 Temu 批量上货表单填写后上传；可点右上角「下载模板」获取空白表。'
  }
  return '请按所选平台的 Excel 上货模板填写后上传。'
})

function agentLabel(agent) {
  return agent?.name || store.agentIdOf(agent) || 'Agent'
}

function isSelectedAgent(agent) {
  return store.agentIdOf(store.selectedAgent) === store.agentIdOf(agent)
}

function taskIdOf(row) {
  return row?.taskId || row?.id || row?.uuid || ''
}

function shortId(id) {
  const s = String(id || '')
  if (s.length <= 12) return s || '—'
  return `${s.slice(0, 8)}…${s.slice(-4)}`
}

function formatTaskTime(row) {
  const raw = row?.createAt ?? row?.createTime ?? row?.updateTime ?? row?.created_at
  return raw == null || raw === '' ? '—' : formatUtc8(raw)
}

function statusMeta(row) {
  const raw = String(row?.status || row?.state || row?.taskStatus || '').trim().toLowerCase()
  if (!raw) return { label: '—', type: 'info' }
  if (['success', 'succeeded', 'done', 'completed', 'finish', 'finished', 'ok'].includes(raw)) {
    return { label: raw, type: 'success' }
  }
  if (['fail', 'failed', 'error', 'timeout', 'cancelled', 'canceled'].includes(raw)) {
    return { label: raw, type: 'danger' }
  }
  if (['running', 'pending', 'processing', 'queue', 'queued', 'waiting', 'doing'].includes(raw)) {
    return { label: raw, type: 'warning' }
  }
  return { label: raw, type: 'info' }
}

const statusAlertType = computed(() => {
  const t = store.statusMessage?.type
  if (t === 'error') return 'error'
  if (t === 'success') return 'success'
  return 'info'
})
</script>

<template>
  <PageScroll class="auto-upload">
    <PageHeader
      title="自动上货"
      eyebrow="Commander"
      description="选择 Agent → 选店铺 → 上传 Excel（经本站代登 Commander）"
    >
      <template v-if="auth.isAuthenticated" #actions>
        <el-button size="small" :icon="Refresh" :loading="store.agentLoading" @click="refreshAll">
          刷新
        </el-button>
      </template>
    </PageHeader>

    <div v-if="!auth.ready" v-loading="true" class="auto-upload__boot" />

    <el-alert
      v-else-if="!auth.isAuthenticated"
      type="warning"
      :closable="false"
      show-icon
      title="请先登录 CrossHub，再使用自动上货"
      class="auto-upload__alert"
    />

    <template v-else>
      <PageSection>
        <template #header>
          <div class="section-title">
            <el-icon class="section-title__icon"><Monitor /></el-icon>
            <span>选择 Agent</span>
            <el-tag v-if="store.onlineAgents.length" size="small" type="success" effect="plain" round>
              {{ store.onlineAgents.length }} 在线
            </el-tag>
          </div>
        </template>
        <template #actions>
          <el-radio-group v-model="store.selectedPlatform" size="small">
            <el-radio-button
              v-for="p in store.platformOptions"
              :key="p.value"
              :value="p.value"
            >
              {{ p.label }}
            </el-radio-button>
          </el-radio-group>
        </template>

        <el-alert
          v-if="store.agentListError"
          type="warning"
          :closable="false"
          :title="store.agentListError"
          class="inline-alert"
        />
        <el-alert
          v-else-if="store.selectedPlatform === 'douyin' && !store.agentLoading && !store.onlineAgents.length"
          type="warning"
          :closable="false"
          title="未检测到在线 Agent。请打开桌面 Agent、开启「抖店」，并确认已连接到 www.yoto.work"
          class="inline-alert"
        />

        <div v-loading="store.agentLoading" class="agent-grid-wrap">
          <el-empty
            v-if="!store.agentLoading && !store.onlineAgents.length"
            :image-size="72"
            description="没有在线 Agent"
          />
          <div v-else class="agent-grid">
            <button
              v-for="agent in store.onlineAgents"
              :key="store.agentIdOf(agent)"
              type="button"
              class="agent-card"
              :class="{ 'is-selected': isSelectedAgent(agent) }"
              @click="store.selectAgent(agent)"
            >
              <span class="agent-card__icon" aria-hidden="true">
                <el-icon :size="20"><Monitor /></el-icon>
              </span>
              <span class="agent-card__body">
                <span class="agent-card__name" :title="agentLabel(agent)">{{ agentLabel(agent) }}</span>
                <span class="agent-card__meta">在线 · 可上货</span>
              </span>
              <span class="agent-card__dot" title="在线" />
            </button>
          </div>
        </div>
      </PageSection>

      <PageSection>
        <template #header>
          <div class="section-title">
            <el-icon class="section-title__icon"><Upload /></el-icon>
            <span>批量上货</span>
          </div>
        </template>
        <template #actions>
          <el-button
            v-if="canDownloadTemplate"
            size="small"
            :icon="Download"
            @click="downloadTemplate"
          >
            下载模板
          </el-button>
        </template>

        <div class="upload-bar">
          <div class="upload-field">
            <span class="upload-field__label">
              <el-icon><Shop /></el-icon>
              店铺
            </span>
            <el-select
              v-model="store.shopId"
              filterable
              clearable
              :loading="store.shopLoading"
              :disabled="!store.selectedAgent"
              placeholder="请先选择 Agent"
              class="upload-field__control"
            >
              <el-option
                v-for="opt in shopOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>

          <div class="upload-field upload-field--file">
            <span class="upload-field__label">
              <el-icon><Document /></el-icon>
              Excel
            </span>
            <el-upload
              class="upload-field__uploader"
              :auto-upload="false"
              :limit="1"
              accept=".xlsx,.xls,.csv"
              :show-file-list="true"
              :on-change="onFileChange"
              :on-remove="clearFile"
            >
              <el-button :icon="Upload">选择文件</el-button>
            </el-upload>
          </div>

          <el-button
            type="primary"
            class="upload-bar__submit"
            :loading="store.submitting"
            :disabled="!canSubmit"
            @click="store.submitExcel()"
          >
            提交上货任务
          </el-button>
        </div>

        <el-text v-if="store.shopLoadError" type="danger" size="small" class="hint">
          {{ store.shopLoadError }}
        </el-text>
        <el-text type="info" size="small" class="hint">
          {{ uploadHint }}
        </el-text>

        <el-alert
          v-if="store.statusMessage"
          :type="statusAlertType"
          :closable="false"
          show-icon
          :title="store.statusMessage.text"
          class="inline-alert"
        />
      </PageSection>

      <PageSection>
        <template #header>
          <div class="section-title">
            <el-icon class="section-title__icon"><Document /></el-icon>
            <span>任务</span>
          </div>
        </template>
        <template #actions>
          <el-button size="small" text :loading="store.taskLoading" @click="store.fetchTasks()">
            刷新任务
          </el-button>
        </template>

        <el-alert
          v-if="store.taskError"
          type="error"
          :closable="false"
          :title="store.taskError"
          class="inline-alert"
        />

        <el-table
          v-loading="store.taskLoading"
          :data="store.taskList"
          size="small"
          class="task-table"
          empty-text="暂无任务"
        >
          <el-table-column label="任务" min-width="140">
            <template #default="{ row }">
              <el-tooltip :content="taskIdOf(row) || '—'" placement="top" :disabled="!taskIdOf(row)">
                <span class="mono">{{ shortId(taskIdOf(row)) }}</span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="平台" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.platform || store.selectedPlatform }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="statusMeta(row).type" effect="light">
                {{ statusMeta(row).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" min-width="150">
            <template #default="{ row }">{{ formatTaskTime(row) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="88" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="store.retryTask(row)">重试</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="store.taskTotal > store.taskPageSize" class="pager">
          <el-pagination
            background
            layout="prev, pager, next"
            :total="store.taskTotal"
            :page-size="store.taskPageSize"
            :current-page="store.taskPage"
            @current-change="store.fetchTasks"
          />
        </div>
      </PageSection>
    </template>
  </PageScroll>
</template>

<style scoped>
.auto-upload__boot {
  min-height: 160px;
}

.auto-upload__alert {
  margin: 24px 0;
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ch-text, #1d2129);
}

.section-title__icon {
  color: var(--ch-primary, #165dff);
}

.inline-alert {
  margin-bottom: 12px;
}

.hint {
  display: block;
  margin-top: 8px;
}

.agent-grid-wrap {
  min-height: 88px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}

.agent-card {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px 14px 14px 12px;
  border: 1px solid var(--ch-border, #e6eaf0);
  border-radius: 10px;
  background: var(--ch-surface, #fff);
  box-shadow: var(--ch-shadow-xs);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.agent-card:hover {
  border-color: var(--ch-primary-muted, #c5d4f7);
  background: linear-gradient(180deg, #f8faff 0%, #fff 70%);
  box-shadow: var(--ch-shadow-sm);
  transform: translateY(-1px);
}

.agent-card.is-selected {
  border-color: var(--ch-primary, #1f4fd6);
  background: var(--ch-primary-soft, #edf2ff);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--ch-primary, #1f4fd6) 22%, transparent);
}

.agent-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 10px;
  background: var(--ch-primary-soft, #edf2ff);
  color: var(--ch-primary, #1f4fd6);
}

.agent-card.is-selected .agent-card__icon {
  background: color-mix(in srgb, var(--ch-primary, #1f4fd6) 14%, #fff);
}

.agent-card__body {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.agent-card__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ch-text, #1d2129);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-card__meta {
  font-size: 12px;
  color: var(--ch-text-muted, #909399);
}

.agent-card__dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--el-color-success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-success) 18%, transparent);
}

.upload-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 12px 16px;
  padding: 14px;
  border: 1px solid var(--ch-border, #e6eaf0);
  border-radius: 10px;
  background: linear-gradient(180deg, #fbfcfe 0%, #fff 100%);
}

.upload-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 220px;
}

.upload-field--file {
  min-width: 240px;
  flex: 1;
}

.upload-field__label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 650;
  color: var(--ch-text-muted, #6a7689);
}

.upload-field__control {
  width: 280px;
  max-width: 100%;
}

.upload-field__uploader :deep(.el-upload-list) {
  margin-top: 6px;
}

.upload-bar__submit {
  margin-top: 22px;
  align-self: flex-start;
  min-width: 108px;
  border-radius: 8px !important;
  font-weight: 650;
}

.task-table {
  width: 100%;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

@media (max-width: 720px) {
  .upload-field__control {
    width: 100%;
  }

  .upload-bar__submit {
    margin-top: 0;
    width: 100%;
  }
}
</style>
