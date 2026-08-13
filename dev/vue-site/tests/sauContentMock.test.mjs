import assert from 'node:assert/strict'
import { useContentMock } from '../src/modules/sau/api/content.js'

assert.equal(typeof useContentMock, 'function')
assert.equal(useContentMock(), false)
console.log('useContentMock ok')
