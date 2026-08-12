export const AI_IMAGE_MODELS = [
  { value: 'gpt-image-2-max', label: 'gpt-image-2-max' },
]

/**
 * UI 比例 → OpenAI size（hyhacct /v1/images/generations）
 */
export const AI_IMAGE_RATIOS = [
  { value: '1:1', label: '1:1', size: '1024x1024' },
  { value: '3:2', label: '3:2', size: '1536x1024' },
  { value: '2:3', label: '2:3', size: '1024x1536' },
  { value: '4:3', label: '4:3', size: '1536x1024' },
  { value: '3:4', label: '3:4', size: '1024x1536' },
  { value: '16:9', label: '16:9', size: '1536x1024' },
  { value: '9:16', label: '9:16', size: '1024x1536' },
]

export const AI_IMAGE_QUALITIES = [
  { value: 'high', label: 'high' },
  { value: 'medium', label: 'medium' },
  { value: 'low', label: 'low' },
]

export const AI_IMAGE_COLLECTIONS = [
  { value: 'all', label: '全部合集' },
  { value: 'favorites', label: '收藏' },
]

export const MAX_REFERENCE_IMAGES = 10

export function sizeFromRatio(ratio) {
  return AI_IMAGE_RATIOS.find((item) => item.value === ratio)?.size || '1024x1024'
}
