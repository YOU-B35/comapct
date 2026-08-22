<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { AI_IMAGE_QUALITIES, AI_IMAGE_RATIOS } from '../constants'
import {
  AI_IMAGE_PROVIDERS,
  loadAiImageSettings,
  loadAiImageStats,
  resetAiImageStats,
  saveAiImageSettings,
} from '../settings'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  activeTab: { type: String, default: 'api' },
})

const emit = defineEmits(['update:modelValue', 'update:activeTab', 'saved'])

const form = reactive({
  configName: '',
  provider: 'hyhacct',
  model: 'gpt-image-2-max',
  apiUrl: '/api-proxy',
  apiKey: '',
  showGuideOnEnter: true,
  defaultRatio: '1:1',
  defaultQuality: 'high',
  defaultCount: 1,
  agentEnabled: true,
})

const stats = reactive({
  success: 0,
  failed: 0,
  images: 0,
  lastAt: 0,
})

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const tab = computed({
  get: () => props.activeTab || 'api',
  set: (v) => emit('update:activeTab', v),
})

const providerLabel = computed(() => {
  return AI_IMAGE_PROVIDERS.find((p) => p.value === form.provider)?.label || form.provider || '—'
})

function hydrate() {
  Object.assign(form, loadAiImageSettings())
  Object.assign(stats, loadAiImageStats())
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) hydrate()
  },
  { immediate: true },
)

function save() {
  const next = saveAiImageSettings({
    configName: String(form.configName || '').trim() || '默认 hyhacct 配置',
    provider: form.provider || 'hyhacct',
    model: form.model || 'gpt-image-2-max',
    apiUrl: String(form.apiUrl || '').trim() || '/api-proxy',
    apiKey: String(form.apiKey || '').trim(),
    showGuideOnEnter: !!form.showGuideOnEnter,
    defaultRatio: form.defaultRatio || '1:1',
    defaultQuality: form.defaultQuality || 'high',
    defaultCount: Math.max(1, Math.min(4, Number(form.defaultCount) || 1)),
    agentEnabled: !!form.agentEnabled,
  })
  emit('saved', next)
  ElMessage.success('设置已保存')
  open.value = false
}

function onResetStats() {
  Object.assign(stats, resetAiImageStats())
  ElMessage.success('统计已清零')
}

function formatTime(ts) {
  return ts ? formatUtc8(ts, { seconds: false }) : '—'
}
</script>

<template>
  <el-dialog
    v-model="open"
    title="设置"
    width="420px"
    top="8vh"
    append-to-body
    destroy-on-close
    :close-on-click-modal="true"
    class="ai-settings-dialog"
    modal-class="ai-settings-overlay"
  >
    <el-tabs v-model="tab" class="ai-settings-tabs">
      <el-tab-pane label="API" name="api">
        <div class="ai-settings-stack">
          <section class="ai-settings-card ai-settings-card--primary">
            <header class="ai-settings-card__head">
              <h4>API Key <span class="ai-badge ai-badge--ok">可改</span></h4>
            </header>
            <el-input
              v-model="form.apiKey"
              size="small"
              type="password"
              show-password
              placeholder="留空则用环境变量"
            />
            <p class="ai-settings-hint">填写后优先生效，用于生图鉴权。</p>
          </section>

          <section class="ai-settings-card">
            <header class="ai-settings-card__head">
              <h4>通道信息 <span class="ai-badge">只读</span></h4>
            </header>
            <dl class="ai-kv">
              <div class="ai-kv__row">
                <dt>模型</dt>
                <dd>{{ form.model || 'gpt-image-2-max' }}</dd>
              </div>
              <div class="ai-kv__row">
                <dt>服务商</dt>
                <dd>{{ providerLabel }}</dd>
              </div>
              <div class="ai-kv__row">
                <dt>代理</dt>
                <dd><code>{{ form.apiUrl || '/api-proxy' }}</code></dd>
              </div>
              <div class="ai-kv__row">
                <dt>备注</dt>
                <dd>{{ form.configName || '—' }}</dd>
              </div>
            </dl>
            <p class="ai-settings-hint">上游固定 <code>gpt-image-2-max</code>，经本站代理转发。</p>
          </section>
        </div>
      </el-tab-pane>

      <el-tab-pane label="偏好" name="app">
        <div class="ai-settings-stack">
          <section class="ai-settings-card ai-settings-card--primary">
            <header class="ai-settings-card__head">
              <h4>默认参数 <span class="ai-badge ai-badge--ok">可改</span></h4>
            </header>
            <el-form label-position="top" size="small" class="ai-settings-form">
              <div class="ai-settings-grid">
                <el-form-item label="比例">
                  <el-select v-model="form.defaultRatio" style="width: 100%">
                    <el-option
                      v-for="item in AI_IMAGE_RATIOS"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="质量">
                  <el-select v-model="form.defaultQuality" style="width: 100%">
                    <el-option
                      v-for="item in AI_IMAGE_QUALITIES"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="数量">
                  <el-input-number
                    v-model="form.defaultCount"
                    :min="1"
                    :max="4"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </div>
            </el-form>
          </section>

          <section class="ai-settings-card">
            <div class="ai-settings-row">
              <div>
                <strong>进入显示操作指南</strong>
                <p>首次进入时弹出</p>
              </div>
              <el-switch v-model="form.showGuideOnEnter" size="small" />
            </div>
          </section>
        </div>
      </el-tab-pane>

      <el-tab-pane label="Agent" name="agent">
        <section class="ai-settings-card ai-settings-card--primary">
          <div class="ai-settings-row">
            <div>
              <strong>启用 Agent 模板</strong>
              <p>只复制到剪贴板，不自动填入</p>
            </div>
            <el-switch v-model="form.agentEnabled" size="small" />
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="统计" name="stats">
        <section class="ai-settings-card">
          <div class="ai-stats">
            <div class="ai-stats__item">
              <strong>{{ stats.success }}</strong>
              <span>成功</span>
            </div>
            <div class="ai-stats__item">
              <strong>{{ stats.failed }}</strong>
              <span>失败</span>
            </div>
            <div class="ai-stats__item">
              <strong>{{ stats.images }}</strong>
              <span>出图</span>
            </div>
          </div>
          <div class="ai-settings-foot">
            <p class="ai-settings-hint">最近：{{ formatTime(stats.lastAt) }}（本机）</p>
            <el-button size="small" @click="onResetStats">清零</el-button>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="关于" name="about">
        <section class="ai-settings-card ai-about">
          <h3>CrossHub AI 生图</h3>
          <p>GPT Image / hyhacct，经 <code>/api-proxy</code> 转发。日常参数用底部「进阶参数」。</p>
          <p class="ai-settings-hint">模型：<code>gpt-image-2-max</code> · @CrossHub</p>
        </section>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button size="small" @click="open = false">取消</el-button>
      <el-button size="small" type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.ai-settings-tabs :deep(.el-tabs__header) {
  margin-bottom: 10px;
}

.ai-settings-tabs :deep(.el-tabs__item) {
  font-weight: 600;
  font-size: 13px;
  height: 34px;
  padding: 0 12px !important;
}

.ai-settings-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
}

.ai-settings-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-settings-card {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.ai-settings-card--primary {
  background: #fff;
  border-color: #dbeafe;
}

.ai-settings-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.ai-settings-card__head h4 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.ai-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
}

.ai-badge--ok {
  background: #dbeafe;
  color: #1d4ed8;
}

.ai-settings-form {
  padding-top: 0;
}

.ai-settings-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.ai-settings-form :deep(.el-form-item__label) {
  margin-bottom: 2px !important;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  line-height: 1.2;
}

.ai-settings-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.ai-settings-hint {
  margin: 6px 0 0;
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}

.ai-settings-hint code,
.ai-about code,
.ai-kv code {
  padding: 0 3px;
  border-radius: 3px;
  background: #f1f5f9;
  color: #475569;
  font-size: 10px;
}

.ai-kv {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ai-kv__row {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 8px;
  align-items: baseline;
  font-size: 12px;
}

.ai-kv__row dt {
  margin: 0;
  color: #94a3b8;
}

.ai-kv__row dd {
  margin: 0;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ai-settings-row strong {
  display: block;
  font-size: 13px;
  color: #0f172a;
  margin-bottom: 2px;
}

.ai-settings-row p {
  margin: 0;
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.35;
}

.ai-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin-bottom: 8px;
}

.ai-stats__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 6px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  text-align: center;
}

.ai-stats__item strong {
  font-size: 18px;
  color: #0f172a;
}

.ai-stats__item span {
  font-size: 11px;
  color: #94a3b8;
}

.ai-settings-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ai-about h3 {
  margin: 0 0 6px;
  font-size: 14px;
  color: #0f172a;
}

.ai-about p {
  margin: 0 0 6px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

@media (max-width: 480px) {
  .ai-settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>

<!-- append-to-body：全局约束弹窗尺寸与遮罩 -->
<style>
.ai-settings-overlay {
  background: rgba(15, 23, 42, 0.28) !important;
}

.ai-settings-dialog.el-dialog {
  width: min(420px, 92vw) !important;
  margin-bottom: 0;
  border-radius: 12px;
  overflow: hidden;
}

.ai-settings-dialog .el-dialog__header {
  padding: 12px 14px 8px;
  margin-right: 0;
}

.ai-settings-dialog .el-dialog__title {
  font-size: 15px;
  font-weight: 700;
}

.ai-settings-dialog .el-dialog__headerbtn {
  top: 12px;
  right: 12px;
  width: 28px;
  height: 28px;
}

.ai-settings-dialog .el-dialog__body {
  padding: 0 14px 8px;
  max-height: min(58vh, 420px);
  overflow: auto;
}

.ai-settings-dialog .el-dialog__footer {
  padding: 8px 14px 12px;
}
</style>
