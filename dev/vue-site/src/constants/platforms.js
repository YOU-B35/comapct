/** 平台分类：跨境平台 / 国内电商 / 独立站 */

export const DTC_PLATFORM_KEY = 'dtc'

/** 店铺绑定层仍区分 Shopify / WordPress */
export const DTC_STORE_PLATFORMS = ['shopify', 'wordpress']

export const DTC_PLATFORMS = DTC_STORE_PLATFORMS

export const MARKETPLACE_PLATFORMS = ['temu', 'aliexpress', '1688', 'amazon', 'walmart']

export const DOMESTIC_PLATFORMS = ['pdd', 'taobao', 'douyin', 'channels']

export const PROCUREMENT_PLATFORMS = ['1688']

/** 运营绑定 / 任务等平台维度：统一为「独立站」 */
export const DTC_PLATFORM_OPTIONS = [
  { value: DTC_PLATFORM_KEY, label: '独立站' },
]

export const DTC_STORE_TYPE_OPTIONS = [
  { value: 'shopify', label: 'Shopify' },
  { value: 'wordpress', label: 'WordPress' },
]

export const MARKETPLACE_PLATFORM_OPTIONS = [
  { value: 'temu', label: 'Temu' },
  { value: 'aliexpress', label: 'AliExpress' },
  { value: '1688', label: '1688' },
  { value: 'amazon', label: 'Amazon' },
  { value: 'walmart', label: 'Walmart' },
]

export const DOMESTIC_PLATFORM_OPTIONS = [
  { value: 'pdd', label: '拼多多' },
  { value: 'taobao', label: '淘宝' },
  { value: 'douyin', label: '抖音' },
  { value: 'channels', label: '视频号' },
]

export const OTHER_PLATFORM_OPTIONS = [
  { value: 'tiktok', label: 'TikTok Shop' },
]

export const PLATFORM_OPTION_GROUPS = [
  { label: '跨境平台', options: MARKETPLACE_PLATFORM_OPTIONS },
  { label: '国内电商', options: DOMESTIC_PLATFORM_OPTIONS },
  { label: '独立站', options: DTC_PLATFORM_OPTIONS },
  { label: '其他平台', options: OTHER_PLATFORM_OPTIONS },
]

const DTC_STORE_LABELS = {
  shopify: 'Shopify',
  wordpress: 'WordPress',
}

const DOMESTIC_PLATFORM_LABELS = {
  pdd: '拼多多',
  taobao: '淘宝',
  douyin: '抖音',
  channels: '视频号',
}

export function isDtcPlatform(platform) {
  const key = String(platform || '').trim().toLowerCase()
  return key === DTC_PLATFORM_KEY || DTC_STORE_PLATFORMS.includes(key)
}

export function isDtcStorePlatform(platform) {
  return DTC_STORE_PLATFORMS.includes(String(platform || '').trim().toLowerCase())
}

export function isDomesticPlatform(platform) {
  return DOMESTIC_PLATFORMS.includes(String(platform || '').trim().toLowerCase())
}

export function dtcPlatformLabel(platform) {
  if (isDtcPlatform(platform)) return '独立站'
  const key = String(platform || '').trim().toLowerCase()
  return DTC_STORE_LABELS[key] || platform
}

export function domesticPlatformLabel(platform) {
  const key = String(platform || '').trim().toLowerCase()
  return DOMESTIC_PLATFORM_LABELS[key] || platform
}

/** 运营绑定表单：shopify/wordpress 合并显示为 dtc */
export function collapsePlatformsForForm(platforms = []) {
  const result = []
  let hasDtc = false
  for (const platform of platforms) {
    if (isDtcPlatform(platform)) {
      hasDtc = true
    } else if (platform) {
      result.push(platform)
    }
  }
  if (hasDtc) result.push(DTC_PLATFORM_KEY)
  return [...new Set(result)]
}

/** 店铺筛选：选中独立站时包含 Shopify / WordPress 店铺 */
export function storeMatchesPlatforms(storePlatform, selectedPlatforms = []) {
  const platform = String(storePlatform || '').trim().toLowerCase()
  const selected = new Set((selectedPlatforms || []).map((item) => String(item).toLowerCase()))
  if (selected.has(platform)) return true
  if (selected.has(DTC_PLATFORM_KEY) && isDtcStorePlatform(platform)) return true
  return false
}

/** 列表展示：多个独立站子平台合并为一个「独立站」 */
export function platformDisplayLabels(platforms = [], labelMap = {}) {
  const labels = []
  let dtcShown = false
  for (const platform of platforms) {
    if (isDtcPlatform(platform)) {
      if (!dtcShown) {
        labels.push('独立站')
        dtcShown = true
      }
      continue
    }
    labels.push(labelMap[platform] || platform)
  }
  return labels
}
