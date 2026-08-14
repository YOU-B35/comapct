import assert from 'node:assert/strict'
import { FULL_SYNC_STEP_IDS, runDouyinFullSync } from './douyinFullSync.js'

assert.deepEqual(FULL_SYNC_STEP_IDS, [
  'compass',
  'compass_product_rank',
  'opportunity',
  'products',
  'orders',
  'issues',
])

const calls = []
const runners = Object.fromEntries(
  FULL_SYNC_STEP_IDS.map((id) => [
    id,
    async () => {
      calls.push(id)
      if (id === 'opportunity') return { ok: false, error: 'boom' }
      return { ok: true, message: id }
    },
  ]),
)
const out = await runDouyinFullSync({ storeId: null, force: true }, runners)
assert.equal(out.partial, true)
assert.deepEqual(calls, FULL_SYNC_STEP_IDS) // 失败后仍继续后续步骤
assert.equal(out.results.filter((r) => !r.ok).map((r) => r.id).join(), 'opportunity')
