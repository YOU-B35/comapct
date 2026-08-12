import assert from 'node:assert/strict'
import { test } from 'node:test'

// Dynamic import after we implement; for TDD, import will fail until file exists.
import {
  HELPER_PROTOCOL_START,
  connectLocalHelper,
} from '../src/utils/agentConnect.js'

test('HELPER_PROTOCOL_START is fixed scheme', () => {
  assert.equal(HELPER_PROTOCOL_START, 'crosshub-sync-helper://start')
})

test('already_running when probe true before trigger', async () => {
  let triggered = 0
  const result = await connectLocalHelper({
    probe: async () => true,
    trigger: () => { triggered += 1 },
    openPanel: () => {},
    timeoutMs: 1000,
    pollMs: 50,
  })
  assert.equal(result.status, 'already_running')
  assert.match(result.message, /已在运行/)
  assert.equal(triggered, 0)
})

test('started when probe becomes true after trigger', async () => {
  let n = 0
  const result = await connectLocalHelper({
    probe: async () => {
      n += 1
      return n >= 3
    },
    trigger: () => {},
    openPanel: () => {},
    sleep: async () => {},
    timeoutMs: 5000,
    pollMs: 1,
  })
  assert.equal(result.status, 'started')
  assert.match(result.message, /已启动/)
})

test('not_found when probe never true', async () => {
  const result = await connectLocalHelper({
    probe: async () => false,
    trigger: () => {},
    openPanel: () => {},
    sleep: async () => {},
    timeoutMs: 30,
    pollMs: 5,
  })
  assert.equal(result.status, 'not_found')
  assert.match(result.message, /请先下载安装/)
})
