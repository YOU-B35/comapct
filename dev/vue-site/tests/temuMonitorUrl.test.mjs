import assert from 'node:assert/strict'
import {
  isTemuMallUrl,
  isTemuProductUrl,
  temuMallUrlErrorMessage,
  temuMallUrlExample,
  temuMallUrlGuideLines,
} from '../src/utils/temuMonitorUrl.js'

assert.equal(
  isTemuMallUrl('https://www.temu.com/mall.html?mall_id=3678530852421'),
  true,
)
assert.equal(
  isTemuMallUrl('https://www.temu.com/jp-zh-Hans/mall.html?mall_id=1'),
  true,
)

assert.equal(
  isTemuProductUrl('https://www.temu.com/jp-zh-Hans/-fishing-g-601105684074765.html?x=1'),
  true,
)
assert.equal(
  isTemuMallUrl('https://www.temu.com/jp-zh-Hans/-fishing-g-601105684074765.html?x=1'),
  false,
)
assert.equal(
  isTemuMallUrl('https://www.temu.com/search_result.html?search_key=lead'),
  false,
)
assert.equal(isTemuMallUrl('https://example.com/mall.html?mall_id=1'), false)
assert.equal(isTemuMallUrl('not-a-url'), false)
assert.equal(isTemuMallUrl('https://www.temu.com/mall.html?mall_id='), false)

assert.match(temuMallUrlErrorMessage, /mall_id|店铺/)
assert.match(temuMallUrlExample, /mall_id=\d+/)
assert.ok(temuMallUrlGuideLines.length >= 3)

console.log('temu_monitor_url_ok')
