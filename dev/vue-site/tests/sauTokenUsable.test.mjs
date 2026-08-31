import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { isSauTokenUsable } from '../src/modules/sau/utils/sauToken.js'

function makeJwt(expSeconds) {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')
  const payload = btoa(JSON.stringify({ exp: expSeconds }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')
  return `${header}.${payload}.x`
}

describe('isSauTokenUsable', () => {
  it('rejects empty token', () => {
    assert.equal(isSauTokenUsable(''), false)
    assert.equal(isSauTokenUsable(null), false)
  })

  it('treats opaque tokens as usable', () => {
    assert.equal(isSauTokenUsable('opaque-token-value'), true)
  })

  it('rejects expired jwt', () => {
    const token = makeJwt(Math.floor(Date.now() / 1000) - 120)
    assert.equal(isSauTokenUsable(token), false)
  })

  it('accepts fresh jwt', () => {
    const token = makeJwt(Math.floor(Date.now() / 1000) + 3600)
    assert.equal(isSauTokenUsable(token), true)
  })
})
