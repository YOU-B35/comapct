# 亚马逊模块 LLM Agent 聊天通道（Chat-LLM-Agent）设计文档

> 日期：2026-09-01
> 状态：待用户评审
> 性质：平台无关 Agent 内核 + 亚马逊适配层先行；新通道并行，旧 `amazon_sync` 保留
> LLM：`deepseek-v4-flash-vision-exp`（可配置，备选 `deepseek-v4-flash`）

## 1. 背景与目标

### 1.1 现状

- 现有亚马逊链路：紫鸟 WebDriver（本机 HTTP API :16851）→ CDP → Playwright 解析 DOM/CSV → Java 入库 → Vue 展示。
- 痛点：解析器依赖硬编码选择器，页面改版即挂，维护成本高、不稳定。
- 用户决策：用紫鸟官方 CLI + 大模型 Agent 替代 Playwright 解析层；先在亚马逊模块以"聊天问答"形态验证。

### 1.2 关键认知

- 紫鸟 API/CLI 不提供电商平台经营数据接口，只提供浏览器窗口控制与页面内容读取能力。
- 紫鸟 CLI 与平台无关：只要店铺账号在紫鸟中绑定且登录态正常，同一套 CLI 工具可用于任何电商平台。
- "页面内容 → 结构化数据"由 Agent 内核中的 LLM 抽取或确定性代码（官方 CSV 解析）完成。

### 1.3 目标（v1）

1. 亚马逊模块新增"AI 助手"聊天框：用户选店铺后自然语言提问，Agent 通过紫鸟 CLI 实时取数，聊天窗口返回答案。
2. 平台无关内核：Agent 运行时（LLM 循环、工具层、上下文/记忆/边界管理）不感知平台，平台差异收敛到适配层。
3. Agent 内核封装为内部 API，供其他模块后续快速接入。
4. 旧通道（`amazon_sync`）保持不动，新通道并行验证；稳定后切换入口或合并。
5. 数据真实性红线：宁可不答，不编数据。

### 1.4 非目标（v1）

| 不做 | 说明 |
|------|------|
| 数据入库与前端看板映射 | v1 只在聊天窗口返回数据 |
| 写操作 | 改价、发货、回复买家等一律拒绝 |
| 跨平台聚合问答 | 如"对比亚马逊与 Temu 订单"暂不支持 |
| 完全开放的网页探索 | 问题域限定在模块现有数据域 |
| 长期向量检索记忆 | v1 用结构化记忆表，二期再评估 embedding |

## 2. 总体架构

三层结构：

```text
┌─ 接入层 ────────────────────────────────┐
│ 前端 AmazonModuleView（复用 AiChatPanel）│
│ Java：/api/amazon/chat* + 任务队列/直连   │
├─ Agent 内核（平台无关，Python）───────────┤
│ LLM 循环 + function calling + 工具执行     │
│ 抽取校验 + 边界管理 + 上下文 + 记忆        │
├─ 平台适配层（每平台一套）─────────────────┤
│ 页面配方 / 数据 Schema / 校验规则 / 问题域  │
└─────────────────────────────────────────┘
```

数据流：

```text
用户提问(带 store) → POST /api/amazon/chat (Java)
  → 创建 amazon_chat 任务 + session
  → 本地 Agent 轮询领取 → 执行 Agent 循环
  → 进度/结果回写 Java → 前端轮询展示
```

## 3. Agent 内核 API（封装为内部服务）

Python 侧新增内部 HTTP 服务，与现有 Agent 进程同机或独立部署，统一入口供其他模块调用：

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/v1/agent/chat` | 提交问答（platform / store_id / session_id / user_query / context） |
| GET | `/api/v1/agent/jobs/{job_id}` | 进度与结果轮询 |
| POST | `/api/v1/agent/chat/stream` | （可选）SSE 流式返回 |
| GET | `/api/v1/agent/memory/{store_id}` | 查看店铺记忆 |
| DELETE | `/api/v1/agent/memory/{store_id}` | 清空店铺记忆 |

- 认证：内部 API Token + 内网/IP 白名单；密钥不落日志。
- 错误码统一 `AGENT_*` 前缀，供各模块复用。
- Java 侧两种接入模式都保留：任务队列模式（兼容现有轮询架构）与内核 HTTP 直连模式（其他模块快速接入）。

## 4. 数据模型

新增表：

| 表 | 用途 |
|----|------|
| `amazon_chat_session` | 会话：id / tenant_id / user_id / store_id / platform / status / created_at / updated_at |
| `amazon_chat_message` | 消息：id / session_id / role(user/assistant/tool_summary/system) / content / tool_calls(JSON) / created_at |
| `amazon_chat_tool_log` | 工具调用日志：session_id / tool_name / args(JSON) / result_summary / ok / duration_ms |
| `amazon_chat_memory` | 店铺记忆：store_id / mem_key / mem_value(JSON) / ttl / updated_at，唯一键 (store_id, mem_key) |

任务复用现有 Agent 任务机制，新增 `task_type=amazon_chat`，不修改旧任务 handler。

## 5. LLM 选型与调用

- 主模型：`deepseek-v4-flash-vision-exp`（DeepSeek 最新视觉模型，2026-08-21 上线，实验性质）。
- 备选/编排模型：`deepseek-v4-flash`（纯文本），模型名可配置切换。
- 调用方式：OpenAI 兼容 Chat Completions，`base_url=https://api.deepseek.com`，支持 function calling（V3.2 起支持思考模式工具调用；strict 模式为 Beta 可选）。
- 图片输入：仅允许出现在 `user` 消息；Base64 内联（单图 ≤32 MiB，折算 ≤384 token）或 Files API；截图兜底时用 `detail=low` 控制成本。
- 配置：`LLM_*` 环境变量/DB 配置，模型可切换；API Key 不进代码、不进日志、不进 git。

## 6. 工具层（全部走紫鸟官方 CLI）

| 工具 | CLI 命令 | 用途 |
|------|----------|------|
| `store_list` | `ziniao-cli store list` | 店铺列表/解析 |
| `store_open` | `ziniao-cli store open --name/--id [--url]` | 打开/复用店铺浏览器 |
| `store_close` | `ziniao-cli store close` | 关闭店铺窗口 |
| `page_visit` | `ziniao-cli page visit --store-id --url [--wait-until]` | 导航 |
| `page_content` | `ziniao-cli page content --content-format structured` | 读取结构化页面内容 |
| `page_exec` | `ziniao-cli page exec` | 滚动、点击导出、读取下载 |
| `automation_run` | `ziniao-cli automation run --steps` | 多步编排（visit→wait→click→exec） |
| `page_screenshot` | `ziniao-cli page screenshot` | 截图（视觉模型兜底） |
| `csv_read` | 纯代码解析官方导出文件 | 最快、最准、零 token |
| `env_doctor` | `ziniao-cli doctor` | 环境/登录态自检 |

- 工具输出瘦身：回填 LLM 前截断、行数上限、字段裁剪。
- 工具层薄封装：命令参数收敛到适配层，CLI 版本升级只影响工具实现。

## 7. 边界管理

1. **铁律 System Prompt**：只用提供的工具取数；只回答页面真实抓到的数据；拿不到就明说"未获取到"；禁止推测、估算、编造。
2. **意图分类 + 问题域白名单**：属于亚马逊现有数据域（账号健康、订单、商品/库存/广告、消息、评论、Case）才放行；闲聊、跨平台、写操作、越权问题直接拒绝并引导。
3. **工具白名单 + strict Schema**：LLM 只能调用注册工具，参数严格校验。
4. **答案校验器**：最终回答必须标注数据来源页面与抓取时间；数据与工具结果不一致时打回重写或返回固定话术。
5. **会话绑定店铺**：回答严格限定在当前 session 绑定的 store，不串店；无该店权限拒绝。

## 8. 上下文存储与管理

- 持久化：`amazon_chat_session` / `amazon_chat_message` / `amazon_chat_tool_log` 三张表，Java 负责读写，Agent 保持无状态。
- 上下文瘦身：工具原始输出（整页 HTML、超长 CSV）不进对话，只存"结构化提取结果 + 页面摘要"。
- 窗口管理：会话保留最近 N 轮完整消息，更早内容由 LLM 压缩为摘要继续携带。
- 会话内抓取缓存：15-30 分钟 TTL，同会话同类数据复用，不重复开页面。
- 前端刷新后历史可恢复，支持继续追问。

## 9. 记忆存储管理

- 短期记忆 = 会话上下文（见上）。
- 长期记忆（按店铺）：
  - 事实记忆：merchantId、常用页面路径、店铺站点/语言等，跨会话复用。
  - 经验记忆：成功完成某类问题的步骤模板（如 TOP20 = home → BR 导出 → 库存导出 → 广告），下次同类问题直接套模板，减少 LLM 决策轮数。
- 落地：`amazon_chat_memory` 表（store_id + key + JSON + TTL），v1 不做向量检索。
- 生命周期：任务开始时读取 → 成功后更新 → 失败记录失败模式 → TTL 或手动清理。
- 脱敏：绝不存密码/cookie/登录态；提供查看/清空管理入口。

## 10. 校验与错误处理

- 抽取输出 JSON Schema 校验：订单号/ASIN/金额/日期格式、非空、数值范围。
- 失败重试：最多 2-3 次，带错误反馈回填 LLM。
- 错误码：

| 错误码 | 触发 |
|--------|------|
| `AGENT_OUT_OF_SCOPE` | 问题超出数据域/权限 |
| `AGENT_ZINIAO_OFFLINE` | 紫鸟客户端/CLI 不可用 |
| `AGENT_LOGIN_REQUIRED` | 店铺未登录 |
| `AGENT_TOOL_ERROR` | CLI 工具执行失败 |
| `AGENT_VALIDATION_FAILED` | 抽取结果未过校验且重试仍失败 |
| `AGENT_LLM_ERROR` | LLM API 调用失败 |
| `AGENT_TIMEOUT` | 单次问答超时（10 分钟），返回部分结果 |

## 11. 前端

- 复用 `AiChatPanel.vue`，将 Demo 回复替换为真实接口调用。
- `AmazonModuleView` 集成：店铺选择 + AI 助手入口 + 进度反馈（打开店铺 → 读取页面 → 整理答案）。
- 会话历史持久化，刷新可恢复；欢迎语/快捷问题按亚马逊数据域定制。

## 12. 测试策略

| 层级 | 覆盖 |
|------|------|
| 单测（Python） | LLM client 封装（mock）、工具参数解析、抽取校验、边界拦截、记忆读写 |
| 集成 | 本地 YOTO 美国账号 + 紫鸟客户端，跑通账号健康 / 订单 / TOP20 三类问题 |
| 对账 | 人工对照 Seller Central，核对数值与来源标注 |
| 统计 | 每次问答耗时、token 用量、工具调用次数 |
| 回归 | 旧 `amazon_sync` 全量回归不受影响 |

## 13. 验收标准

1. 聊天框可提问并返回真实数据，带来源与时间标注。
2. 乱问/跨域/写操作问题被拒绝，不编造数据。
3. 会话可追问、历史可恢复；上下文窗口切换不丢要点。
4. 店铺记忆跨会话生效，可查看/清空。
5. 单次问答耗时与 token 统计可见。
6. 旧通道回归通过，可一键回滚。

## 14. 实施阶段（概要，待 writing-plans 细化）

| 阶段 | 内容 |
|------|------|
| M1 | Python Agent 内核：LLM 循环 + CLI 工具层 + DeepSeek 接入（命令行验证） |
| M2 | 内核 API 封装 + Java chat 接口 + 前端聊天框接入 |
| M3 | 上下文 / 记忆 / 边界管理落地 |
| M4 | 端到端验收 + 对账 + 耗时/token 统计 |

每阶段旧通道不动，新通道独立任务类型并行。

## 15. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 视觉模型为实验性质 | 模型可配置，纯文本模型兜底编排，视觉仅用于截图 |
| LLM 抽取幻觉 | Schema 校验 + 来源强制标注 + 宁缺毋滥 |
| token 成本失控 | CSV 优先、上下文瘦身、会话缓存、意图拦截 |
| 紫鸟 CLI 能力/版本变化 | 工具层薄封装，命令收敛到适配层 |
| 多店铺并发 | 复用现有 `BROWSER_LOCK_POOL` 浏览器锁 |
| 会话/记忆膨胀 | 窗口压缩、TTL、手动清空 |

## 16. 自检

- [x] 无占位符 / TBD / 未决字段。
- [x] 平台无关内核与亚马逊适配层边界清晰，其他模块可复用。
- [x] v1 范围聚焦：不做入库、写操作、开放探索、向量检索。
- [x] 与用户已确认决策一致：本地验证、并行新通道、紫鸟官方 CLI、DeepSeek 视觉模型、内核 API 封装。
