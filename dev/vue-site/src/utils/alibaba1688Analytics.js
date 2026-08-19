/** 1688 商品数据分析列表的归类工具。 */

export const BESTSELLER_TIERS = [
  { key: '', label: '全部' },
  { key: '爆款', label: '爆款' },
  { key: '潜力爆款', label: '潜力爆款' },
  { key: '一般', label: '一般' },
  { key: '无销量', label: '无销量' },
]

export function classifyBestsellerTier(salesQty) {
  const qty = Number(salesQty) || 0
  if (qty >= 30) return '爆款'
  if (qty >= 10) return '潜力爆款'
  if (qty >= 1) return '一般'
  return '无销量'
}

export function formatAnalyticsAmount(value) {
  const n = Number(value) || 0
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
