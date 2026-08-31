import assert from 'node:assert/strict'

/**
 * SearchableTable 传入 () => props.data 时，旧实现 unref(fn) 得到函数本身，
 * Function.length===0 → 表格恒空。此处验证 getter 可解析为数组。
 */
function resolveSourceList(source) {
  const raw = typeof source === 'function' ? source() : source
  return Array.isArray(raw) ? raw : []
}

const rows = [{ label: '铅坠', url: 'https://www.temu.com/mall.html?mall_id=1' }]
assert.equal(resolveSourceList(() => rows).length, 1)
assert.equal(resolveSourceList(rows).length, 1)
assert.equal(resolveSourceList(() => null).length, 0)
// regression: treating getter as array used Function.length
assert.notEqual((() => rows).length, rows.length)

console.log('fuzzy_pagination_getter_ok')
