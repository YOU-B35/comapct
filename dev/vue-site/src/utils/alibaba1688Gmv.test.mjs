import test from 'node:test'
import assert from 'node:assert/strict'
import {
  parse1688Money,
  summarize1688ProductGmv,
  filterItemsByStoreIds,
} from './alibaba1688.js'

test('parse1688Money parses plain and formatted amounts', () => {
  assert.equal(parse1688Money('1234.5'), 1234.5)
  assert.equal(parse1688Money('1,234.50'), 1234.5)
  assert.equal(parse1688Money('¥12'), 12)
  assert.equal(parse1688Money(''), 0)
  assert.equal(parse1688Money(null), 0)
})

test('summarize1688ProductGmv sums gmv1d and counts sold skus', () => {
  const s = summarize1688ProductGmv([
    { gmv1d: '10' },
    { gmv_1d: '20.5' },
    { gmv1d: '0' },
    { gmv1d: '' },
  ])
  assert.equal(s.totalGmv, 30.5)
  assert.equal(s.soldCount, 2)
  assert.equal(s.productCount, 4)
})

test('filterItemsByStoreIds keeps matches when any overlap', () => {
  const items = [{ storeId: 'a' }, { storeId: 'b' }]
  assert.deepEqual(
    filterItemsByStoreIds(items, ['b']).map((i) => i.storeId),
    ['b'],
  )
})

test('filterItemsByStoreIds falls back to all items when no overlap', () => {
  const items = [{ storeId: 'x' }]
  assert.deepEqual(filterItemsByStoreIds(items, ['y']), items)
})

test('filterItemsByStoreIds returns empty when source empty', () => {
  assert.deepEqual(filterItemsByStoreIds([], ['y']), [])
})
