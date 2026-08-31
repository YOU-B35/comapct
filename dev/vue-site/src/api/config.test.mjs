import assert from 'node:assert/strict'
import { isTemuBackendEnabled } from './config.js'

assert.equal(isTemuBackendEnabled(), true)
