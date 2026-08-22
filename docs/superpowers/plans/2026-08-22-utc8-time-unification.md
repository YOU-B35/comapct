# 全链路统一 UTC+8 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 CrossHub 全链路（Java API、Python、前端展示、历史数据）时间口径统一为 UTC+8（Asia/Shanghai）。

**Architecture:** 服务器容器/JVM 时区改为 Asia/Shanghai，使所有 `LocalDateTime.now()` 新数据自动为北京时间；前端新增无依赖的 `formatUtc8` 统一展示入口；历史数据通过白名单迁移脚本把“系统时钟字段”+8 小时，平台来源时间保持原样。

**Tech Stack:** Spring Boot 17 / Java、Vue 3 + Vite、Python 3、SQLite、PowerShell 启动脚本。

## Global Constraints

- API 返回的时间字符串格式保持不变：`yyyy-MM-dd HH:mm:ss`，语义统一为 Asia/Shanghai 墙钟。
- 无时区字符串一律视为 UTC+8；带 `Z`/偏移的 ISO 时间或毫秒/秒时间戳展示前换算成 UTC+8。
- 迁移只动“系统时钟字段”白名单；平台/业务时间字段（`ordered_at`、`violated_at`、`published_at`、`report_time` 等）一律不碰。
- 不引入 dayjs/moment 等新依赖；前端时间工具必须是纯函数、无依赖。
- 不迁移浏览器 localStorage 旧演示数据（可用 `scripts/clear-demo-data.ps1` 重置）。
- 本仓库 `.gitignore` 忽略 `docs/`，新增文档用 `git add -f` 提交。

---

### Task 1: 后端与部署时区统一为 Asia/Shanghai

**Files:**
- Modify: `deploy/Dockerfile.java`
- Modify: `deploy/docker-compose.yml`
- Modify: `scripts/run-java-api.ps1`
- Modify: `scripts/restart-java-api.ps1`
- Modify: `scripts/restart-java-vue.ps1`
- Modify: `scripts/start-local.ps1`

**Interfaces:**
- Produces: 生产容器与本地 JVM 默认时区均为 Asia/Shanghai；`LocalDateTime.now()` / `LocalDate.now()` 结果即北京时间。

- [ ] **Step 1: 修改 `deploy/Dockerfile.java`**

在 `EXPOSE 18080` 前增加时区环境变量，并给启动命令加 JVM 参数：

```dockerfile
ENV TZ=Asia/Shanghai

EXPOSE 18080
ENTRYPOINT ["java", "-Duser.timezone=Asia/Shanghai", "-jar", "/app/app.jar", "--server.port=18080"]
```

- [ ] **Step 2: 修改 `deploy/docker-compose.yml`**

在 `crosshub-java` 与 `crosshub-python-worker` 的 `environment:` 块各增加一行：

```yaml
      TZ: Asia/Shanghai
```

- [ ] **Step 3: 修改本地启动脚本（4 个文件）**

在每次执行 `mvn` 之前设置 `JAVA_TOOL_OPTIONS`：

`scripts/run-java-api.ps1`：
```powershell
$env:JAVA_TOOL_OPTIONS = '-Duser.timezone=Asia/Shanghai'
mvn spring-boot:run
```

`scripts/restart-java-api.ps1`：在 `Write-Host "==> compile Java API"` 之前增加：
```powershell
$env:JAVA_TOOL_OPTIONS = '-Duser.timezone=Asia/Shanghai'
```
并把 launcher `ScriptLines` 中的 `"mvn -q -DskipTests spring-boot:run"` 上一行增加：
```powershell
    "`$env:JAVA_TOOL_OPTIONS='-Duser.timezone=Asia/Shanghai'"
```

`scripts/restart-java-vue.ps1`：同样在 compile 前增加 `$env:JAVA_TOOL_OPTIONS = '-Duser.timezone=Asia/Shanghai'`，并在 launcher `ScriptLines` 的 `"mvn -q spring-boot:run"` 上一行增加相同的 `JAVA_TOOL_OPTIONS` 行。

`scripts/start-local.ps1`：在 launcher `ScriptLines` 的 `"mvn -q spring-boot:run"` 上一行增加：
```powershell
    "`$env:JAVA_TOOL_OPTIONS='-Duser.timezone=Asia/Shanghai'"
```

- [ ] **Step 4: 验证**

运行：`cd backend/java; mvn -q test -DskipITs`
预期：BUILD SUCCESS，无新增失败用例（现有测试不依赖默认时区）。

运行：`python -c "import yaml; yaml.safe_load(open('deploy/docker-compose.yml', encoding='utf-8'))"`
预期：无异常（如本机无 PyYAML，则用 `docker compose -f deploy/docker-compose.yml config -q` 替代）。

- [ ] **Step 5: Commit**

```bash
git add deploy/Dockerfile.java deploy/docker-compose.yml scripts/run-java-api.ps1 scripts/restart-java-api.ps1 scripts/restart-java-vue.ps1 scripts/start-local.ps1
git commit -m "chore(time): default JVM/container timezone to Asia/Shanghai"
```

---

### Task 2: 前端统一时间工具 time.js（TDD）

**Files:**
- Create: `dev/vue-site/src/utils/time.js`
- Create: `dev/vue-site/src/utils/time.test.mjs`
- Modify: `dev/vue-site/package.json`

**Interfaces:**
- Produces:
  - `toUtc8Date(value): Date | null`
  - `formatUtc8(value, { seconds = true } = {}): string`（无法解析时：空值返回 `'—'`，非空但非法返回原字符串）
  - `nowUtc8String(): string`（`YYYY-MM-DD HH:mm:ss`）
  - `nowUtc8DateString(): string`（`YYYY-MM-DD`）

- [ ] **Step 1: 写失败测试**

创建 `dev/vue-site/src/utils/time.test.mjs`：

```js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatUtc8, nowUtc8DateString, nowUtc8String, toUtc8Date } from './time.js'

test('naive string is treated as Asia/Shanghai wall clock', () => {
  assert.equal(formatUtc8('2026-08-22 09:00:00'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22T09:00:00'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22 09:00', { seconds: false }), '2026-08-22 09:00')
})

test('ISO with Z is converted to UTC+8', () => {
  assert.equal(formatUtc8('2026-08-22T01:00:00Z'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22T01:00:00+00:00'), '2026-08-22 09:00:00')
  assert.equal(formatUtc8('2026-08-22T09:00:00+08:00'), '2026-08-22 09:00:00')
})

test('epoch ms and seconds are converted to UTC+8', () => {
  const ms = Date.UTC(2026, 7, 22, 1, 0, 0)
  assert.equal(formatUtc8(ms), '2026-08-22 09:00:00')
  assert.equal(formatUtc8(Math.floor(ms / 1000)), '2026-08-22 09:00:00')
})

test('invalid input falls back gracefully', () => {
  assert.equal(formatUtc8(null), '—')
  assert.equal(formatUtc8(''), '—')
  assert.equal(formatUtc8('not-a-time'), 'not-a-time')
  assert.equal(toUtc8Date('not-a-time'), null)
})

test('now helpers produce UTC+8 wall clock', () => {
  const s = nowUtc8String()
  const d = nowUtc8DateString()
  assert.match(s, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
  assert.match(d, /^\d{4}-\d{2}-\d{2}$/)
  const shifted = new Date(toUtc8Date(s).getTime() + 8 * 3600 * 1000)
  assert.equal(shifted.toISOString().slice(0, 19).replace('T', ' '), s)
})
```

- [ ] **Step 2: 运行测试确认失败**

运行：`cd dev/vue-site; node --test src/utils/time.test.mjs`
预期：FAIL，`Cannot find module './time.js'`。

- [ ] **Step 3: 实现 `dev/vue-site/src/utils/time.js`**

```js
/** 全项目时间口径：Asia/Shanghai（UTC+8），无时区字符串一律视为北京时间 */
export const SHANGHAI_OFFSET_MS = 8 * 60 * 60 * 1000

function pad(n) {
  return String(n).padStart(2, '0')
}

export function toUtc8Date(value) {
  if (value == null || value === '') return null
  if (typeof value === 'number') {
    const ms = Math.abs(value) < 1e12 ? value * 1000 : value
    return Number.isFinite(ms) ? new Date(ms) : null
  }
  const s = String(value).trim()
  if (!s) return null
  if (/^\d+$/.test(s)) {
    const n = Number(s)
    const ms = n < 1e12 ? n * 1000 : n
    return Number.isFinite(ms) ? new Date(ms) : null
  }
  if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) {
    const d = new Date(s)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return null
  const [, y, mo, d, h, mi, se = '0'] = m
  const utcMs = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(se))
  return new Date(utcMs - SHANGHAI_OFFSET_MS)
}

export function formatUtc8(value, { seconds = true } = {}) {
  const d = toUtc8Date(value)
  if (!d) return value == null || value === '' ? '—' : String(value)
  const shifted = new Date(d.getTime() + SHANGHAI_OFFSET_MS)
  const base = `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} ${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}`
  return seconds ? `${base}:${pad(shifted.getUTCSeconds())}` : base
}

export function nowUtc8String() {
  return formatUtc8(new Date())
}

export function nowUtc8DateString() {
  return formatUtc8(new Date(), { seconds: false }).slice(0, 10)
}
```

- [ ] **Step 4: 修改 `dev/vue-site/package.json`**

在 `scripts` 中增加：

```json
"test:time": "node --test src/utils/time.test.mjs"
```

- [ ] **Step 5: 运行测试确认通过**

运行：`npm run test:time`
预期：全部 test PASS。

- [ ] **Step 6: 验证前端可构建**

运行：`npm run build`
预期：vite build 成功。

- [ ] **Step 7: Commit**

```bash
git add dev/vue-site/src/utils/time.js dev/vue-site/src/utils/time.test.mjs dev/vue-site/package.json
git commit -m "feat(time): add shared UTC+8 time formatter for frontend"
```

---

### Task 3: 前端组件/视图时间展示统一走 formatUtc8

**Files:** 以下文件均新增一行 import：
`import { formatUtc8 } from '@/utils/time'`

Modify（模板表达式替换，`→` 前为原文、后为改文）：

| 文件 | 替换 |
| --- | --- |
| `views/warehouse/WarehouseOrdersView.vue:323` | `{{ row.lastUrgedAt.slice(5, 16) }}` → `{{ formatUtc8(row.lastUrgedAt).slice(5, 16) }}` |
| `views/boss/AgentNodesView.vue:68` | `{{ integration.last_heartbeat_at }}` → `{{ formatUtc8(integration.last_heartbeat_at) }}` |
| `components/common/PanelHeader.vue:29` | `{{ syncedPrefix }} {{ syncedAt }}` → `{{ syncedPrefix }} {{ formatUtc8(syncedAt) }}` |
| `components/common/PlatformSyncLogPanel.vue:97,102` | `{{ syncStore.lastFinishedAt }}` → `{{ formatUtc8(syncStore.lastFinishedAt) }}` |
| `components/amazon/AmazonCouponsPanel.vue:82` | `{{ row.startAt }} ~ {{ row.endAt }}` → `{{ formatUtc8(row.startAt) }} ~ {{ formatUtc8(row.endAt) }}` |
| `components/amazon/AmazonSellerNewsPanel.vue:64` | `{{ item.publishedAt }}` → `{{ formatUtc8(item.publishedAt) }}` |
| `components/amazon/AmazonPanelHeader.vue:49` | `{{ syncedAt }}` → `{{ formatUtc8(syncedAt) }}` |
| `components/tasks/AssignedTaskDetailDrawer.vue:93-94` | `{{ task.assignedAt || '—' }}` → `{{ formatUtc8(task.assignedAt) }}`；`{{ task.updatedAt || '—' }}` → `{{ formatUtc8(task.updatedAt) }}` |
| `components/warehouse/WarehouseOrderDetailDrawer.vue:41,126,141,152` | `{{ order.submittedAt }}` → `{{ formatUtc8(order.submittedAt) }}`；`{{ order.warehouseReview.estimatedShipAt }}` → `{{ formatUtc8(order.warehouseReview.estimatedShipAt) }}`；`{{ order.warehouseReview.reviewedAt }}` → `{{ formatUtc8(order.warehouseReview.reviewedAt) }}`；`{{ order.warehouseReview.releasedAt }}` → `{{ formatUtc8(order.warehouseReview.releasedAt) }}` |
| `components/aliexpress/AliExpressPanelHeader.vue:29` | `{{ syncedAt }}` → `{{ formatUtc8(syncedAt) }}` |
| `components/aliexpress/AliExpressViolationsPanel.vue:204` | `{{ row.confirmedAt }}` → `{{ formatUtc8(row.confirmedAt) }}` |
| `components/alibaba1688/Alibaba1688MonitorPanel.vue:330` | `{{ latest.latest_snapshot_at }}` → `{{ formatUtc8(latest.latest_snapshot_at) }}` |
| `components/alibaba1688/Alibaba1688OrderDetailsPanel.vue:174` | `{{ row.refundedAt || '—' }}` → `{{ formatUtc8(row.refundedAt) }}` |
| `components/alibaba1688/Alibaba1688ProductPanel.vue:52` | `{{ syncState.syncedAt }}` → `{{ formatUtc8(syncState.syncedAt) }}` |
| `components/dashboard/DailyOpsReportPanel.vue:36,161` | `{{ report.syncedAt }}` → `{{ formatUtc8(report.syncedAt) }}`；`{{ item.submittedAt }}` → `{{ formatUtc8(item.submittedAt) }}` |
| `components/dashboard/OperationsIssuesPanel.vue:300` | `{{ overview.syncedAt }}` → `{{ formatUtc8(overview.syncedAt) }}` |
| `components/domestic/DomesticIssuesPanel.vue:127` | `{{ syncedAt }}` → `{{ formatUtc8(syncedAt) }}` |
| `components/domestic/DomesticOrdersPanel.vue:77` | `{{ syncedAt }}` → `{{ formatUtc8(syncedAt) }}` |
| `components/temu/CompetitorAnalysis.vue:651` | `{{ row.lastAnalyzedAt }}` → `{{ formatUtc8(row.lastAnalyzedAt) }}` |
| `components/douyin/DouyinSyncLogDrawer.vue:156,159,191` | `{{ run.startedAt }}` → `{{ formatUtc8(run.startedAt) }}`；`{{ run.finishedAt }}` → `{{ formatUtc8(run.finishedAt) }}`；`{{ step.updatedAt }}` → `{{ formatUtc8(step.updatedAt) }}` |
| `views/douyin/DouyinModuleView.vue:1351,1572,1797,2026,2120` | `{{ compassSyncedAt }}` → `{{ formatUtc8(compassSyncedAt) }}`；`{{ rankSyncedAt }}` → `{{ formatUtc8(rankSyncedAt) }}`；`{{ opportunitySyncedAt }}` → `{{ formatUtc8(opportunitySyncedAt) }}`；`{{ productsSyncedAt }}` → `{{ formatUtc8(productsSyncedAt) }}`；`{{ row.publishedAt || '—' }}` → `{{ formatUtc8(row.publishedAt) }}` |
| `components/helper/HelperStatusBar.vue:753` | `（至 {{ bindInfo.expires_at }} UTC）` → `（至 {{ formatUtc8(bindInfo.expires_at) }}）` |
| `components/temu/TemuAgentPanel.vue:149` | 同上（`bindInfo.expires_at`，去掉 UTC 字样） |
| `components/temu/TemuHelperBanner.vue:281` | 同上 |
| `components/temu/TemuHelperStatusBar.vue:599` | 同上 |

`dev/vue-site/src/utils/syncHistory.js`：`formatSyncClock` 函数体改为委托统一工具（保持返回 `''` 的旧语义）：

```js
import { formatUtc8 } from './time.js'

export function formatSyncClock(isoLike) {
  const s = formatUtc8(isoLike, { seconds: false })
  return s === '—' ? '' : s
}
```

**Interfaces:**
- Consumes: `formatUtc8(value, options)`（Task 2）
- Produces: 所有列出的页面时间统一按 UTC+8 显示。

- [ ] **Step 1: 按上表逐文件替换并新增 import**

- [ ] **Step 2: 验证构建**

运行：`cd dev/vue-site; npm run build`
预期：构建成功；`rg -n "expires_at.*UTC" src` 无结果。

- [ ] **Step 3: Commit**

```bash
git add dev/vue-site/src
git commit -m "feat(time): render all page times via UTC+8 formatter"
```

---

### Task 4: 局部格式化函数与 demo/local 数据改 UTC+8

**Files:**
- Modify: `dev/vue-site/src/modules/sau/views/ContentWorks.vue`
- Modify: `dev/vue-site/src/modules/sau/views/MaterialManagement.vue`
- Modify: `dev/vue-site/src/modules/sau/views/PublishCenter.vue`
- Modify: `dev/vue-site/src/modules/commander/views/AutoUploadView.vue`
- Modify: `dev/vue-site/src/modules/ai-image/components/AiImageSettingsDialog.vue`
- Modify: `dev/vue-site/src/stores/platformSync.js`
- Modify: `dev/vue-site/src/api/alibaba1688.js`, `aliexpressOrdersLocal.js`, `aliexpressViolationsLocal.js`, `amazonBossLocal.js`, `amazonDailyLocal.js`, `assignedTasks.js`, `assignedTasksLocal.js`, `authLocal.js`, `domesticPlatformLocal.js`, `dtcOrdersLocal.js`, `employeesLocal.js`, `opsFeedbackLocal.js`, `platformAccountsLocal.js`, `platformShipRequests.js`, `platformShipRequestsLocal.js`, `temuCompetitorsLocal.js`, `walmartListingsLocal.js`, `walmartOrdersLocal.js`, `warehouseOrdersLocal.js`, `warehouseSitesLocal.js`, `warehouseStaffLocal.js`
- Modify: `dev/vue-site/src/constants/temuCompetitors.js`
- Modify: `dev/vue-site/src/utils/dailyOpsReport.js`, `amazon.js`, `employeeTasks.js`, `operationsOverview.js`, `warehouseOrders.js`

**Interfaces:**
- Consumes: `formatUtc8`、`nowUtc8String`、`nowUtc8DateString`（Task 2）

- [ ] **Step 1: 局部格式化函数改为委托**

`modules/sau/views/ContentWorks.vue`（约 403-406 行）：
```js
const formatTime = (value) => {
  if (!value) return '-'
  return formatUtc8(value)
}
```
文件顶部新增 `import { formatUtc8 } from '@/utils/time'`。

`modules/commander/views/AutoUploadView.vue`（142-158 行 `formatTaskTime` 整体替换）：
```js
function formatTaskTime(row) {
  const raw = row?.createAt ?? row?.createTime ?? row?.updateTime ?? row?.created_at
  return raw == null || raw === '' ? '—' : formatUtc8(raw)
}
```
文件顶部新增 `import { formatUtc8 } from '@/utils/time'`。

`modules/ai-image/components/AiImageSettingsDialog.vue`（90-96 行）：
```js
function formatTime(ts) {
  return ts ? formatUtc8(ts, { seconds: false }) : '—'
}
```
文件顶部新增 `import { formatUtc8 } from '@/utils/time'`。

`stores/platformSync.js`：232、248、270 行
`new Date().toLocaleString('zh-CN', { hour12: false })` → `nowUtc8String()`，并新增 `import { nowUtc8String } from '@/utils/time'`。

- [ ] **Step 2: 模板渲染替换**

`modules/sau/views/MaterialManagement.vue:141`：`{{ currentMaterial.upload_time }}` → `{{ formatUtc8(currentMaterial.upload_time) }}`（新增 import）。

`modules/sau/views/PublishCenter.vue:219`：`{{ material.upload_time }}` → `{{ formatUtc8(material.upload_time) }}`（新增 import）。

- [ ] **Step 3: demo/local 数据生成改 UTC+8**

以下每个文件顶部新增：
```js
import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
```

替换规则：
- `new Date().toISOString().replace('T', ' ').slice(0, 19)` → `nowUtc8String()`
- `new Date().toISOString().slice(0, 19).replace('T', ' ')` → `nowUtc8String()`
- `new Date().toISOString().slice(0, 10)` → `nowUtc8DateString()`
- `new Date().toISOString().replace('T', ' ').slice(0, 16)` → `nowUtc8String().slice(0, 16)`

逐文件清单（行号供核对）：

| 文件 | 行 | 说明 |
| --- | --- | --- |
| `api/alibaba1688.js` | 24, 56, 67 | `syncedAt` |
| `api/aliexpressOrdersLocal.js` | 13, 17 | 日期 + 时间 |
| `api/aliexpressViolationsLocal.js` | 21, 43, 128 | 时间 + 2×日期 |
| `api/amazonBossLocal.js` | 9, 13 | 时间 + 日期 |
| `api/amazonDailyLocal.js` | 35 | 时间 |
| `api/assignedTasks.js` | 198, 208 | `lastFeedbackAt` |
| `api/assignedTasksLocal.js` | 12 | 时间 |
| `api/authLocal.js` | 74 | `createdAt` |
| `api/domesticPlatformLocal.js` | 5, 9 | 日期 + 时间 |
| `api/dtcOrdersLocal.js` | 7 | 日期 |
| `api/employeesLocal.js` | 86 | `boundAt` |
| `api/opsFeedbackLocal.js` | 8, 12 | 日期 + 时间 |
| `api/platformAccountsLocal.js` | 237 | `boundAt` |
| `api/platformShipRequests.js` | 91 | `shipPushedAt` |
| `api/platformShipRequestsLocal.js` | 20 | 时间 |
| `api/temuCompetitorsLocal.js` | 40, 68, 109 | `now` |
| `api/walmartListingsLocal.js` | 9 | 时间 |
| `api/walmartOrdersLocal.js` | 9, 13 | 日期 + 时间 |
| `api/warehouseOrdersLocal.js` | 24, 72 | 时间 + `nowUtc8DateString().replace(/-/g, '')` |
| `api/warehouseSitesLocal.js` | 62 | 时间 |
| `api/warehouseStaffLocal.js` | 63 | 时间 |
| `constants/temuCompetitors.js` | 243 | `now`（原 `now.toISOString()...`） |
| `utils/dailyOpsReport.js` | 106 | 日期 |
| `utils/amazon.js` | 70 | 日期 |
| `utils/employeeTasks.js` | 84 | `updatedAt`（无秒，用 `nowUtc8String().slice(0, 16)`） |
| `utils/operationsOverview.js` | 21, 755 | 日期 + `syncedAt` |
| `utils/warehouseOrders.js` | 39, 49 | `uploadedAt` |

注意：`constants/temuCompetitors.js:243` 为三元表达式中的分支，替换后整体为：
```js
      ? nowUtc8String()
```

- [ ] **Step 4: 验证**

运行：`cd dev/vue-site; npm run build`
预期：构建成功。

运行：`rg -n "toISOString\(\).*replace\('T', ' '\)|toISOString\(\)\.slice\(0, (10|19)\)" src`
预期：无匹配（或仅剩明确用于计算而非展示的合法用例，需人工确认）。

- [ ] **Step 5: Commit**

```bash
git add dev/vue-site/src
git commit -m "feat(time): demo/local data and remaining formatters use UTC+8"
```

---

### Task 5: Python 服务器侧时间显式 Asia/Shanghai

**Files:**
- Modify: `backend/python/app/competitor_ingest.py`
- Modify: `backend/python/app/monitor_worker_service.py`
- Modify: `backend/python/app/ingest_alibaba1688.py`
- Modify: `backend/python/app/crawler/aliexpress_mapper.py`

**Interfaces:**
- Produces: 服务器侧 Python 写入 DB 的时间字符串为 UTC+8。

- [ ] **Step 1: 各文件增加时区导入与常量**

在 `competitor_ingest.py` 顶部 import 区新增：
```python
from zoneinfo import ZoneInfo
```
并在模块级新增：
```python
SHANGHAI = ZoneInfo("Asia/Shanghai")
```

同法修改 `monitor_worker_service.py`、`ingest_alibaba1688.py`、`crawler/aliexpress_mapper.py`（如已有 `from datetime import datetime` 则保留）。

- [ ] **Step 2: 替换 `datetime.now()`**

- `competitor_ingest.py:74,129`：`datetime.now().strftime(...)` → `datetime.now(SHANGHAI).strftime(...)`
- `monitor_worker_service.py:716`：同上
- `ingest_alibaba1688.py:12`：同上
- `crawler/aliexpress_mapper.py:30`：同上

- [ ] **Step 3: 验证**

运行：
```bash
python -m py_compile backend/python/app/competitor_ingest.py backend/python/app/monitor_worker_service.py backend/python/app/ingest_alibaba1688.py backend/python/app/crawler/aliexpress_mapper.py
python -c "from zoneinfo import ZoneInfo; from datetime import datetime; assert datetime.now(ZoneInfo('Asia/Shanghai')).utcoffset().total_seconds() == 8*3600; print('OK')"
```
预期：两命令均无异常，输出 OK。

- [ ] **Step 4: Commit**

```bash
git add backend/python/app/competitor_ingest.py backend/python/app/monitor_worker_service.py backend/python/app/ingest_alibaba1688.py backend/python/app/crawler/aliexpress_mapper.py
git commit -m "fix(time): python server-side timestamps use Asia/Shanghai"
```

---

### Task 6: 历史数据迁移脚本（dry-run + 备份 + 白名单）

**Files:**
- Create: `scripts/migrate_db_utc_to_shanghai.py`
- Create: `scripts/test_migrate_db_utc_to_shanghai.py`

**Interfaces:**
- Produces: `main(argv)`：`--db PATH`（必填）、`--dry-run`（只统计不写库）、`--backup-dir PATH`（默认备份到 DB 同目录）。

- [ ] **Step 1: 写失败测试**

创建 `scripts/test_migrate_db_utc_to_shanghai.py`：

```python
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from migrate_db_utc_to_shanghai import migrate


class MigrateTest(unittest.TestCase):
    def _db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE agent_task (
              id TEXT PRIMARY KEY,
              created_at TEXT,
              started_at TEXT,
              finished_at TEXT
            );
            CREATE TABLE douyin_order (
              id TEXT PRIMARY KEY,
              ordered_at TEXT,
              created_at TEXT
            );
            CREATE TABLE mix (
              id TEXT PRIMARY KEY,
              updated_at TEXT,
              expires_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO agent_task VALUES ('a', '2026-08-22 01:01:15', '2026-08-22 01:04:51', '2026-08-22 01:06:03')"
        )
        conn.execute("INSERT INTO douyin_order VALUES ('o', '2026-08-13 23:49:21', '2026-08-14 17:33:31')")
        conn.execute("INSERT INTO mix VALUES ('m', '2026-08-22 01:00:00', '2026-08-22T01:00:00Z')")
        conn.commit()
        conn.close()
        return path

    def test_clock_columns_shift_plus_8(self):
        path = self._db()
        conn = sqlite3.connect(path)
        migrate(conn, dry_run=False)
        conn.commit()
        row = conn.execute("SELECT created_at, started_at, finished_at FROM agent_task WHERE id='a'").fetchone()
        self.assertEqual(row, ("2026-08-22 09:01:15", "2026-08-22 09:04:51", "2026-08-22 09:06:03"))
        conn.close()
        os.remove(path)

    def test_platform_and_iso_columns_untouched(self):
        path = self._db()
        conn = sqlite3.connect(path)
        migrate(conn, dry_run=False)
        conn.commit()
        row = conn.execute("SELECT ordered_at, created_at FROM douyin_order WHERE id='o'").fetchone()
        self.assertEqual(row, ("2026-08-13 23:49:21", "2026-08-14 17:33:31"))
        row = conn.execute("SELECT updated_at, expires_at FROM mix WHERE id='m'").fetchone()
        self.assertEqual(row, ("2026-08-22 09:00:00", "2026-08-22T01:00:00Z"))
        conn.close()
        os.remove(path)

    def test_dry_run_does_not_write(self):
        path = self._db()
        conn = sqlite3.connect(path)
        migrate(conn, dry_run=True)
        row = conn.execute("SELECT created_at FROM agent_task WHERE id='a'").fetchone()
        self.assertEqual(row, ("2026-08-22 01:01:15",))
        conn.close()
        os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

运行：`python scripts/test_migrate_db_utc_to_shanghai.py`
预期：FAIL，`ModuleNotFoundError: No module named 'migrate_db_utc_to_shanghai'`。

- [ ] **Step 3: 实现 `scripts/migrate_db_utc_to_shanghai.py`**

```python
#!/usr/bin/env python3
"""Migrate server-clock naive UTC timestamps to Asia/Shanghai (+8 hours).

Usage:
  python scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db --dry-run
  python scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db

Only whitelisted "system clock" columns are touched. Platform/business time
columns and any ISO-with-offset values are never modified.
"""

import argparse
import datetime as _dt
import os
import re
import shutil
import sqlite3
import sys

# Columns set by the server clock (Java LocalDateTime.now() / Python datetime.now()).
CLOCK_COLUMNS = {
    "created_at", "updated_at", "started_at", "finished_at", "queued_at",
    "last_heartbeat_at", "bound_at", "last_success_at", "next_retry_at",
    "last_run_at", "next_run_at", "submitted_at", "assigned_at",
    "last_feedback_at", "nudged_at", "joined_at", "read_at",
    "last_analyzed_at", "latest_snapshot_at", "snapshot_at", "synced_at",
}

# Platform/business content times: never migrate, even if the name looks like a clock column.
PLATFORM_COLUMNS = {
    "ordered_at", "paid_at", "refunded_at", "created_platform_at",
    "updated_platform_at", "violated_at", "published_at", "listed_at",
    "join_site_time", "report_time", "data_report_time", "feedback_date",
    "date_window", "snapshot_date", "broadcast_at", "expected_ship_at",
    "expected_arrival_at", "actual_ship_at", "start_at", "end_at",
    "expires_at",
}

NAIVE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?$")


def _table_columns(conn):
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    return {
        t: [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
        for t in tables
    }


def migrate(conn, dry_run=False):
    """Return (table, column, affected_rows) tuples for changed columns."""
    changed = []
    for table, columns in _table_columns(conn).items():
        for col in columns:
            if col not in CLOCK_COLUMNS or col in PLATFORM_COLUMNS:
                continue
            like = (
                f"SELECT COUNT(*) FROM \"{table}\" "
                f"WHERE (\"{col}\" LIKE '____-__-__ __:__%' "
                f"OR \"{col}\" LIKE '____-__-__T__:__%') "
                f"AND \"{col}\" NOT LIKE '%Z' "
                f"AND \"{col}\" NOT LIKE '%+%'"
            )
            count = conn.execute(like).fetchone()[0]
            if not count:
                continue
            if dry_run:
                sample = conn.execute(
                    f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT 1'
                ).fetchone()
                print(f"[dry-run] {table}.{col}: {count} row(s), sample={sample[0] if sample else ''}")
            else:
                cur = conn.execute(
                    f'UPDATE "{table}" SET "{col}" = '
                    f"datetime(\"{col}\", '+8 hours') "
                    f'WHERE (("{col}" LIKE \'____-__-__ __:__%\' '
                    f"OR \"{col}\" LIKE '____-__-__T__:__%') "
                    f"AND \"{col}\" NOT LIKE '%Z' "
                    f"AND \"{col}\" NOT LIKE '%+%')"
                )
                print(f"[apply] {table}.{col}: {cur.rowcount} row(s)")
            changed.append((table, col, count))
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Only report, do not write")
    parser.add_argument("--backup-dir", help="Directory for timestamped backup (default: DB directory)")
    args = parser.parse_args(argv)

    if not args.dry_run:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{args.db}.bak-{stamp}"
        if args.backup_dir:
            os.makedirs(args.backup_dir, exist_ok=True)
            backup = os.path.join(args.backup_dir, os.path.basename(backup))
        shutil.copy2(args.db, backup)
        print(f"[backup] {args.db} -> {backup}")

    conn = sqlite3.connect(args.db)
    try:
        migrate(conn, dry_run=args.dry_run)
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试确认通过**

运行：`python scripts/test_migrate_db_utc_to_shanghai.py`
预期：`OK`（3 个测试全部通过）。

- [ ] **Step 5: 本地 dry-run 自检**

运行：
```bash
python scripts/migrate_db_utc_to_shanghai.py --db backend/data/crosshub.db --dry-run
```
预期：无异常（本地如无该 DB 会报错属正常，以 Step 4 单元测试为准）。

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_db_utc_to_shanghai.py scripts/test_migrate_db_utc_to_shanghai.py
git commit -m "feat(time): add dry-run DB migration for UTC to UTC+8 clock columns"
```

---

### Task 7: 生产上线执行清单（人工操作）

**Files:** 无代码改动。

- [ ] **Step 1: 构建并备份**

```bash
cd backend/java && mvn -q -DskipTests package
cd ../../dev/vue-site && npm run build
```

- [ ] **Step 2: 部署新容器（含 TZ）**

按现有 `scripts/deploy-server.ps1` / `deploy-server.js` 流程部署（`docker compose up -d --force-recreate`，期间有已知 502 空窗）。

- [ ] **Step 3: 迁移前 dry-run 与备份**

```bash
python3 scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db --dry-run
python3 scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db --backup-dir /data/crosshub/backups
```

- [ ] **Step 4: 验证**

- 抽查：`SELECT last_heartbeat_at FROM integration_agent ORDER BY last_heartbeat_at DESC LIMIT 1` 应与服务器当前北京时间接近（±1 分钟）。
- 浏览器登录 www.yoto.work/crosshub，检查任务时间、同步时间、心跳时间与本地北京时间一致。
- `mvn test`、前端构建在 Step 1 已通过。

- [ ] **Step 5: 回滚预案（如需）**

- 恢复旧 jar：`docker compose -f /data/crosshub/docker-compose.yml up -d --force-recreate crosshub-java` 前还原 `/data/crosshub/app.jar`；
- 恢复数据库：用 `--backup-dir` 生成的 `.bak-*` 文件覆盖 `crosshub.db` 并重启容器；
- 前端回滚：还原 `/opt/1panel/www/sites/www.yoto.work/index/crosshub` 上一版静态文件。
