# 全链路统一 UTC+8（Asia/Shanghai）设计

- 日期：2026-08-22
- 状态：已确认（用户选择“全链路统一 UTC+8”，历史数据仅迁移系统时钟字段）
- 范围：CrossHub SaaS（前端 dev/vue-site、Java API backend/java、Python backend/python、部署 deploy/）

## 1. 背景与现状

当前项目时间口径混乱，线上表现为页面时间比北京时间慢 8 小时：

- 生产 Java 容器时区为 UTC（`date` 显示 `01:09 UTC`，宿主机为 `09:09 +0800`），代码大量使用 `LocalDateTime.now()` / `LocalDate.now()` 生成 `yyyy-MM-dd HH:mm:ss` 字符串写入 SQLite，例如 `integration_agent.last_heartbeat_at = '2026-08-22 01:09:37'`，实际是 UTC 墙钟。
- 前端拿到接口字符串后**原样渲染**，没有统一的时间换算工具；本地 demo 数据又用 `new Date().toISOString()`（UTC）生成，聊天类组件用浏览器本地时间，三种来源三种口径。
- 部分代码已显式使用 `Asia/Shanghai`（`@Scheduled(zone=...)`、Python 抖音模块 `datetime.now(SHANGHAI)`），与 UTC 混用，除显示偏差外，心跳过期判断、冷却、TTL 等基于字符串与 `LocalDateTime.now()` 比较的逻辑也可能偏差 8 小时。

## 2. 目标与统一口径

- **全链路统一口径：所有“无时区”时间字符串一律视为 Asia/Shanghai（UTC+8）墙钟**。
- 服务器（Java、服务器侧 Python）新写入的时间必须是北京时间；
- 前端展示统一按 UTC+8 输出；
- 历史数据中由服务器时钟生成的字段迁移 +8 小时，平台/业务来源时间保持原样；
- API 返回格式不变（仍为 `yyyy-MM-dd HH:mm:ss`），避免破坏现有解析。

## 3. 总体方案

### 3.1 后端与部署时区统一

1. `deploy/docker-compose.yml`：`crosshub-java`、`crosshub-python-worker` 增加环境变量 `TZ: Asia/Shanghai`。
2. `deploy/Dockerfile.java`：增加 `ENV TZ=Asia/Shanghai`，启动命令改为
   `["java", "-Duser.timezone=Asia/Shanghai", "-jar", "/app/app.jar", "--server.port=18080"]`。
3. 本地开发启动脚本统一注入 JVM 时区（保持本地与生产一致）：
   - `scripts/restart-java-api.ps1`、`scripts/restart-java-vue.ps1`、`scripts/run-java-api.ps1`、`scripts/start-local.ps1`
   - 方式：在 `mvn spring-boot:run` 前设置 `$env:JAVA_TOOL_OPTIONS = '-Duser.timezone=Asia/Shanghai'`（或在启动参数中传 `-Dspring-boot.run.jvmArguments`）。

效果：所有 `LocalDateTime.now()` / `LocalDate.now()` / `Instant` 相关逻辑在服务器上自动为北京时间，无需逐个修改数百处 Java 调用点。

### 3.2 前端统一时间工具

新增 `dev/vue-site/src/utils/time.js`（纯函数、无依赖）：

- `toUtc8Date(value)`
  - 数字或数字字符串：按毫秒时间戳解析（< 1e12 视为秒，自动乘 1000）；
  - 含 `Z` 或 `+08:00` 等时区后缀的 ISO 字符串：`new Date(value)` 解析；
  - 无时区 `YYYY-MM-DD[ T]HH:mm(:ss)`：按 Asia/Shanghai 墙钟解析（用 `Date.UTC(...) - 8h` 构造绝对时间）；
  - 其他输入返回 `null`。
- `formatUtc8(value, { seconds = true } = {})`
  - 将任意输入统一换算成 UTC+8 墙钟，输出 `YYYY-MM-DD HH:mm:ss`（或去掉秒）；
  - 无法解析时原样返回输入或 `—`（调用方按需）。
- `nowUtc8String()`：当前时间的 UTC+8 字符串，供 demo/localStorage 数据生成使用。

使用方式：所有模板中直接渲染时间字段的地方改为 `formatUtc8(...)`；已有的局部时间格式化函数（如 `SyncHistoryDrawer.formatSyncClock`、`AutoUploadView.formatTaskTime`、SAU `ContentWorks.formatTime`）改为内部委托给 `formatUtc8`。

改造范围（以实际代码清单为准，实施计划中逐项核对）：

- 公共组件：`PanelHeader.vue`、`PlatformSyncLogPanel.vue`、`SyncHistoryDrawer.vue`；
- 平台模块：Temu（`CompetitorAnalysis.lastAnalyzedAt`、Helper 状态栏 `expires_at` 并移除“UTC”字样）、AliExpress（面板头、`confirmedAt`）、Amazon（面板头、`publishedAt`、`startAt/endAt`、`syncedAt`）、1688（`syncedAt`、`latest_snapshot_at`、`refundedAt`）、抖音（`compassSyncedAt`、`rankSyncedAt`、`opportunitySyncedAt`、`productsSyncedAt`、`publishedAt`、同步日志 `startedAt/finishedAt/updatedAt`）；
- 任务/仓库/看板：`AssignedTaskDetailDrawer`、`WarehouseOrderDetailDrawer`、`WarehouseOrdersView.lastUrgedAt`、`OperationsIssuesPanel`、`DailyOpsReportPanel`、`DomesticIssuesPanel`、`DomesticOrdersPanel`、`AgentNodesView.last_heartbeat_at`；
- SAU / Commander / AI：`ContentWorks`、`PublishCenter.upload_time`、`MaterialManagement`、`AutoUploadView`、`AiImageSettingsDialog.lastAt`；
- 本地 demo 数据生成（`*Local.js`、`warehouseOrders.js`、`platformSync.js` 等）统一改用 `nowUtc8String()`，替换 `new Date().toISOString().replace('T',' ')`。

### 3.3 Python 服务器侧

- 服务器侧写入时间的关键脚本显式使用 `Asia/Shanghai`（不依赖容器 TZ）：
  - `backend/python/app/competitor_ingest.py`
  - `backend/python/app/monitor_worker_service.py`
  - `backend/python/app/ingest_alibaba1688.py`
  - `backend/python/app/crawler/aliexpress_mapper.py`（按实际运行位置确认）
- 本地助手（Windows 位于 +8 时区）与抖音模块（已用 `Asia/Shanghai`）保持现状。

### 3.4 历史数据迁移（仅系统时钟字段）

新增 `scripts/migrate-db-utc-to-shanghai.py`（Python，可 `--dry-run`）：

1. **备份**：执行前用 SQLite backup API 生成 `/data/crosshub/data/crosshub.db.bak-YYYYMMDD-HHMMSS`。
2. **白名单规则**：仅迁移“系统时钟字段”（Java `LocalDateTime.now()` / `LocalDate.now()` / 服务器侧 Python `datetime.now()` 赋值的列）：
   `created_at, updated_at, started_at, finished_at, queued_at, last_heartbeat_at, bound_at, last_success_at, next_retry_at, last_run_at, next_run_at, submitted_at, assigned_at, last_feedback_at, nudged_at, joined_at, read_at, last_analyzed_at, latest_snapshot_at, snapshot_at, synced_at`（服务器写入的同步时间，如 douyin/amazon/1688 各表的 synced_at）。
3. **不迁移**（平台/业务内容时间）：`ordered_at, paid_at, refunded_at, created_platform_at, updated_platform_at, violated_at, published_at, listed_at, join_site_time, report_time, data_report_time, feedback_date, date_window, snapshot_date, broadcast_at, expected_ship_at, expected_arrival_at, actual_ship_at, start_at, end_at` 及任何 ISO 带时区/时间戳格式的值。
4. **安全约束**：
   - 只处理匹配 `^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$` 的字符串值；
   - `UPDATE ... SET col = datetime(col, '+8 hours') WHERE col LIKE '____-__-__ __:__:__'`（SQLite 内置 datetime 函数，非法值自动忽略）；
   - `--dry-run` 先输出每表每列影响行数与样例，人工确认后再执行。
5. **执行顺序**：先部署带 `TZ=Asia/Shanghai` 的新容器（新数据开始写 +8）→ 立即执行迁移（旧数据 +8）→ 验证，避免迁移后再次写入 UTC 数据。

### 3.5 验证

- Java：`mvn test` 全量通过（确认无依赖默认时区的断言）。
- 前端：新增 `dev/vue-site/src/utils/time.test.mjs`（node:test）覆盖：
  - 无时区字符串按 +8 解析；
  - ISO `Z` 转换为 +8；
  - 毫秒/秒时间戳；
  - 非法输入回退；
  - `npm run build` 通过；`node --test src/utils/time.test.mjs` 通过。
- 生产：迁移 dry-run 行数合理 → 备份 → 执行 → 抽查 `integration_agent.last_heartbeat_at` ≈ 当前北京时间；登录后检查任务/同步/心跳页面时间正确。

## 4. 不做的事（明确排除）

- 不改变 API 字符串格式（保持 `yyyy-MM-dd HH:mm:ss`）；
- 不迁移平台/业务内容时间字段；
- 不迁移浏览器 localStorage 中的旧 demo 数据（属演示数据，可执行 `scripts/clear-demo-data.ps1` 重置）；
- 不引入 dayjs/moment 等新依赖。

## 5. 风险与回滚

- 迁移风险：白名单列判断错误会把正确时间加错。缓解：dry-run 行数+样例核对、迁移前备份、迁移后抽查。
- 部署风险：`--force-recreate` 会带来 502 空窗（已知问题），按常规发布窗口执行；保留旧 `app.jar` 与 DB 备份可回滚。
- 抖音等本地助手数据：其 `synced_at/created_at/updated_at` 实际由 Java 在接收时用服务器时钟覆写（代码 `String now = now();`），迁移后与服务器口径一致。
- SAU/Commander 等外部系统时间：无时区字符串按 +8 显示（保持墙钟不变），带时区字符串统一转 +8，均为预期行为。

## 6. 涉及文件清单（实施计划细化）

- 部署：`deploy/docker-compose.yml`、`deploy/Dockerfile.java`
- 本地脚本：`scripts/restart-java-api.ps1`、`scripts/restart-java-vue.ps1`、`scripts/run-java-api.ps1`、`scripts/start-local.ps1`
- 前端：新增 `dev/vue-site/src/utils/time.js`、`dev/vue-site/src/utils/time.test.mjs`；改造 3.2 节列出的视图/组件/demo 数据文件；`dev/vue-site/package.json` 增加 `test:time` 脚本（可选）
- Python：`backend/python/app/competitor_ingest.py`、`backend/python/app/monitor_worker_service.py`、`backend/python/app/ingest_alibaba1688.py` 等
- 迁移：新增 `scripts/migrate-db-utc-to-shanghai.py`

## 7. 实施顺序

1. 后端时区（Dockerfile/compose/本地脚本）→ Java 测试；
2. 前端 time.js + 测试 + 页面改造 → build 验证；
3. Python 服务器侧显式时区；
4. 迁移脚本（dry-run）→ 生产部署新容器 → 备份并执行迁移 → 验证 → 收尾检查。
