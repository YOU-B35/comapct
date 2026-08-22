import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatUtc8, nowUtc8DateString, nowUtc8String, toUtc8Date } from './time.js'

test('naive string is treated as Asia/Shanghai wall clock', () => {
  assert.equal(formatUtc8('2026-08-22 09:00:00'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22T09:00:00'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22 09:00', { seconds: false }), '2026-08-22 09:00')
})

test('ISO with Z is converted to UTC+8', () => {
  assert.equal(formatUtc8('2026-08-22T01:00:00Z'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22T01:00:00+00:00'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22T09:00:00+08:00'), '2026-08-22 09:00:00')
})

test('epoch ms and seconds are converted to UTC+8', () => {
  const ms = Date.UTC(2026, 7, 22, 1, 0, 0)
  assert.equal(formatUtc8(ms), '2026-08-22 09:00:00')
  assert.equal(formatUtc8(Math.floor(ms / 1000)), '2026-08-22 09:00:00')
})

test('invalid input falls back gracefully', () => {
  assert.equal(formatUtc8(null), '—')
  assert.equal(formatUtc8(''), '—')
  assert.equal(formatUtc8('not-a-time'), 'not-a-time')
  assert.equal(toUtc8Date('not-a-time'), null)
})

test('now helpers produce UTC+8 wall clock', () => {
  const s = nowUtc8String()
  const d = nowUtc8DateString()
  assert.match(s, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
  assert.match(d, /^\d{4}-\d{2}-\d{2}$/)
  const shifted = new Date(toUtc8Date(s).getTime() + 8 * 3600 * 1000)
  assert.equal(shifted.toISOString().slice(0, 19).replace('T', ' '), s)
})
