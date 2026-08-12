<script setup>
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { AI_IMAGE_MODELS } from '../constants'
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
    provider: form.provider,
    model: form.model,
    apiUrl: String(form.apiUrl || '').trim() || '/api-proxy',
    apiKey: String(form.apiKey || '').trim(),
    showGuideOnEnter: !!form.showGuideOnEnter,
    defaultRatio: form.defaultRatio,
    defaultQuality: form.defaultQuality,
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
  if (!ts) return '—'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<template>
  <el-dialog
    v-model="open"
    title="设置"
    width="min(640px, 92vw)"
    append-to-body
    destroy-on-close
    class="ai-settings-dialog"
  >
    <el-tabs v-model="tab">
      <el-tab-pane label="API 配置" name="api">
        <el-form label-position="top" class="ai-settings-form">
          <el-form-item label="当前模型">
            <el-select v-model="form.model" style="width: 100%">
              <el-option
                v-for="item in AI_IMAGE_MODELS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="配置名称">
            <el-input v-model="form.configName" placeholder="例如：默认 hyhacct 配置" />
          </el-form-item>
          <el-form-item label="服务商模型">
            <el-select v-model="form.provider" style="width: 100%">
              <el-option
                v-for="item in AI_IMAGE_PROVIDERS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="API URL">
            <el-input v-model="form.apiUrl" placeholder="/api-proxy" />
            <p class="ai-settings-hint">
              本站默认走同源代理 <code>/api-proxy</code> → hyhacct（OpenAI 兼容）。一般无需改为外网直连。
            </p>
          </el-form-item>
          <el-form-item label="API Key">
            <el-input
              v-model="form.apiKey"
              type="password"
              show-password
              placeholder="留空则使用环境变量 VITE_GPT_IMAGE_API_KEY"
            />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="应用配置" name="app">
        <el-form label-position="top" class="ai-settings-form">
          <el-form-item label="进入页面显示操作指南">
            <el-switch v-model="form.showGuideOnEnter" />
          </el-form-item>
          <el-form-item label="默认比例">
            <el-input v-model="form.defaultRatio" placeholder="1:1" />
          </el-form-item>
          <el-form-item label="默认质量">
            <el-input v-model="form.defaultQuality" placeholder="high" />
          </el-form-item>
          <el-form-item label="默认数量">
            <el-input-number v-model="form.defaultCount" :min="1" :max="4" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="Agent 配置" name="agent">
        <el-form label-position="top" class="ai-settings-form">
          <el-form-item label="启用 Agent 模板">
            <el-switch v-model="form.agentEnabled" />
          </el-form-item>
          <p class="ai-settings-hint">
            Agent 提供电商主图 / 场景图等快捷提示词模板，一键填入底部输入栏，不连接外部对话服务。
          </p>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="数据统计" name="stats">
        <div class="ai-stats">
          <div class="ai-stats__item">
            <strong>{{ stats.success }}</strong>
            <span>成功次数</span>
          </div>
          <div class="ai-stats__item">
            <strong>{{ stats.failed }}</strong>
            <span>失败次数</span>
          </div>
          <div class="ai-stats__item">
            <strong>{{ stats.images }}</strong>
            <span>出图张数</span>
          </div>
        </div>
        <p class="ai-settings-hint">最近一次：{{ formatTime(stats.lastAt) }}（仅本机会话统计）</p>
        <el-button @click="onResetStats">清零统计</el-button>
      </el-tab-pane>

      <el-tab-pane label="关于" name="about">
        <div class="ai-about">
          <h3>CrossHub AI 生图</h3>
          <p>基于 GPT Image / hyhacct（OpenAI 兼容），支持文生图与参考图。接口经本站 <code>/api-proxy</code> 转发。</p>
          <p class="ai-settings-hint">@CrossHub · 电商主图 / 场景图一键生成</p>
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="open = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.ai-settings-form {
  padding-top: 4px;
}

.ai-settings-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.ai-settings-hint code {
  padding: 0 4px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #334155;
}

.ai-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.ai-stats__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  text-align: center;
}

.ai-stats__item strong {
  font-size: 22px;
  color: #0f172a;
}

.ai-stats__item span {
  font-size: 12px;
  color: #64748b;
}

.ai-about h3 {
  margin: 0 0 8px;
  font-size: 16px;
  color: #0f172a;
}

.ai-about p {
  margin: 0 0 8px;
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}
</style>
