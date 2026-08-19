import test from 'node:test'
import assert from 'node:assert/strict'
import { BESTSELLER_TIERS, classifyBestsellerTier } from './alibaba1688Analytics.js'

test('bestseller tiers classify by 30d sales quantity', () => {
  assert.equal(classifyBestsellerTier(45), '爆款')
  assert.equal(classifyBestsellerTier(30), '爆款')
  assert.equal(classifyBestsellerTier(12), '潜力爆款')
  assert.equal(classifyBestsellerTier(10), '潜力爆款')
  assert.equal(classifyBestsellerTier(3), '一般')
  assert.equal(classifyBestsellerTier(1), '一般')
  assert.equal(classifyBestsellerTier(0), '无销量')
  assert.equal(classifyBestsellerTier(null), '无销量')
})

test('tier options cover all buckets', () => {
  const keys = BESTSELLER_TIERS.map((t) => t.key)
  assert.deepEqual(keys, ['', '爆款', '潜力爆款', '一般', '无销量'])
})
