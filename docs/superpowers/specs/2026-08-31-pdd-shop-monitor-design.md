# 拼多多（PDD）竞店监控模块 设计文档

> 日期：2026-08-31
> 状态：待用户评审
> 关联：通用竞店监控框架（`monitor_target` / `monitor_schedule` / `monitor_job` / `monitor_snapshot` / `monitor_product_snapshot` / `monitor_signal`）、1688 竞店监控（`alibaba1688_shop_collector.py` + `alibaba1688_monitor_adapter.py`）、PDD 数据同步链路（`pdd_tasks.py`）

## 1. 背景与目标

### 现状

- PDD 模块已有「竞店监控」页签（`PddMonitorPanel.vue`），前端界面完整：店铺管理、爆款榜、趋势图、告警信号。
- 通用竞店框架已跑通 1688 / Temu；PDD 目前是半成品，链路断点如下：
  - Java `MonitorAgentTaskEnqueuer` 对所有平台硬编码创建 `1688_monitor_crawl` 任务，PDD 店铺会被 1688 适配器抓取，必然失败；
  - Python 端没有 PDD 竞店适配器/采集器，`monitor_worker.py` 未注册 `pdd`；
  - Java URL 校验只覆盖 1688 / Temu，PDD 链接直接放行；
  - 助手端没有 `pdd_monitor_crawl` 任务处理与 PDD 竞店 ingest 回写端点。
- 另有半成品「同行爆款」（`pdd_peer_bestseller`）不在本次范围内，且已于 8 月 28 日从 UI 移除。

### 目标（本次迭代）

1. PDD 竞店抓取链路端到端跑通：前端 → Java 任务派发 → 助手 PDD 适配器（买家端真实抓取）→ 入库 → 前端展示。
2. 结构完全对齐 1688 竞店：采集器 + 适配器 + URL 校验 + 按平台派发 + ingest 回写 + worker 注册。
3. 新增买家登录通道：前端工具栏「买家登录」按钮 + 登录状态；验证码/风控时弹有头窗口人工过验证。
4. 保留现有 monitor 表结构与信号分析逻辑，不回归 1688 / Temu。

### 不做（本次）

- 恢复/补全「同行爆款」（`pdd_peer_bestseller`）功能。
- AI 大模型专向分析（快照 `raw_json` 留存，为后续 AI 分析预留数据地基）。
- 竞店精确订单数据（公开接口不存在，只做累计销量差值估算）。
- 商家后台竞品数据（只抓买家端公开信息）。

## 2. 抓取数据源

- 拼多多买家端（`mobile.yangkeduo.com` / `yangkeduo.com`）：
  - 店铺主页：`mall_page.html?mall_id=...`
  - 商品详情：`goods.html?goods_id=...&mall_id=...`（采集时反查店铺）
- 公开字段：商品标题、价格、「已拼 X 件」累计销量、图片、商品链接、店铺名、店铺内排名。
- 拼多多买家端没有免登录公开接口：采集器使用租户级买家浏览器 profile，打开店铺页后捕获商品列表 XHR 并带 cookie 回放、分页拉取（复用 `pdd_tasks.py` 的 XHR 捕获/回放机制，域名从商家后台换到买家端）。
- 验证码/风控：切有头窗口弹登录界面，用户手动完成验证后继续（Temu 模式）。

## 3. 架构与组件

整体沿用 1688 竞店五层结构：前端面板、Java 任务调度与 ingest、助手任务处理、采集器 + 适配器、monitor worker。

### 3.1 Python（助手端）

| 文件 | 动作 | 职责 |
|---|---|---|
| `app/platforms/pdd_shop_collector.py` | 新增 | 链接解析（mall_id / goods_id）、买家 profile 启动与登录等待、店铺商品列表 XHR 捕获与回放、分页取 Top N + pinned 商品、商品字段解析、「已拼 X 件」数值换算、验证码/风控检测 |
| `app/platforms/pdd_monitor_adapter.py` | 新增 | 实现 `MonitorPlatformAdapter.crawl_target`，调用采集器并映射为 monitor 产品字段，错误码规范化 |
| `agent/handlers.py` | 修改 | 新增 `handle_pdd_monitor_crawl`、`handle_pdd_buyer_login_open`（及可选 buyer session probe），注册到 `dispatch_task`，任务类型纳入浏览器占用集合 |
| `agent/java_client.py` | 修改 | 新增 `ingest_pdd_monitor`、买家登录/会话相关调用 |
| `monitor_worker.py` | 修改 | adapters 注册表增加 `"pdd"` |

### 3.2 Java（后端）

| 文件 | 动作 | 职责 |
|---|---|---|
| `monitor/util/PddMonitorUrlValidator.java` | 新增 | 校验店铺主页（mall_id 非空）与商品详情链接（goods_id 非空），规范化 URL |
| `monitor/service/impl/MonitorServiceImpl.java` | 修改 | URL 校验按平台分发增加 pdd 分支 |
| `monitor/service/impl/MonitorAgentTaskEnqueuer.java` | 修改 | 按平台选择任务类型与提示文案：1688 → `1688_monitor_crawl`，pdd → `pdd_monitor_crawl` |
| `pdd/service/PddAgentTasks.java` | 修改 | 新增 `MONITOR_CRAWL`、`BUYER_LOGIN_OPEN`、`BUYER_SESSION_PROBE`，纳入 `BROWSER_BUSY_TYPES` |
| `pdd/controller/PddController.java` | 修改 | `POST /api/pdd/monitor/buyer-login`、`GET /api/pdd/monitor/buyer-session` |
| `pdd/controller/PddAgentController.java` | 修改 | `POST /api/agent/pdd/monitor/ingest` 复用 `MonitorIngestService.ingestSnapshot` 落库；买家会话快照回写（复用 `pdd_session_snapshot`，store_id=`buyer`） |

### 3.3 前端

| 文件 | 动作 | 职责 |
|---|---|---|
| `components/pdd/PddMonitorPanel.vue` | 修改 | 工具栏（添加店铺监控、刷新快照一行）新增「买家登录」按钮与登录状态标签；链接输入 placeholder 与错误提示适配拼多多买家端 |
| `api/pddMonitorApi.js` | 修改 | 封装 buyer-login / buyer-session 请求 |

复用不动：monitor 全部表结构、`MonitorIngestService` 入库与信号计算、`MonitorServiceImpl` 的 trigger / latest / trend / signals 查询、前端爆款榜 / 趋势图 / 告警面板。

## 4. 数据流

1. 前端添加店铺 → `POST /api/monitor/targets`（platform=pdd，crawl_strategy=`pdd_shop_topn` / `pdd_pinned_offers`）→ `PddMonitorUrlValidator` 校验并规范化链接。
2. 手动「立即刷新」或调度到期 → `MonitorServiceImpl.trigger` 创建 `monitor_job` → `MonitorAgentTaskEnqueuer` 按平台分发 `pdd_monitor_crawl` 任务（payload：tenant_id / target_id / job_id / target_url / crawl_strategy / config_json / top_n）。
3. 助手领取任务 → `handle_pdd_monitor_crawl` → `PddMonitorAdapter.crawl_target` → `pdd_shop_collector.crawl_shop`：
   a. 解析目标 URL 得 mall_id（商品链接从 URL 参数或详情页取 mall_id）；
   b. 租户级买家 profile 启动 Playwright（无头；验证时切有头弹窗）；
   c. 打开店铺页，捕获商品列表 XHR 并回放，分页取 Top N + pinned goods；
   d. 解析商品字段；列表页缺少店铺名/图片时打开商品详情页补全（本期核心字段不依赖详情页）。
4. 助手回写 `POST /api/agent/pdd/monitor/ingest` → `MonitorIngestService.ingestSnapshot`：写 `monitor_snapshot` + `monitor_product_snapshot`，计算日增销量（本次累计 − 上次累计）与信号，更新 target 与 job 状态。
5. 前端 `latest` / `trend` / `signals` 展示，现有面板逻辑不变。

## 5. 字段映射（采集 → monitor_product_snapshot）

| 采集字段 | 落库字段 |
|---|---|
| goods_id | product_id |
| 标题 | product_name |
| 价格（元） | price |
| 「已拼 X 件」解析数值 | total_sales（累计） |
| 0（由入库按差值计算） | daily_sales |
| 「已拼 X 件」原文 | sale_text |
| 店铺 Top N 序号 | rank |
| 商品链接（goods.html?goods_id=…） | url |
| 主图 | image_url |
| 店铺名 | shop_name |
| 规范化店铺页链接 | shop_url |
| 是否在 config_json.pinned_offer_ids 中 | is_pinned |
| 在售/下架判定 | status / expired |
| 本次接口响应原文 | raw_json（截断 4000，与 1688 一致） |

## 6. 错误处理与登录/验证流程

- **买家会话隔离**：独立买家 profile（`.pdd-buyer-browser-profile/tenant-{id}`），与商家后台 profile 分开。
- **验证码/风控**：无头抓取遇到登录 CTA、验证码或风控页时切有头窗口，等待用户完成验证后继续；同一任务内等待上限 5 分钟，超时抛 `MONITOR_TIMEOUT`。调度任务遇到弹窗需求直接失败并记录 `auth_or_risk` 信号，前端指引用户手动刷新完成验证。
- **失败隔离**：单店铺失败不影响其他目标；单商品解析失败跳过该项；部分成功任务标记成功并附告警（沿用现有框架）。
- **频率控制**：列表分页间隔加随机抖动（复用 `pdd_tasks.py` 的 `_pdd_page_sleep` 与 TokenBucket 节奏）。
- **数据质量**：「已拼 X 件」支持"万"等单位换算；日增销量为负或跳变异常（>5 倍且 >1000）标 `suspicious` 不计入趋势，保留 `raw_json`。
- **冷却**：沿用现有 `monitor:{target_id}` 冷却 scope。

采集阶段统一抛 `MONITOR_*` 错误码：

| 错误码 | 触发 |
|---|---|
| `MONITOR_AUTH_REQUIRED` | 需前台登录/验证，触发弹窗流程 |
| `MONITOR_RISK_BLOCKED` | 被风控拦截 |
| `MONITOR_NO_PRODUCTS` | 店铺页无商品或解析失败 |
| `MONITOR_INVALID_URL` | 解析不出 mall_id / goods_id |
| `MONITOR_TIMEOUT` | 抓取或验证超时 |
| `MONITOR_JOB_FAILED` | 兜底 |

## 7. 买家登录通道

- 前端 `PddMonitorPanel` 工具栏（添加店铺监控、刷新快照同一行）新增「买家登录」按钮与登录状态标签（未登录 / 登录中 / 已登录），状态轮询 `GET /api/pdd/monitor/buyer-session`。
- 点击「买家登录」→ `POST /api/pdd/monitor/buyer-login` → Java 创建 `pdd_buyer_login_open` 任务 → 助手打开买家端有头浏览器（yangkeduo 店铺页），等待用户登录/过验证（上限 10 分钟）→ 完成任务时回写 `{"session": {...}}`，Java 落 `pdd_session_snapshot`（store_id=`buyer`），前端状态变「已登录」。
- 登录窗口打开期间与其他 PDD 浏览器任务互斥（纳入 browser busy 集合）。

## 8. 测试策略

| 层级 | 覆盖 |
|---|---|
| 单元（Python） | 链接解析（店铺页 / goods 页提取 mall_id、goods_id）、「已拼 X 件」数值解析（含"万"换算）、适配器字段映射、`handle_pdd_monitor_crawl` 与 ingest 回写（mock Java client） |
| 单元（Java） | `PddMonitorUrlValidator`（合法/非法链接）、`MonitorAgentTaskEnqueuer` 按平台分发（1688 走原任务、pdd 走新任务） |
| 前端 | 现有测试跑通 + 手动 smoke：添加 PDD 店铺 → 买家登录 → 立即刷新 → 爆款榜 / 趋势图 / 告警展示 |
| 回归 | 1688 / Temu 竞店功能不受影响 |

解析测试用真实页面 HTML/JSON 做 fixtures。实现阶段需要 1–2 个真实拼多多竞店店铺链接样本，抓取一次后保存为测试夹具。

## 9. 验收标准

1. 店铺主页链接与商品详情链接都能正确添加，商品链接可反查店铺。
2. 买家登录按钮完成一次登录后，「立即刷新」可真实抓到 Top N 商品并入库展示。
3. 第二次刷新后趋势图出现日增销量；价格 / 排名变化产生告警信号。
4. 被风控/验证码拦截时任务以 `MONITOR_AUTH_REQUIRED` / `MONITOR_RISK_BLOCKED` 失败，前端有明确指引。
5. 1688 / Temu 竞店功能回归不受影响。

## 10. 实施阶段（概要，待 writing-plans 细化）

1. Python：`pdd_shop_collector.py` + `pdd_monitor_adapter.py` + handlers / java_client / monitor_worker 注册。
2. Java：`PddMonitorUrlValidator` + 按平台派发重构 + `PddAgentTasks` + buyer-login / buyer-session / monitor-ingest 端点。
3. 前端：买家登录按钮与状态标签 + URL 提示与错误文案。
4. 测试：真实链接样本 fixtures、单测、冒烟、1688 / Temu 回归。

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| PDD 反爬强（captcha / 限频） | 串行采集、随机抖动、退避重试、失败隔离、冷却 |
| 页面 / XHR 结构变化 | 解析集中在一个模块、`raw_json` 留存、fixtures 回归 |
| 买家端无免登录公开接口 | XHR 捕获回放 + 独立买家 profile 维护登录态 |
| 与商家后台会话冲突 | 独立买家 profile 目录，任务互斥 |
| 买家登录弹窗占用任务时长 | 登录任务上限 10 分钟、抓取任务验证等待上限 5 分钟、超时降级为失败并提示 |
