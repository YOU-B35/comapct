import { describe, expect, it } from 'vitest'
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
    expect(isSauTokenUsable('')).toBe(false)
    expect(isSauTokenUsable(null)).toBe(false)
  })

  it('treats opaque tokens as usable', () => {
    expect(isSauTokenUsable('opaque-token-value')).toBe(true)
  })

  it('rejects expired jwt', () => {
    const token = makeJwt(Math.floor(Date.now() / 1000) - 120)
    expect(isSauTokenUsable(token)).toBe(false)
  })

  it('accepts fresh jwt', () => {
    const token = makeJwt(Math.floor(Date.now() / 1000) + 3600)
    expect(isSauTokenUsable(token)).toBe(true)
  })
})
