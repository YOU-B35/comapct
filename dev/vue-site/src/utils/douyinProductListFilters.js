/**
 * 抖音商品 Tab 筛选项：今日销售订单、新品销售。
 */
import { isExcludedOrderStatus } from './douyinTodayHotProducts.js'

const MS_DAY = 24 * 60 * 60 * 1000

export function parseDateTime(raw) {
  if (raw == null || raw === '') return null
  if (raw instanceof Date) return Number.isNaN(raw.getTime()) ? null : raw
  const s = String(raw).trim()
  if (!s) return null
  const d = new Date(s.replace(' ', 'T'))
  if (!Number.isNaN(d.getTime())) return d
  const d2 = new Date(s.replace(/-/g, '/'))
  return Number.isNaN(d2.getTime()) ? null : d2
}

function startOfLocalDay(date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

function endOfLocalDay(date) {
  const d = new Date(date)
  d.setHours(23, 59, 59, 999)
  return d
}

function orderTime(order) {
  return parseDateTime(order?.orderedAt || order?.ordered_at || order?.createdAt || order?.created_at)
}

function publishedTime(product) {
  return parseDateTime(
    product?.publishedAt || product?.published_at || product?.createTime || product?.createdAt,
  )
}

/**
 * 自然日「今天」的有效销售订单（排除关闭/取消）。
 * @param {unknown[]} orders
 * @param {{ now?: Date|number|string }} [opts]
 */
export function filterTodaySalesOrders(orders = [], opts = {}) {
  const now = opts.now != null ? new Date(opts.now) : new Date()
  const start = startOfLocalDay(now).getTime()
  const end = endOfLocalDay(now).getTime()
  return (Array.isArray(orders) ? orders : []).filter((order) => {
    if (isExcludedOrderStatus(order?.status)) return false
    const t = orderTime(order)
    if (!t) return false
    const ms = t.getTime()
    return ms >= start && ms <= end
  })
}

/**
 * 近 days 天内上架的商品（默认 3 天，含今天往前共 days 个自然日）。
 * @param {unknown[]} products
 * @param {{ now?: Date|number|string, days?: number }} [opts]
 */
export function filterNewListedProducts(products = [], opts = {}) {
  const now = opts.now != null ? new Date(opts.now) : new Date()
  const days = opts.days != null ? Number(opts.days) : 3
  const windowDays = Number.isFinite(days) && days > 0 ? days : 3
  const start = startOfLocalDay(new Date(now.getTime() - (windowDays - 1) * MS_DAY)).getTime()
  const end = endOfLocalDay(now).getTime()

  return (Array.isArray(products) ? products : [])
    .filter((p) => {
      const t = publishedTime(p)
      if (!t) return false
      const ms = t.getTime()
      return ms >= start && ms <= end
    })
    .slice()
    .sort((a, b) => {
      const ta = publishedTime(a)?.getTime() || 0
      const tb = publishedTime(b)?.getTime() || 0
      return tb - ta
    })
}
