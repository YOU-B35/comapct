<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { normalizeAiImageModel, produceAiImage } from '../api'
import { sizeFromRatio } from '../constants'
import {
  deleteAiImageHistoryItem,
  loadAiImageHistory,
  saveAiImageHistoryBatch,
} from '../historyDb'
import {
  hasSeenAiImageGuide,
  loadAiImageSettings,
  recordAiImageFailure,
  recordAiImageSuccess,
  resolveAiImageApiKey,
} from '../settings'
import AiImageHero from '../components/AiImageHero.vue'
import AiImageToolbar from '../components/AiImageToolbar.vue'
import AiImageFilterBar from '../components/AiImageFilterBar.vue'
import AiImageResultCard from '../components/AiImageResultCard.vue'
import AiImageComposer from '../components/AiImageComposer.vue'
import AiImageSettingsDialog from '../components/AiImageSettingsDialog.vue'
import AiImageGuideDialog from '../components/AiImageGuideDialog.vue'
import AiImageAgentPanel from '../components/AiImageAgentPanel.vue'

const settings = ref(loadAiImageSettings())

const prompt = ref('生成一个可爱小猫')
const quality = ref(settings.value.defaultQuality || 'high')
const ratio = ref(settings.value.defaultRatio || '1:1')
const steps = ref('auto')
const count = ref(Math.max(1, Math.min(4, Number(settings.value.defaultCount) || 1)))
const model = ref(normalizeAiImageModel(settings.value.model || 'gpt-image-2-max'))
const collection = ref('all')
const keyword = ref('')
const imageFiles = ref([])
const results = ref([])
const historyLoading = ref(false)
const submitting = ref(false)
const progress = ref(0)
const lightboxUrl = ref('')
const abortRef = ref(null)
const listRef = ref(null)

const settingsOpen = ref(false)
const settingsTab = ref('api')
const guideOpen = ref(false)
const agentOpen = ref(false)

const visibleResults = computed(() => {
  let list = results.value
  if (collection.value === 'favorites') {
    list = list.filter((item) => item.favorite)
  }
  const q = keyword.value.trim().toLowerCase()
  if (q) {
    list = list.filter((item) => String(item.prompt || '').toLowerCase().includes(q))
  }
  return list
})

const progressHint = computed(() => {
  const p = Number(progress.value) || 0
  if (p >= 100) return '生成完成，正在展示结果…'
  if (p >= 90) return '即将完成，正在解析返回图片…'
  if (p >= 40) return '模型绘制中，通常需要约 1 分钟，请勿关闭页面…'
  return '已提交任务，正在排队/生成中…'
})

onMounted(async () => {
  historyLoading.value = true
  try {
    results.value = await loadAiImageHistory()
  } catch (err) {
    console.warn('[ai-image] load history failed', err)
  } finally {
    historyLoading.value = false
  }
  if (settings.value.showGuideOnEnter && !hasSeenAiImageGuide()) {
    guideOpen.value = true
  }
})

onUnmounted(() => {
  abortRef.value?.abort()
})

function applySettings(next) {
  settings.value = next
  if (next.model) model.value = next.model
  if (next.defaultRatio) ratio.value = next.defaultRatio
  if (next.defaultQuality) quality.value = next.defaultQuality
  if (next.defaultCount) count.value = Math.max(1, Math.min(4, Number(next.defaultCount) || 1))
}

function onPickFiles(files) {
  imageFiles.value = (files || []).filter((f) => f instanceof File)
  if (imageFiles.value.length) {
    ElMessage.success(`已添加 ${imageFiles.value.length} 张参考图`)
  }
}

function onToolbarUpload() {
  ElMessage.info('请使用底部输入栏右侧回形针上传参考图')
}

async function sharePayload({ title, text, url } = {}) {
  const payload = {
    title: title || 'CrossHub AI 生图',
    text: text || '',
    url: url || '',
  }
  try {
    if (navigator.share && (payload.url || payload.text)) {
      await navigator.share({
        title: payload.title,
        text: payload.text,
        url: payload.url || undefined,
      })
      ElMessage.success('已打开系统分享')
      return
    }
  } catch (err) {
    if (err?.name === 'AbortError') return
  }
  const clipboard = [payload.text, payload.url].filter(Boolean).join('\n')
  if (!clipboard) {
    ElMessage.warning('暂无可分享内容')
    return
  }
  try {
    await navigator.clipboard.writeText(clipboard)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('分享失败，请手动复制')
  }
}

async function onToolbarShare() {
  const latest = results.value[0]
  if (!latest) {
    ElMessage.info('暂无生成记录，可先生成一张再分享')
    return
  }
  await sharePayload({
    title: 'CrossHub AI 生图',
    text: latest.prompt || '',
    url: latest.url || '',
  })
}

function onToolbarHistory() {
  listRef.value?.scrollTo?.({ top: 0, behavior: 'smooth' })
}

function onToolbarSettings() {
  settingsTab.value = 'api'
  settingsOpen.value = true
}

function onToolbarAgent() {
  if (!settings.value.agentEnabled) {
    ElMessage.warning('Agent 已在设置中关闭，可到设置 → Agent 配置开启')
    settingsTab.value = 'agent'
    settingsOpen.value = true
    return
  }
  agentOpen.value = true
}

function onToolbarGuide() {
  guideOpen.value = true
}

function onApplyAgentTemplate(item) {
  prompt.value = item?.prompt || ''
  ElMessage.success(`已填入模板：${item?.label || 'Agent'}`)
}

async function refreshList() {
  historyLoading.value = true
  try {
    results.value = await loadAiImageHistory()
    ElMessage.success(`已刷新，共 ${results.value.length} 条记录`)
  } catch (err) {
    ElMessage.error(err?.message || '刷新失败')
  } finally {
    historyLoading.value = false
  }
}

async function submit() {
  const text = String(prompt.value || '').trim()
  if (!text) {
    ElMessage.warning('请输入提示词')
    return
  }
  if (!resolveAiImageApiKey(settings.value)) {
    ElMessage.error('未配置 API Key，请到设置中填写，或配置 VITE_GPT_IMAGE_API_KEY')
    settingsTab.value = 'api'
    settingsOpen.value = true
    return
  }

  abortRef.value?.abort()
  const controller = new AbortController()
  abortRef.value = controller
  submitting.value = true
  progress.value = 1

  try {
    const images = await produceAiImage({
      prompt: text,
      model: model.value,
      size: sizeFromRatio(ratio.value),
      quality: quality.value,
      n: count.value,
      images: imageFiles.value,
      signal: controller.signal,
      onProgress: (p) => {
        progress.value = Math.max(1, Math.min(100, Number(p) || 0))
      },
    })
    const stamp = Date.now()
    const batch = images.map((img, index) => ({
      ...img,
      id: `${stamp}-${index}`,
      prompt: text,
      model: model.value,
      quality: quality.value,
      ratio: ratio.value,
      steps: steps.value,
      count: count.value,
      createdAt: stamp,
      favorite: false,
      remoteUrl: img.url,
    }))
    results.value = [...batch, ...results.value]
    progress.value = 100
    recordAiImageSuccess(batch.length)
    // 与原站一致：写入 IndexedDB（元数据 + 图片缓存）
    saveAiImageHistoryBatch(batch).catch((err) => {
      console.warn('[ai-image] persist history failed', err)
    })
    ElMessage.success(`已生成 ${batch.length} 张图片`)
  } catch (err) {
    if (err?.name === 'AbortError') return
    recordAiImageFailure()
    ElMessage.error(err?.message || '生图失败')
  } finally {
    submitting.value = false
    progress.value = 0
  }
}

async function copyPrompt(item) {
  try {
    await navigator.clipboard.writeText(item.prompt || '')
    ElMessage.success('提示词已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

function downloadImage(item) {
  const a = document.createElement('a')
  a.href = item.url
  a.download = `ai-image-${item.id}.png`
  a.target = '_blank'
  a.rel = 'noopener'
  a.click()
}

function editPrompt(item) {
  prompt.value = item.prompt || ''
  quality.value = item.quality || quality.value
  ratio.value = item.ratio || ratio.value
  ElMessage.success('已填回底部输入栏')
}

async function shareItem(item) {
  await sharePayload({
    title: 'CrossHub AI 生图',
    text: item?.prompt || '',
    url: item?.url || '',
  })
}

async function removeItem(item) {
  results.value = results.value.filter((row) => row.id !== item.id)
  try {
    await deleteAiImageHistoryItem(item.id)
  } catch (err) {
    console.warn('[ai-image] delete history failed', err)
  }
}
</script>

<template>
  <div class="ai-page">
    <div class="ai-page__inner">
      <AiImageHero />
      <AiImageToolbar
        :refreshing="historyLoading"
        @refresh="refreshList"
        @upload="onToolbarUpload"
        @share="onToolbarShare"
        @history="onToolbarHistory"
        @settings="onToolbarSettings"
        @agent="onToolbarAgent"
        @guide="onToolbarGuide"
      />
      <AiImageFilterBar v-model:collection="collection" v-model:keyword="keyword" />

      <div ref="listRef" class="ai-page__list">
        <div v-if="historyLoading && !visibleResults.length" class="ai-empty">
          <p>正在加载历史记录…</p>
          <span>读取本机 IndexedDB（与原站同模式）</span>
        </div>
        <div v-else-if="!visibleResults.length" class="ai-empty">
          <p>暂无生成记录</p>
          <span>在下方输入提示词后点击蓝色按钮开始生成</span>
        </div>
        <div v-else class="ai-list">
          <AiImageResultCard
            v-for="item in visibleResults"
            :key="item.id"
            :item="item"
            @preview="lightboxUrl = $event.url"
            @copy="copyPrompt"
            @download="downloadImage"
            @edit="editPrompt"
            @share="shareItem"
            @remove="removeItem"
          />
        </div>
      </div>
    </div>

    <div class="ai-page__composer">
      <div v-if="submitting" class="ai-progress">
        <el-progress
          :percentage="progress"
          :stroke-width="10"
          striped
          striped-flow
          :status="progress >= 100 ? 'success' : undefined"
        />
        <p class="ai-progress__hint">{{ progressHint }}</p>
      </div>
      <AiImageComposer
        v-model:prompt="prompt"
        v-model:quality="quality"
        v-model:ratio="ratio"
        v-model:steps="steps"
        v-model:count="count"
        v-model:model="model"
        :submitting="submitting"
        :file-count="imageFiles.length"
        @pick-files="onPickFiles"
        @submit="submit"
      />
    </div>

    <el-dialog
      :model-value="!!lightboxUrl"
      width="min(920px, 92vw)"
      append-to-body
      destroy-on-close
      @update:model-value="(open) => { if (!open) lightboxUrl = '' }"
    >
      <img v-if="lightboxUrl" :src="lightboxUrl" class="ai-lightbox" alt="preview" />
    </el-dialog>

    <AiImageSettingsDialog
      v-model="settingsOpen"
      v-model:active-tab="settingsTab"
      @saved="applySettings"
    />
    <AiImageGuideDialog v-model="guideOpen" />
    <AiImageAgentPanel v-model="agentOpen" @apply="onApplyAgentTemplate" />
  </div>
</template>

<style scoped>
.ai-page {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  background: var(--ch-layout-bg);
  overflow: hidden;
}

.ai-page__inner {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px 140px;
  overflow: hidden;
}

.ai-page__list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.ai-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 960px;
}

.ai-empty {
  height: 100%;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--ch-text-muted);
  border: 1px dashed var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
}

.ai-empty p {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: var(--ch-text-secondary);
}

.ai-empty span {
  font-size: 13px;
}

.ai-page__composer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 18px;
  z-index: 5;
  pointer-events: none;
}

.ai-page__composer :deep(.ai-composer),
.ai-progress {
  pointer-events: auto;
}

.ai-progress {
  max-width: 960px;
  margin: 0 auto 10px;
  padding: 10px 14px 6px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.ai-progress__hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
  text-align: center;
}

.ai-lightbox {
  width: 100%;
  max-height: 75vh;
  object-fit: contain;
  display: block;
}
</style>
