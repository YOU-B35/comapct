import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatSyncDuration,
  formatTriggerLabel,
  formatRecordCount,
  buildSyncSummaryText,
} from './syncHistory.js'

test('formatSyncDuration under one minute', () => {
  assert.equal(
    formatSyncDuration('2026-08-12 11:00:00', '2026-08-12 11:00:45'),
    '45秒',
  )
})

test('formatSyncDuration minutes and seconds', () => {
  assert.equal(
    formatSyncDuration('2026-08-12 11:00:00', '2026-08-12 11:01:23'),
    '1分23秒',
  )
})

test('formatSyncDuration missing end', () => {
  assert.equal(formatSyncDuration('2026-08-12 11:00:00', ''), '—')
})

test('formatTriggerLabel daily vs manual', () => {
  assert.equal(formatTriggerLabel({ trigger: 'daily_schedule' }), '定时')
  assert.equal(formatTriggerLabel({ triggered_by: 0 }), '定时')
  assert.equal(formatTriggerLabel({ triggered_by: 42 }), '手动')
})

test('formatRecordCount temu', () => {
  assert.equal(
    formatRecordCount({ rows_count: 128, shops_count: 2 }, 'temu'),
    '128 条 · 2 店',
  )
})

test('buildSyncSummaryText success', () => {
  const text = buildSyncSummaryText(
    {
      status: 'success',
      finished_at: '2026-08-12 11:42:10',
      started_at: '2026-08-12 11:40:47',
      rows_count: 128,
      shops_count: 1,
    },
    'temu',
  )
  assert.match(text, /最近同步/)
  assert.match(text, /128 条/)
  assert.match(text, /耗时/)
})

test('buildSyncSummaryText running', () => {
  assert.equal(
    buildSyncSummaryText({ status: 'running' }, 'temu'),
    '同步中…',
  )
})

test('buildSyncSummaryText failed', () => {
  const text = buildSyncSummaryText(
    {
      status: 'failed',
      finished_at: '2026-08-12 11:42:10',
      error_message: '助手离线',
    },
    'temu',
  )
  assert.match(text, /最近同步失败/)
  assert.match(text, /助手离线/)
})
