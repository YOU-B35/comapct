/**
 * Temu ops口径对齐（无 Vite alias）：内联与 src 相同的公式做回归。
 * 正式路径仍以 src/utils/temu.js + Java TemuWarningServiceImpl 为准。
 */
import assert from 'node:assert/strict'

const HOT_SURGE = 1.5
const HOT_MIN = 1

function isHotProduct(dailySales, avg7DayDaily) {
  const today = Number(dailySales) || 0
  const avg = Number(avg7DayDaily) || 0
  if (today < HOT_MIN) return false
  if (avg <= 0) return today >= HOT_MIN
  return today / avg >= HOT_SURGE
}

function calcReplenishLikeJava(s7, s30, stock) {
  const d7 = s7 / 7
  const d30 = Math.max(s7, s30) / 30
  let trend = 1
  if (d30 > 0) trend = Math.max(0.8, Math.min(d7 / d30, 1.5))
  const dAdj = (d7 * 0.7 + d30 * 0.3) * trend
  const warningDays = 7 + 3
  if (dAdj <= 0) return { need: false, qty: 0 }
  const cover = stock / dAdj
  if (cover < warningDays) {
    const target = dAdj * 15
    return { need: true, qty: Math.max(0, Math.ceil(target - stock)), cover, warningDays }
  }
  return { need: false, qty: 0, cover, warningDays }
}

assert.equal(isHotProduct(15, 5), true)
assert.equal(isHotProduct(2, 10), false)
assert.equal(isHotProduct(3, 0), true)
assert.equal(isHotProduct(0, 0), false)

const plan = calcReplenishLikeJava(70, 300, 50)
assert.equal(plan.need, true)
assert.ok(plan.qty > 0)

console.log('temu_ops_alignment_ok')
