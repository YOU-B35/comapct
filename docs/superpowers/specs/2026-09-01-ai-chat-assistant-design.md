# AI 聊天助手（Shopify 批量上货工具）设计文档

- 日期：2026-09-01
- 状态：已获用户口头确认，待用户审阅本文件
- 范围：在现有 `shopify-bulk-uploader` 本地工具中嵌入一个受限 AI 聊天窗口

## 1. 背景与目标

现有工具支持上传 Excel（含 WPS 内嵌图片提取）、校验预览、创建 Shopify 商品（草稿）、修改库存/类别/产品类型/集合关联。用户希望直接在这套工具里和一个 AI 助手对话完成这些操作，并且：

- AI 只能做"上货/修改"相关工作，**不能做其他事情**（不读任意文件、不执行任意命令、不访问外网内容）；
- 高风险操作（删除商品、直接公开上架）必须先经用户确认；
- 需要上下文管理（会话历史 + 自动摘要）和全局记忆存储（跨会话偏好）。

## 2. 已确认需求

| 项 | 决定 |
| --- | --- |
| 模型 | DeepSeek（OpenAI 兼容接口，`AI_BASE_URL` / `AI_API_KEY` / `AI_CHAT_MODEL` 可配置） |
| 实现方案 | 函数调用 + 后端白名单工具注册表（方案 A） |
| 操作边界 | 白名单工具集；删除、公开（ACTIVE）需聊天内确认；其余直接执行 |
| UI | 页面右侧固定聊天侧边栏 |
| 上下文 | 会话历史持久化到本地，超长自动摘要，不丢重点 |
| 记忆 | 全局偏好记忆（自动沉淀 + 可查看/清空），跨会话生效 |
| 安全 | 依赖代码层白名单而非提示词；服务建议仅监听 127.0.0.1 |

## 3. 非目标（明确不做）

- 不做通用网页浏览、抓取、搜索；
- 不做 shell / 任意文件系统访问 / 任意代码执行；
- 不做多用户账号与权限体系（本工具定位本地单用户）；
- 不做语音、图片生成以外的多模态（图片生成沿用现有 `openaiImages.js`，不在本次范围）。

## 4. 架构与数据流

```
浏览器右侧聊天侧边栏 (public/chat.js)
        │  POST /api/chat（SSE 流式）  /api/chat/upload（Excel 附件）
        ▼
src/ai/chatController.js —— 会话状态机、确认门、工具调用循环
        │
        ├── src/ai/llmClient.js        DeepSeek（openai SDK + 自定义 baseURL），支持流式
        ├── src/ai/tools.js            工具注册表（唯一执行入口，白名单）
        ├── src/ai/schema.js           工具参数 schema 校验（zod 风格手写校验）
        ├── src/ai/sessionStore.js     data/chat/sessions/<id>.jsonl + 摘要
        ├── src/ai/memoryStore.js      data/chat/memory.json（键值偏好）
        └── 复用现有模块
            ├── src/excelParser.js / src/mapper.js / src/cellImages.js
            ├── src/shopify.js（商品/变体/图片/库存/集合/分类）
            └── 内存批次（/api/upload 产物）
```

数据流（一次对话）：

1. 前端把用户消息 + 可选附件（Excel）发给 `/api/chat`；
2. 控制器追加消息到当前会话，构建 `system + 全局记忆 + 会话摘要 + 最近 N 条`；
3. 调用 DeepSeek（流式），若模型请求工具调用：
   - 服务端在注册表查找工具，校验参数 schema；
   - 未注册工具 / 参数非法 → 直接返回拒绝原因给模型；
   - 若工具标记 `requiresConfirmation` → 进入"待确认"状态，把确认卡片推给前端，等用户确认后再执行；
   - 执行工具 → 结果（截断后）回填给模型继续；
4. 模型产出最终文本 → SSE 流式返回前端；
5. 会话历史落盘；必要时生成摘要。

## 5. 工具白名单

下表是唯一允许 AI 调用的工具，未列出的任何工具/行为一律拒绝。

| 工具 | 说明 | 关键参数 | 需确认 |
| --- | --- | --- | --- |
| `get_batch_summary` | 查看批次汇总与商品列表 | `batchId` | 否 |
| `list_products` | 查询店铺商品（分页/筛选） | `query?`, `limit?` | 否 |
| `get_product_detail` | 商品详情（变体/库存/图片/类别） | `id` 或 `handle` | 否 |
| `create_products` | 把批次商品创建到 Shopify（**固定 DRAFT**，可带 SKU 图片） | `batchId`, `includeSkuImages?` | 否 |
| `set_inventory` | 设置变体库存数量 | `ids`/`handles`, `quantity`(0-100000) | 否 |
| `set_product_category` | 设置标准分类（默认钓鱼分类） | `ids`, `categoryId?` | 否 |
| `set_product_type` | 设置产品类型（可清空） | `ids`, `productType` | 否 |
| `assign_collections` | 按系列关联集合 | `ids`, `collections[]` | 否 |
| `delete_products` | 删除商品 | `ids` | **是** |
| `publish_products` | 公开上架（ACTIVE） | `ids` | **是** |
| `memory_get` | 读取偏好 | `key?` | 否 |
| `memory_set` | 写入偏好 | `key`, `value` | 否 |
| `memory_list` | 列出全部偏好 | 无 | 否 |
| `memory_clear` | 清空偏好 | `key?` | 否 |

隔离规则：

- 工具实现只调用现有业务模块，不开放任意代码/任意文件/外网；
- 参数 schema 校验（类型、范围、id/handle 格式、数量上限），非法直接拒绝；
- 工具结果做长度截断（列表类默认 ≤50 条），防止上下文爆炸；
- 文件只允许通过 `/api/chat/upload` 上传的 Excel（复用现有 multer 限制）。

## 6. 确认门

- 仅 `delete_products`、`publish_products` 标记为高风险；
- 当模型请求高风险工具时，控制器不执行，而是：
  1. 生成确认卡片（写明将删除/公开哪些商品，含标题与数量）；
  2. 前端展示"确认 / 取消"按钮；
  3. 用户确认 → 重新提交执行；取消或更换话题 → 丢弃；
- 同一会话同时只允许一个待确认操作；新高风险请求会先提示取消旧确认。

## 7. 上下文管理

- 会话历史：`data/chat/sessions/<id>.jsonl`，每行一条消息（role/content/工具调用与结果）；
- 构建请求：`system`（角色与边界说明）+ 全局记忆 + 会话摘要（若有）+ 最近 20 条消息；
- 超长处理：当消息数 > 20 或估算 token 超阈值（默认 ~12000）时，用 DeepSeek 把旧消息压成摘要，存到会话文件，后续请求只带摘要 + 最近消息；
- 会话文件只增不改（摘要单独字段），刷新/重启不丢。

## 8. 全局记忆

- 存储：`data/chat/memory.json`，结构 `{ "<key>": { "value": "...", "updatedAt": "ISO" } }`；
- 写入：AI 通过 `memory_set` 沉淀长期偏好（如"库存默认 100""类别=钓鱼用具""默认创建草稿"）；
- 注入：每次请求把记忆内容放进 system 提示，让 AI 遵循用户长期偏好；
- 管理：侧边栏提供"记忆管理"入口，可查看全部、删除单条、一键清空；
- 一致性：`memory_set` 只能写字符串键值，防止污染结构。

## 9. 边界与安全

- 唯一执行入口是工具注册表；模型输出任何未注册工具名都会被拒绝并回传原因；
- 系统提示词同时声明能力边界（只处理上货/修改相关），但安全不依赖提示词；
- 服务监听建议改为 `127.0.0.1`（`app.listen(port, "127.0.0.1")`），阻止局域网访问；
- `AI_API_KEY` 只存 `.env`，不进前端、不打日志；会话/记忆文件仅本机；
- 上传 Excel 沿用 multer 300MB 限制与上传目录隔离。

## 10. UI

- 右侧固定侧边栏（宽约 360px）：
  - 消息列表（用户/AI/工具执行状态），AI 回复流式渲染；
  - 输入框 + 附件按钮（选择 `.xlsx`）+ 发送；
  - 确认卡片（高风险操作）；
  - 顶部"记忆管理"与"清空会话"入口；
- 新增 `public/chat.js`，样式扩展 `public/styles.css`；`index.html` 挂载侧边栏容器；
- 未配置 `AI_API_KEY` 时，聊天区显示提示且禁用发送。

## 11. 配置（.env 新增）

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=sk-xxxxxxxx
AI_CHAT_MODEL=deepseek-chat
AI_CONTEXT_MAX_TOKENS=12000
```

`openai` 依赖已存在（^4.85.1），以 `baseURL = AI_BASE_URL`（默认 `https://api.deepseek.com`，SDK 会自行追加 `/chat/completions` 路径）实例化客户端，无需新增依赖。

## 12. 错误处理

- LLM/网络失败：返回可读错误，会话历史保留，用户可重试；
- 工具执行失败：错误文本回填给模型，让它说明原因或换方案；
- 参数校验失败：拒绝并回传校验原因；
- 会话文件损坏：跳过坏行并继续，不阻塞对话；
- 确认门超时/切换话题：自动作废待确认操作。

## 13. 测试

- 单元测试：
  - 工具注册表：未注册工具拒绝、参数 schema 校验（非法数量/SKU/缺参）；
  - 确认门状态机：请求 → 待确认 → 确认/取消 → 执行/丢弃；
  - 记忆存储：读写/列出/清空、非法键拒绝；
  - 上下文裁剪：超长会话正确生成并注入摘要；
- 集成测试：聊天控制器用 mock LLM 验证"工具调用 → 执行 → 回填 → 最终回复"全链路；
- 手工验收：真实 DeepSeek Key 下完整走一遍"上传 Excel → 创建草稿 → 改库存 → 确认删除"。

## 14. 文件变更清单

新增：

- `src/ai/chatController.js`
- `src/ai/llmClient.js`
- `src/ai/tools.js`
- `src/ai/schema.js`
- `src/ai/sessionStore.js`
- `src/ai/memoryStore.js`
- `public/chat.js`
- `test/ai/*.test.js`

修改：

- `src/server.js`（挂载 `/api/chat`、`/api/chat/upload`、记忆管理接口）
- `src/config.js`（新增 AI 配置项）
- `public/index.html`、`public/styles.css`（侧边栏 UI）
- `.env.example`（新增 AI 配置示例）
