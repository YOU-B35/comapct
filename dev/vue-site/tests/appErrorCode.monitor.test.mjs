import assert from 'node:assert/strict'
import { resolveAppError } from '../src/utils/appErrorCode.js'

const sourceUnavailable = resolveAppError({
  errorCode: 'MONITOR_SOURCE_UNAVAILABLE',
  message: 'Temu snapshots require boards/ctf-website page-card evidence.',
})

assert.equal(sourceUnavailable.title, '缺少页面卡片证据')
assert.match(sourceUnavailable.summary, /页面卡片证据/)
assert.ok(sourceUnavailable.steps.some((step) => step.includes('raw_products.json')))

const invalidUrl = resolveAppError({
  errorCode: 'MONITOR_INVALID_URL',
  message: 'Temu provider requires a valid temu.com mall URL.',
})

assert.equal(invalidUrl.title, '竞店链接无效')
assert.match(invalidUrl.summary, /Temu 店铺链接/)

const targetUrlInvalid = resolveAppError({
  errorCode: 'MONITOR_TARGET_URL_INVALID',
  message: '请填写 Temu 店铺链接（含 mall_id），商品详情页无法作为竞店抓取',
})

assert.equal(targetUrlInvalid.title, '竞店链接格式不正确')
assert.match(targetUrlInvalid.summary, /mall_id|发现竞店/)
assert.ok(targetUrlInvalid.steps.some((step) => /mall\.html|发现渔具/.test(step)))

const legacyDisabled = resolveAppError({
  errorCode: 'MONITOR_LEGACY_ANALYZE_DISABLED',
  message: '旧竞店分析入口已停用，请使用 /api/monitor 任务链路',
})

assert.equal(legacyDisabled.title, '旧竞店分析入口已停用')
assert.match(legacyDisabled.summary, /\/api\/monitor/)

console.log('monitor_error_copy_ok')
