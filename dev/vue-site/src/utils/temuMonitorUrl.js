/** Temu 竞店 monitor URL 校验：仅接受含非空 mall_id 的店铺链接，拒绝商品详情页。 */

export const temuMallUrlExample = 'https://www.temu.com/mall.html?mall_id=3678530852421'

export const temuMallUrlErrorMessage =
  '请填写 Temu 店铺链接（含 mall_id），商品详情页无法作为竞店抓取'

/** 竞店设置页展示的 URL 格式说明（与后端 TemuMonitorUrlValidator 一致） */
export const temuMallUrlGuideLines = [
  '必须是 Temu 店铺页链接，查询参数含非空 mall_id',
  `正确示例：${temuMallUrlExample}`,
  '不可用：商品详情页（URL 含 -g-数字.html）、搜索页、无 mall_id 的链接',
  '建议从上方「渔具 Top10 候选」选店铺，或在 Temu 店铺主页复制 mall 链接',
]

export function isTemuProductUrl(url) {
  try {
    const u = new URL(url)
    return /-g-\d+\.html$/i.test(u.pathname)
  } catch {
    return false
  }
}

export function isTemuMallUrl(url) {
  try {
    const u = new URL(url)
    if (!/(^|\.)temu\.com$/i.test(u.hostname)) return false
    if (isTemuProductUrl(url)) return false
    const mallId = u.searchParams.get('mall_id')
    return Boolean(mallId && mallId.trim())
  } catch {
    return false
  }
}
