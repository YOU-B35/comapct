const SETTINGS_KEY = 'crosshub.ai-image.settings.v1'
const STATS_KEY = 'crosshub.ai-image.stats.v1'
const GUIDE_SEEN_KEY = 'crosshub.ai-image.guide-seen.v1'

export const DEFAULT_AI_IMAGE_SETTINGS = {
  configName: '默认 hyhacct 配置',
  provider: 'hyhacct',
  model: 'gpt-image-2-max',
  apiUrl: '/api-proxy',
  apiKey: '',
  showGuideOnEnter: true,
  defaultRatio: '1:1',
  defaultQuality: 'high',
  defaultCount: 1,
  agentEnabled: true,
}

export const AI_IMAGE_PROVIDERS = [
  { value: 'hyhacct', label: 'hyhacct（本站代理）' },
  { value: 'openai-compatible', label: 'OpenAI 兼容接口' },
]

export const AGENT_PROMPT_TEMPLATES = [
  {
    id: 'main-white',
    label: '电商白底主图',
    prompt:
      '电商产品白底主图，居中摆放，柔和棚拍光，高清细节，无文字无水印，适合详情页主图',
  },
  {
    id: 'scene-lifestyle',
    label: '生活场景图',
    prompt:
      '真实生活场景中的产品展示，自然光线，浅景深，氛围感强，无文字无水印，适合电商场景图',
  },
  {
    id: 'hero-banner',
    label: '横幅 Hero 图',
    prompt:
      '电商横幅背景图，宽构图，金色暖光均匀铺满，产品或主题居中偏右，留白给文案，无文字无水印',
  },
  {
    id: 'packshot',
    label: '包装特写',
    prompt:
      '产品包装盒特写，正面略侧 15 度，材质纹理清晰，柔和环境光，干净背景，无文字变形，无水印',
  },
]

export const GUIDE_STEPS = [
  {
    title: '选择生成方式',
    body: '底部输入框默认为空白占位。可手写提示词；也可直接粘贴图片到输入区做图生图。',
  },
  {
    title: '使用模板关键词',
    body: '点「Agent」可查看电商常用模板；选择后仅复制到剪贴板，不会自动填入输入框。',
  },
  {
    title: '自定义关键词',
    body: '可用「/」分隔多个关键词，例如：白底主图 / 柔光 / 无文字。',
  },
  {
    title: '选择数量并生成',
    body: '在底部设置比例、模型与数量（最多 4 张），点击蓝色按钮开始生成。通常约需 1 分钟。',
  },
  {
    title: '注意事项',
    body: '提示词需合规，避免违规内容，否则可能判定失败（violation）。参考图可上传或粘贴，建议单张不超过 8MB。',
  },
]

function safeParse(raw, fallback) {
  if (!raw) return { ...fallback }
  try {
    const data = JSON.parse(raw)
    return data && typeof data === 'object' ? { ...fallback, ...data } : { ...fallback }
  } catch {
    return { ...fallback }
  }
}

export function loadAiImageSettings() {
  if (typeof localStorage === 'undefined') return { ...DEFAULT_AI_IMAGE_SETTINGS }
  const loaded = safeParse(localStorage.getItem(SETTINGS_KEY), DEFAULT_AI_IMAGE_SETTINGS)
  let dirty = false
  // 旧 GRSAI / 旧模型迁移到 hyhacct 可用模型，并写回本地，避免下次仍发 gpt-image-2
  if (loaded.model === 'gpt-image-2' || loaded.provider === 'grsai') {
    loaded.model = 'gpt-image-2-max'
    loaded.provider = 'hyhacct'
    if (!loaded.configName || String(loaded.configName).includes('GRSAI')) {
      loaded.configName = '默认 hyhacct 配置'
    }
    dirty = true
  }
  if (dirty && typeof localStorage !== 'undefined') {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(loaded))
  }
  return loaded
}

export function saveAiImageSettings( partial = {}) {
  const next = {
    ...loadAiImageSettings(),
    ...partial,
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(next))
  }
  return next
}

export function resolveAiImageApiKey(settings = loadAiImageSettings()) {
  const fromSettings = String(settings.apiKey || '').trim()
  if (fromSettings) return fromSettings
  return String(import.meta.env.VITE_GPT_IMAGE_API_KEY || '').trim()
}

export function loadAiImageStats() {
  const empty = { success: 0, failed: 0, images: 0, lastAt: 0 }
  if (typeof localStorage === 'undefined') return empty
  return safeParse(localStorage.getItem(STATS_KEY), empty)
}

export function recordAiImageSuccess(imageCount = 1) {
  const cur = loadAiImageStats()
  const next = {
    success: Number(cur.success || 0) + 1,
    failed: Number(cur.failed || 0),
    images: Number(cur.images || 0) + Math.max(0, Number(imageCount) || 0),
    lastAt: Date.now(),
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STATS_KEY, JSON.stringify(next))
  }
  return next
}

export function recordAiImageFailure() {
  const cur = loadAiImageStats()
  const next = {
    success: Number(cur.success || 0),
    failed: Number(cur.failed || 0) + 1,
    images: Number(cur.images || 0),
    lastAt: Date.now(),
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STATS_KEY, JSON.stringify(next))
  }
  return next
}

export function resetAiImageStats() {
  const empty = { success: 0, failed: 0, images: 0, lastAt: 0 }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STATS_KEY, JSON.stringify(empty))
  }
  return empty
}

export function hasSeenAiImageGuide() {
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(GUIDE_SEEN_KEY) === '1'
}

export function markAiImageGuideSeen() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(GUIDE_SEEN_KEY, '1')
  }
}
