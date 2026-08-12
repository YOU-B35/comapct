import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const modPath = join(dirname(fileURLToPath(import.meta.url)), '../src/modules/commander/utils/agent.js')
const { agentIdOf, isAgentOnline, normalizeAgentList } = await import(`file://${modPath.replace(/\\/g, '/')}`)

assert.equal(agentIdOf({ uuid: 'abc', id: 'x' }), 'abc')
assert.equal(isAgentOnline({ status: true }), true)
assert.equal(isAgentOnline({ status: false }), false)
assert.equal(isAgentOnline({ status: 'online' }), true)
assert.equal(isAgentOnline({ status: 'offline' }), false)

const list = normalizeAgentList({
  data: [
    { uuid: 'u1', name: 'A', status: true },
    { uuid: 'u2', name: 'B', status: false },
  ],
})
assert.equal(list.length, 2)
assert.equal(list[0].id, 'u1')
assert.equal(list[0].online, true)
assert.equal(list[1].online, false)
assert.equal(list.filter((a) => a.online).length, 1)

console.log('commanderAgentOnline.test.mjs ok')
