import assert from 'node:assert/strict'
import { collectImageFilesFromClipboard } from '../src/modules/ai-image/pasteImages.js'

const fakePng = { name: 'a.png', type: 'image/png' }
const clipboard = {
  items: [
    { kind: 'string', type: 'text/plain', getAsFile: () => null },
    { kind: 'file', type: 'image/png', getAsFile: () => fakePng },
  ],
  files: [],
}

const got = collectImageFilesFromClipboard(clipboard)
assert.equal(got.length, 1)
assert.equal(got[0].name, 'a.png')

const empty = collectImageFilesFromClipboard({ items: [], files: [] })
assert.equal(empty.length, 0)

console.log('ai-image paste collect ok')
