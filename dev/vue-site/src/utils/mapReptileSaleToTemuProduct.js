/** 分 → 元 */
import {
  estimateDaysWithoutSaleFromRow,
} from '@/utils/temuSlowAlgo'

export function centsToYuan(value) {
  const n = Number(value)
  if (Number.isNaN(n)) return 0
  return Math.round(n) / 100
}

/** Commander status → SaaS listingStatus */
export function statusToListing(status) {
  return String(status) === '400' ? 'offline' : 'online'
}

/**
 * Temu 入库的 son_sales_seven_days 是「近 7 日总销量」。
 * 拆成 7 天序列时必须保证 sum === total7（不可 Math.round(total/7) 再 ×7，否则小销量被抹成 0）。
 */
export function salesLast7DaysFromRow(row) {
  const total7 = Math.max(0, Math.floor(Number(row.son_sales_seven_days ?? row.sonSalesSevenDays ?? 0) || 0))
  const base = Math.floor(total7 / 7)
  const rem = total7 - base * 7
  return Array.from({ length: 7 }, (_, i) => base + (i < rem ? 1 : 0))
}

export function sales7TotalFromRow(row) {
  return Math.max(0, Math.floor(Number(row.son_sales_seven_days ?? row.sonSalesSevenDays ?? 0) || 0))
}

/**
 * 将 commander TableReptileSale 行映射为 enrichTemuProduct 输入结构
 * @param {Record<string, unknown>} row
 * @param {Record<string, unknown>} [overrides]
 */
export function mapReptileSaleToTemuProduct(row, overrides = {}) {
  const sku = String(row.ext_code ?? row.extCode ?? row.son_ext_code ?? '').trim()
  const sellingPrice = centsToYuan(row.son_price ?? row.sonPrice)
  const costPrice = centsToYuan(row.cost ?? 0)
  const sales7Total = sales7TotalFromRow(row)
  const localStockRaw = row.local_stock ?? row.localStock
  const localStock = localStockRaw == null || localStockRaw === ''
    ? null
    : Math.max(0, Math.floor(Number(localStockRaw) || 0))

  return {
    sku,
    storeId: String(row.shop_id ?? row.shopId ?? ''),
    name: String(row.title ?? sku),
    sellingPrice,
    costPrice,
    platformFeeRate: 0.15,
    logisticsFee: 0,
    officialStock: Number(row.warehouse_available_stock ?? row.warehouseAvailableStock ?? 0),
    localStock,
    daysWithoutSale: estimateDaysWithoutSaleFromRow(row),
    dailySales: Number(row.son_today_sales ?? row.sonTodaySales ?? 0),
    sales7Total,
    sales30Total: Math.max(0, Math.floor(Number(row.son_sales_thirty_days ?? row.sonSalesThirtyDays ?? 0) || 0)),
    salesLast7Days: salesLast7DaysFromRow(row),
    category: String(row.category_name ?? row.categoryName ?? ''),
    owner: String(row.nickname ?? row.username ?? overrides.owner ?? ''),
    listingStatus: statusToListing(row.status),
    spuId: String(row.spu ?? ''),
    skcId: String(row.skc ?? ''),
    skuId: String(row.son_sku ?? row.sonSku ?? ''),
    imgUrl: String(row.img_url ?? row.imgUrl ?? ''),
    joinSiteTime: Math.max(0, Math.floor(Number(row.join_site_time ?? row.joinSiteTime ?? 0) || 0)),
    ...overrides,
  }
}

export function productKeyFromRow(row) {
  return String(row.ext_code ?? row.extCode ?? row.son_ext_code ?? '').trim()
}
