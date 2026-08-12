import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const requestSource = readFileSync(resolve(root, 'src/modules/commander/api/request.js'), 'utf8')
const agentSource = readFileSync(resolve(root, 'src/modules/commander/api/agent.js'), 'utf8')
const viewSource = readFileSync(resolve(root, 'src/modules/commander/views/AutoUploadView.vue'), 'utf8')

assert.match(requestSource, /getAccessToken as getCrosshubAccessToken/)
assert.match(requestSource, /from '@\/api\/request'/)
assert.doesNotMatch(requestSource, /LEGACY_TOKEN_KEY/)
assert.doesNotMatch(requestSource, /localStorage\.setItem\(\s*['"]accessToken['"]/)
assert.doesNotMatch(requestSource, /localStorage\.setItem\(\s*['"]commander_accessToken['"]/)
assert.match(requestSource, /localStorage\.removeItem\('commander_accessToken'\)/)
assert.match(agentSource, /\/api\/commander\/v1/)
assert.doesNotMatch(viewSource, /CommanderLoginPanel/)

console.log('commander_request_bff_auth_ok')
