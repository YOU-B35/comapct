import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(here, '../src/api/temuCompetitorsApi.js'), 'utf8')

assert.match(source, /service\.get\('\/api\/monitor\/targets'/)
assert.match(source, /service\.post\(`\/api\/monitor\/targets\/\$\{id\}\/trigger`/)
assert.match(source, /service\.get\(`\/api\/monitor\/targets\/\$\{id\}\/latest`/)
assert.match(source, /service\.get\(`\/api\/monitor\/targets\/\$\{id\}\/history`/)
assert.match(source, /force: !!crawlOpts\.force/)
assert.match(source, /bypass_cooldown: Boolean\(normalized\.bypassCooldown \|\| crawlOpts\.force\)/)
assert.match(source, /force: false/)
assert.doesNotMatch(source, /if \(latest\.has_fresh_data\) continue/)
assert.match(source, /MONITOR_TARGET_URL_INVALID/)
assert.match(source, /isTemuMallUrl/)
assert.match(source, /validTargets/)
assert.match(source, /skippedInvalidUrlCount/)
// Monitor trigger must not use FE platform 3h localStorage cooldown gate
assert.doesNotMatch(source, /assertPlatformCrawlAllowed/)
assert.match(source, /normalizeCrawlOptions\(normalized\)/)

console.log('temu_competitors_api_routes_ok')
