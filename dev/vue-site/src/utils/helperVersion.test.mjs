import test from 'node:test'
import assert from 'node:assert/strict'
import { isHelperOutdated, parseHelperVersion } from './helperVersion.js'

test('parse dotted version', () => {
  assert.deepEqual(parseHelperVersion('2026.08.19.1'), [2026, 8, 19, 1])
  assert.deepEqual(parseHelperVersion(''), [])
  assert.deepEqual(parseHelperVersion(null), [])
})

test('outdated when local empty or lower', () => {
  assert.equal(isHelperOutdated('', '2026.08.19.1'), true)
  assert.equal(isHelperOutdated('2026.08.19.0', '2026.08.19.1'), true)
  assert.equal(isHelperOutdated('2026.08.18.1', '2026.08.19.1'), true)
  assert.equal(isHelperOutdated('2026.08.19.1', '2026.08.19.1'), false)
  assert.equal(isHelperOutdated('2026.08.19.2', '2026.08.19.1'), false)
})

test('no latest info never blocks', () => {
  assert.equal(isHelperOutdated('', ''), false)
  assert.equal(isHelperOutdated('2026.08.19.1', ''), false)
})
