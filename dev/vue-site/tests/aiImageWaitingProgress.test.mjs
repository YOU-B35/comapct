import assert from 'node:assert/strict'
import { createWaitingProgress } from '../src/modules/ai-image/waitingProgress.js'

const samples = []
const stop = createWaitingProgress({
  onProgress: (p) => samples.push(p),
  from: 5,
  ceiling: 92,
  expectedMs: 1000,
  tickMs: 50,
})

await new Promise((r) => setTimeout(r, 280))
stop()

assert.equal(samples[0], 5, 'starts at from')
assert.ok(samples.length >= 3, `should tick multiple times, got ${samples.length}`)
assert.ok(samples.at(-1) > 5, `should advance past 5%, got ${samples.at(-1)}`)
assert.ok(samples.at(-1) <= 92, `should not exceed ceiling, got ${samples.at(-1)}`)
assert.ok(
  samples.every((v, i) => i === 0 || v >= samples[i - 1]),
  'progress should be non-decreasing',
)

console.log('ai-image waiting progress ok', samples.slice(0, 6), '→', samples.at(-1))
