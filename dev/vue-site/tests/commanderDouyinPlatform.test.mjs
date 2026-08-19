import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const storeSrc = readFileSync(join(root, 'src/modules/commander/stores/autoUpload.js'), 'utf8')

assert.match(storeSrc, /value:\s*'douyin'/)
assert.match(storeSrc, /label:\s*'抖店'/)
assert.match(storeSrc, /value:\s*'temu'/)
assert.match(storeSrc, /value:\s*'aliexpress'/)
assert.match(storeSrc, /value:\s*'ozon'/)

console.log('commanderDouyinPlatform.test.mjs ok')
