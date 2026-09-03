# Amazon 固定登录态接口采集设计

**状态：** 运行时框架已实现；待真实店铺确认批准端点

**日期：** 2026-09-04
**范围：** Amazon 运营模块的 `daily`、`reports`、`account_health` 同步

## 1. 背景与目标

当前 Amazon 普通模式通过紫鸟 CLI 定位店铺，并由 ZClaw 读取 Seller Central 页面内容。该路径可用作通用降级，但页面加载、文本提取和页面结构变化都会影响耗时与稳定性。

本设计增加一条优先的数据路径：在紫鸟已登录浏览器的页面上下文内，调用已经确认的 Seller Central 同源数据接口，直接取得 JSON 并映射为 CrossHub 的标准数据。接口确认只在开发联调阶段进行一次；日常同步不扫描 Network、不枚举页面请求，也不学习新接口。

目标：

1. 将重复同步的页面操作缩减为少量固定 JSON 请求。
2. 保持 Cookie、会话令牌和浏览器 Profile 仅留在用户本机。
3. 让每个前端字段都有可追溯的数据来源、接口版本和降级策略。
4. 当固定接口失效时，自动回退到现有的页面解析，而不是返回伪造数据。

## 2. 非目标与边界

- 不在网站前端直接请求 Amazon。
- 不把 Amazon Cookie、授权头或页面令牌上传到 Java 服务或数据库。
- 不提供任意 URL、任意请求头、任意 JavaScript 的远程执行能力。
- 不在生产同步时动态抓包、探测或猜测 Seller Central 的内部接口。
- 不规避登录、人机校验、权限限制或平台访问控制；出现这些状态时任务应明确失败并提示人工处理。

## 3. 总体链路

```text
Vue 点击同步
  -> POST /api/amazon/sync(scope, platform_account_id)
  -> Java 创建 tenant + 店铺 + scope 对应的 Agent 任务
  -> 本机 Helper 领取任务
  -> 紫鸟 CLI 按已绑定的 store_id 打开已登录浏览器
  -> ZClaw 在当前页面同源上下文执行固定接口请求
  -> JSON 校验、字段标准化、回传任务结果
  -> Java 按 tenant_id + platform_account_id + scope 落库
  -> Vue 重读 /api/amazon/daily 或 /api/amazon/insights 并回显
```

固定接口不可用、返回非预期 JSON、会话失效或数据质量不足时：

```text
固定接口失败 -> 页面解析降级 -> 仍失败则任务失败并保存原因
```

## 4. 一次性接口确认流程

接口确认只在一台已授权、已登录的紫鸟浏览器上执行，不属于用户日常同步流程。

1. 针对 `daily`、`reports`、`account_health` 分别打开对应 Seller Central 页面。
2. 记录页面实际使用的 JSON 请求：稳定路径、HTTP 方法、非敏感参数、响应样例和触发页面。
3. 剔除含一次性签名、临时下载链接、追踪请求、埋点和非业务响应的记录。
4. 使用同一店铺再次验证接口；仅在两次结果一致、响应可解析时批准。
5. 将批准项人工写入 Python 源码中的静态端点注册表，并补充脱敏 fixture 与单元测试。
6. 提交代码审查后发布。运行期不读取 HAR、不读取上次抓包文件，也不自动改写注册表。

接口地址本身可固定；以下内容必须在每次请求时由当前浏览器上下文生成或选择：店铺上下文、日期范围、分页游标、语言/站点参数，以及可能会过期的页面防伪令牌。它们不得被持久化为固定密钥。

## 5. 静态端点注册表

注册表应位于 `backend/python/app/amazon/`，作为受代码审查保护的 Python 常量，而不是环境变量或数据库配置。每个端点使用不可变定义，至少包含：

| 字段 | 说明 |
| --- | --- |
| `key` | 稳定、可读的端点标识，例如 `orders_list_v1` |
| `scope` | `daily`、`reports` 或 `account_health` |
| `page_url` | 发起请求前必须处于的 Seller Central 同源页面 |
| `method` / `path` | 经确认的固定 HTTP 方法和路径 |
| `build_request` | 仅构造日期、分页、店铺上下文等非敏感动态参数 |
| `response_schema` | 必需字段、最大返回量和版本识别规则 |
| `mapper` | JSON 到 CrossHub 标准指标、订单或商品的映射函数 |
| `fallback` | 接口失败时调用的页面解析器 |
| `approved_at` / `version` | 审批时间和接口版本 |

执行器只能通过 `key` 选择已注册条目；任务 payload、前端参数和 LLM 均不能传入 URL、脚本、Cookie 或自定义请求头。

## 6. 浏览器上下文请求规则

Helper 使用 `ziniao-cli page exec` 在已打开的同源页面中执行一个固定的请求模板。模板只接受注册表给出的 `method`、`path` 和经类型校验的参数，并遵守：

1. 目标必须是 `https://sellercentral.amazon.com` 的同源 HTTPS 地址。
2. 请求使用浏览器当前会话，凭据仅限当前源；不读取或导出 Cookie。
3. 响应必须是 JSON，且限制状态码、体积、数组长度和执行超时。
4. 原始响应只在内存中用于映射；日志仅记录 `key`、状态码、耗时、字段计数和脱敏错误码。
5. 页面令牌只可在当前请求生命周期内由当前页面读取，不写入文件、数据库、Agent 日志或任务结果。

## 7. Scope 与前端字段契约

| Scope | 前端主要数据 | 优先固定接口 | 当前降级路径 |
| --- | --- | --- | --- |
| `daily` | 销售额、订单量、待处理订单、订单明细 | 经营首页摘要、订单列表 JSON | 首页 + 订单页文本/表格解析 |
| `reports` | ASIN、SKU、流量、转化、销量、库存 | Business Report、库存列表 JSON | Business Report + 库存页解析 |
| `account_health` | 账户评级、ODR、迟发率、追踪率、违规 | 账户健康摘要 JSON | 账户健康页文本解析 |

前端继续只依赖 CrossHub 自己的 `/api/amazon/daily` 与 `/api/amazon/insights`。无论来源是固定接口还是页面解析，后端返回的数据结构必须保持一致。

## 8. 数据质量、缓存与错误处理

- 结果写入时保留 `transport`（`zclaw_api` 或 `zclaw_page`）、`endpoint_key`、`endpoint_version`、同步时间和数据质量标记。
- JSON 缺失关键字段、字段类型漂移、结果为空或超过合理上限时视为接口失败，不覆盖上一份有效快照。
- 单个端点失败不阻断同 scope 的其它端点；scope 级别结果标记为部分成功并附带可读原因。
- 连续失败达到阈值后将端点标记为需要维护，后续任务直接走页面降级，避免每次同步增加无效等待。
- `刷新全部` 仍按 `daily -> reports -> account_health` 串行调度，避免同一紫鸟浏览器会话的并发互相干扰。

## 9. 实施与验收

### 当前实现状态

- 已实现：源码静态端点注册表、同源浏览器登录态 JSON 执行器、响应大小/JSON/来源校验、scope 页面降级、来源与端点诊断回传。
- 已实现：白名单为空时不发起任何页面访问或接口探测；现有页面解析行为保持不变。
- 待完成：在真实已授权店铺上确认 `daily`、`reports`、`account_health` 的批准端点，并将其常量、mapper 和脱敏 fixture 提交到代码。
- 交接步骤见 `2026-09-04-amazon-static-api-handover.md`。

实施顺序：

1. 收集并审核一次真实店铺的脱敏请求/响应样例。
2. 新增静态端点注册表、浏览器上下文 JSON 执行器和字段 mapper。
3. 将 ZClaw crawler 改为“固定接口优先，页面解析降级”。
4. 为每个批准接口加入 fixture 测试、schema 漂移测试和降级测试。
5. 在至少一个真实店铺连续执行 `daily`、`reports`、`account_health`，核对数据库与 Seller Central 显示值。

验收标准：

- 日常任务没有 Network 扫描或接口发现行为。
- 任务 payload、日志、数据库和前端响应中均不出现 Cookie 或页面令牌。
- 已批准接口成功时使用 `zclaw_api`，失败时可见 `zclaw_page` 降级来源。
- 任一固定接口的路径或响应变化不会导致前端字段错位或旧数据被空结果覆盖。
- 同一店铺连续同步的耗时和失败率较当前纯页面解析路径有可量化改善。
