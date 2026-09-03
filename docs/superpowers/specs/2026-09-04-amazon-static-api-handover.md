# Amazon 固定接口采集交接与真机联调

**日期：** 2026-09-04

**当前状态：** 静态登录态接口执行器、页面降级和单元测试已完成。尚未把未经真机验证的 Amazon 内部接口写入源码白名单。

## 交接内容

| 路径 | 用途 |
| --- | --- |
| `backend/python/app/amazon/static_authenticated_api.py` | 固定端点白名单、同源 JSON 请求、响应校验和诊断 |
| `backend/python/app/amazon/zclaw_crawler.py` | 固定接口优先，页面解析降级 |
| `backend/python/tests/test_amazon_static_authenticated_api.py` | 白名单、会话边界、合并和降级测试 |
| `docs/superpowers/specs/2026-09-04-amazon-static-authenticated-api-design.md` | 设计、边界和验收标准 |

`STATIC_AUTHENTICATED_ENDPOINTS` 有意保持为空。真实接口确认前，系统继续使用当前页面解析，不会在运行时抓包、扫描或学习新接口。

## 真机前置检查

以下事项必须在同一 Windows 用户会话中准备完成。

1. 已安装紫鸟，且目标 Amazon 店铺已在 Seller Central 登录。
2. 当前 Windows 用户已完成紫鸟 CLI 授权。不得把 API Key 写入 Git、`.env`、任务 payload 或测试证据。
3. CrossHub Helper 已绑定目标租户并保持在线。
4. 紫鸟普通模式下 ZClaw Bridge 可用。此功能不需要、也不应强制使用旧 WebDriver。
5. CrossHub 店铺绑定保留紫鸟唯一 `store_id`。有重名店铺时不能只依赖店铺名匹配。

在 Helper 所在用户的 PowerShell 中，从 `D:\gongsi\comapct\tools\ziniao-cli\node_modules\.bin` 运行 `ziniao-cli doctor` 与 `ziniao-cli store list`。前者必须确认 CLI 授权和本地 Bridge 可用，后者必须列出目标 Amazon 店铺。任一项失败时，先修复紫鸟或 CLI 授权，不开始接口确认。

## 一次性接口确认

该步骤仅在开发联调时执行一次，不能进入日常同步流程。

1. 在已授权店铺依次打开经营首页、订单列表、Business Report/库存和账户健康页。
2. 在浏览器开发者工具 Network 中仅检查返回 `application/json` 的业务请求。
3. 记录候选请求的方法、稳定路径、非敏感 query/body 字段、触发页面、响应结构、响应大小和状态码。
4. 排除埋点、日志、临时下载链接、图片/脚本，以及包含可复用凭据的请求。
5. 再触发一次同一流程。只有路径与响应结构稳定，且不依赖持久化令牌时，才批准该请求。
6. 保存脱敏的请求/响应 fixture 供单元测试使用。不得保留 Cookie、Authorization、CSRF 值、买家信息或完整账号标识。

只有稳定的接口定义会写死。日期范围、分页游标、店铺上下文和短期页面令牌必须由当前浏览器会话临时生成，不能持久化。

## 登记批准接口

在 `static_authenticated_api.py` 的 `STATIC_AUTHENTICATED_ENDPOINTS` 中添加 `StaticAuthenticatedEndpoint` 常量。每项至少包含：`key`、`scope`、`page_url`、固定的同源 `method`/`path`、`provides`、`version`、批准日期、非敏感 `request_builder` 与经过 fixture 测试的 `response_mapper`。

框架会拒绝完整 URL、非 Seller Central 页面、未知 scope、自定义请求头、非 JSON 响应和过大响应。它使用浏览器的 `same-origin` 登录态，绝不导出 Cookie。

## 真机验收步骤

1. 在已授权 Windows 用户下启动 Java、Vue 和 Helper。
2. 在 Amazon 模块中选择唯一绑定的店铺。
3. 分别刷新账户健康、经营数据、Business Report，再执行“刷新全部”。
4. 检查任务结果。完整固定接口路径应显示 `transport: zclaw_api`、`endpoint_keys`、`endpoint_versions` 和 `fallback_used: false`。
5. 核对 Seller Central 页面、数据库快照和前端展示值，至少核对一个金额、数量、订单、商品和账户健康指标。
6. 临时移除批准端点，或让 fixture 返回非 JSON。任务必须改为 `zclaw_api+page` 或 `zclaw`，且不能以空数据覆盖已有有效快照。
7. 每个 scope 连续执行三次，记录耗时、成功率和降级次数，并与原有纯页面解析基线比较。

用脱敏任务日志和测试结果作为验收证据即可，不收集或上传包含店铺、买家信息的截图。

## 本地回归

从 `D:\gongsi\comapct\backend\python` 运行 `python -m unittest tests.test_amazon_static_authenticated_api tests.test_amazon_zclaw_crawler tests.test_ziniao_cli_tools tests.test_sync_helper_ziniao_startup tests.test_amazon_task_timing_context`。从 `D:\gongsi\comapct\dev\vue-site` 运行 `npm run build`，提交前执行仓库差异检查。

## 常见故障

| 现象 | 优先排查 | 处理方式 |
| --- | --- | --- |
| `AMAZON_ZINIAO_CLI_SETUP_REQUIRED` | 当前 Windows 用户是否完成 CLI 授权 | 完成授权后重启 Helper |
| Bridge 不可用或普通模式提示 WebDriver | 紫鸟客户端和 ZClaw Bridge | 保持普通模式，恢复客户端；不要强制旧 WebDriver |
| `NON_JSON_RESPONSE` | 固定路径、登录重定向或权限 | 不批准该接口；修复登录/权限并保留页面降级 |
| `HTTP_ERROR` | 方法、动态参数、当前页面令牌、店铺权限 | 对照脱敏 fixture；令牌只在当前请求中读取 |
| mapper 字段错误 | Seller Central 响应结构变化 | 更新 mapper/fixture，提升接口版本，保留页面降级 |
| 数据为空或不一致 | scope 映射、日期范围、分页、店铺绑定 | 不覆盖旧快照，修复映射后再批准 |
| 同步仍慢 | scope 缺少完整接口覆盖 | 补齐批准端点并确认 `fallback_used: false` |

## 回滚

固定接口不稳定时，删除对应 `StaticAuthenticatedEndpoint` 常量并发布即可。没有匹配批准项时，系统自动使用原有 ZClaw 页面解析，无需重置 Helper、CLI 或数据库。
