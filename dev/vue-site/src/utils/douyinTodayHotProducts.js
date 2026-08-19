/**
 * 抖音「今日爆款」：近 24h 有效订单汇总，quantity ≥ minQty。
 * 优先按 productId 聚合/匹配商品库；无 ID 时回退店+品名。
 */

const MS_24H = 24 * 60 * 60 * 1000

export function isExcludedOrderStatus(status) {
  const s = String(status || '')
  return s.includes('关闭') || s.includes('取消')
}

function parseOrderTime(order) {
  const raw = order?.orderedAt || order?.ordered_at || order?.createdAt || order?.created_at || ''
  if (!raw) return null
  const normalized = String(raw).trim().replace(' ', 'T')
  const d = new Date(normalized)
  if (!Number.isNaN(d.getTime())) return d
  const d2 = new Date(String(raw).replace(/-/g, '/'))
  return Number.isNaN(d2.getTime()) ? null : d2
}

function qtyOf(order) {
  const n = Number(order?.quantity)
  return Number.isFinite(n) && n > 0 ? n : 1
}

function nameOf(row) {
  return String(row?.productName || row?.product_name || '').trim()
}

function storeOf(row) {
  return String(row?.storeId || row?.store_id || '')
}

function productIdOf(row) {
  const id = row?.productId ?? row?.product_id
  if (id == null || id === '') return ''
  return String(id).trim()
}

function aggregateKey(order) {
  const storeId = storeOf(order)
  const pid = productIdOf(order)
  if (pid) return { key: `${storeId}||id:${pid}`, storeId, productId: pid, productName: nameOf(order) }
  const name = nameOf(order)
  return { key: `${storeId}||name:${name}`, storeId, productId: '', productName: name }
}

/**
 * @param {unknown[]} orders
 * @param {unknown[]} products
 * @param {{ now?: Date|number|string, minQty?: number }} [opts]
 */
export function buildTodayHotProducts(orders = [], products = [], opts = {}) {
  const now = opts.now != null ? new Date(opts.now) : new Date()
  const minQty = opts.minQty != null ? Number(opts.minQty) : 10
  const cutoff = now.getTime() - MS_24H

  const totals = new Map()
  for (const order of Array.isArray(orders) ? orders : []) {
    if (isExcludedOrderStatus(order?.status)) continue
    const meta = aggregateKey(order)
    if (!meta.productId && !meta.productName) continue
    const t = parseOrderTime(order)
    if (!t || t.getTime() < cutoff || t.getTime() > now.getTime()) continue
    const prev = totals.get(meta.key) || {
      storeId: meta.storeId,
      productId: meta.productId || undefined,
      productName: meta.productName,
      todaySales: 0,
    }
    prev.todaySales += qtyOf(order)
    if (meta.productId) prev.productId = meta.productId
    if (meta.productName) prev.productName = meta.productName
    totals.set(meta.key, prev)
  }

  const byId = new Map()
  const byName = new Map()
  for (const p of Array.isArray(products) ? products : []) {
    const storeId = storeOf(p)
    const pid = productIdOf(p)
    const name = nameOf(p)
    if (pid) byId.set(`${storeId}||${pid}`, p)
    if (name) byName.set(`${storeId}||${name}`, p)
  }

  return [...totals.values()]
    .filter((row) => row.todaySales >= minQty)
    .sort((a, b) => b.todaySales - a.todaySales)
    .map((row) => {
      const hit =
        (row.productId && byId.get(`${row.storeId}||${row.productId}`))
        || byName.get(`${row.storeId}||${row.productName}`)
        || null
      if (!hit) {
        return {
          storeId: row.storeId,
          productId: row.productId,
          productName: row.productName,
          todaySales: row.todaySales,
        }
      }
      return {
        ...hit,
        storeId: row.storeId || hit.storeId,
        productId: row.productId || hit.productId,
        productName: hit.productName || row.productName,
        todaySales: row.todaySales,
      }
    })
}
