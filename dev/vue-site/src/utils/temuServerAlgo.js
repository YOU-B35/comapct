import { productKeyFromRow } from '@/utils/mapReptileSaleToTemuProduct'
import { buildSlowMovingFromRow, isSlowCandidateRow } from '@/utils/temuSlowAlgo'

function round1(n) {
  return Math.round(n * 10) / 10
}

export function buildServerRestock(product, inv) {
  const coverDays = Number(inv.cover_days ?? inv.coverDays ?? 0)
  const suggestedRestock = Number(inv.replenish_qty ?? inv.replenishQty ?? 0)
  const warningDays = Number(inv.warning_days ?? inv.warningDays ?? 10)

  let urgency = 'normal'
  let urgencyLabel = '正常'
  if (suggestedRestock > 0) {
    if (coverDays <= warningDays) {
      urgency = 'critical'
      urgencyLabel = '紧急补货'
    } else {
      urgency = 'warning'
      urgencyLabel = '建议补货'
    }
  }

  return {
    ...product.restock,
    avg7DayDaily: product.avg7DayDaily,
    dailyDemand: round1(inv.daily_sales_adj ?? inv.dailySalesAdjusted ?? product.restock?.dailyDemand ?? 0),
    targetStock: Math.ceil(Number(inv.target_stock ?? inv.targetStock ?? 0)),
    suggestedRestock,
    coverDays: round1(coverDays),
    safetyStock: Math.ceil(warningDays),
    stockGap: product.officialStock - Math.ceil(warningDays),
    urgency,
    urgencyLabel,
    isHot: product.isHot,
    canFulfill: false,
    shortfall: suggestedRestock,
    fromServer: true,
  }
}

/**
 * 将 Commander 预警结果合并到已 enrich 的产品列表
 */
export function applyServerAlgorithms(products, { loseProducts = [], lowWarnings = [], inventoryWarnings = [], overloadProducts = [] } = {}) {
  const loseSet = new Set(loseProducts.map(productKeyFromRow).filter(Boolean))
  const overloadSet = new Set(overloadProducts.map(productKeyFromRow).filter(Boolean))

  const lowMap = new Map()
  for (const row of lowWarnings) {
    const key = productKeyFromRow(row)
    if (key && isSlowCandidateRow(row)) lowMap.set(key, row)
  }

  const invMap = new Map()
  for (const row of inventoryWarnings) {
    const key = productKeyFromRow(row)
    if (key) invMap.set(key, row)
  }

  return products.map((product) => {
    let next = { ...product }

    if (loseSet.size) {
      next.isLoss = loseSet.has(product.sku) && Number(next.costPrice) > 0
    }

    const lowRow = lowMap.get(product.sku)
    if (lowRow) {
      const slow = buildSlowMovingFromRow(lowRow)
      if (slow) {
        next.slowMoving = slow
        next.daysWithoutSale = slow.daysWithoutSale
      }
    }

    const invRow = invMap.get(product.sku)
    if (invRow) {
      next.restock = buildServerRestock(product, invRow)
    }

    if (overloadSet.has(product.sku)) {
      next.isOverload = true
    }

    return next
  })
}
