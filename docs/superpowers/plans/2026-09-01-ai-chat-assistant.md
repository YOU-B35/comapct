# AI 聊天助手（Shopify 批量上货工具）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Shopify 批量上货工具中嵌入一个右侧聊天侧边栏，AI（DeepSeek）只能通过白名单工具完成上货/修改/删除/记忆管理，删除与公开必须先经用户确认，并具备会话上下文与全局记忆。

**Architecture:** 前端侧边栏通过 SSE 调用 `/api/chat`；后端 `ChatController` 用 DeepSeek（openai SDK + 自定义 baseURL）做流式函数调用，工具执行只经过 `src/ai/tools.js` 白名单注册表，复用现有 `shopify.js / mapper.js / cellImages.js`；会话历史存 `data/chat/sessions/*.jsonl`，全局记忆存 `data/chat/memory.json`。

**Tech Stack:** Node >= 20（当前 20.19）、ESM、express、openai@^4.85.1（已有）、fflate（已有）、`node --test` 测试。

## Global Constraints

- 不新增 npm 依赖；`openai` 用 `baseURL = AI_BASE_URL`（默认 `https://api.deepseek.com`）。
- 所有 AI 相关代码放 `src/ai/`，测试放 `test/ai/`。
- 工具执行唯一入口是 `src/ai/tools.js` 注册表；未注册工具一律拒绝。
- `delete_products`、`publish_products` 必须标记 `requiresConfirmation` 并走确认门。
- `create_products` 固定 `status: "DRAFT"`，不允许直接 ACTIVE。
- 会话/记忆数据只写入 `data/chat/`（已加入 `.gitignore`）。
- 服务监听改为 `127.0.0.1`。
- 界面文案与 AI 回复使用中文。
- 测试命令统一为 `node --test <文件>`；提交使用 `git -c user.name="Codex" -c user.email="codex@local" commit ...`（仓库无全局身份）。

---

## 文件结构

新增：

- `src/ai/schema.js` — 工具参数校验（类型/范围/长度）
- `src/ai/memoryStore.js` — `memory.json` 读写
- `src/ai/sessionStore.js` — 会话 jsonl + 摘要 + 上下文构建
- `src/ai/shopifyTools.js` — 新增 Shopify 管理操作（库存/类别/类型/集合/删除/公开/查询）—— 注：为保持 `src/shopify.js` 聚焦，新操作放在独立模块
- `src/ai/tools.js` — 工具注册表（定义 + handler + 确认标记）
- `src/ai/llmClient.js` — DeepSeek 客户端（流式 + 摘要）
- `src/ai/chatController.js` — 对话循环、确认门、SSE 事件
- `public/chat.js`、`test/ai/*.test.js`

修改：

- `src/config.js`（AI 配置）、`src/server.js`（路由 + 127.0.0.1）、`public/index.html`、`public/styles.css`、`.env.example`

---

### Task 1: 参数校验器 `src/ai/schema.js`

**Files:**
- Create: `src/ai/schema.js`
- Test: `test/ai/schema.test.js`

**Interfaces:**
- Produces: `validateParams(schema, params)` → `{ ok, value, errors }`；schema 形如 `{ 参数名: { type: "string"|"int"|"stringArray", required?: boolean, min?: number, max?: number } }`

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { validateParams } from "../../src/ai/schema.js";

test("validateParams 校验必填、类型、范围", () => {
  const schema = {
    quantity: { type: "int", required: true, min: 0, max: 100000 },
    handles: { type: "stringArray", required: true, max: 50 },
    productType: { type: "string", max: 100 }
  };
  assert.deepEqual(validateParams(schema, { quantity: 100, handles: ["a", "a", "b"] }).value, {
    quantity: 100,
    handles: ["a", "b"]
  });
  assert.equal(validateParams(schema, { handles: [] }).ok, false);
  assert.equal(validateParams(schema, { quantity: "x", handles: ["a"] }).ok, false);
  assert.equal(validateParams(schema, { quantity: 999999, handles: ["a"] }).ok, true);
  assert.equal(validateParams(schema, { quantity: 999999, handles: ["a"] }).value.quantity, 100000);
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/schema.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```js
const TYPE_CHECK = {
  string: (v) => typeof v === "string" && v.trim() !== "",
  int: (v) => typeof v === "number" && Number.isInteger(v),
  stringArray: (v) => Array.isArray(v) && v.length > 0 && v.every((x) => typeof x === "string")
};

const CLAMP = {
  string: (v, field) => v.trim().slice(0, field.max ?? 2000),
  int: (v, field) => {
    let n = v;
    if (field.min !== undefined) n = Math.max(n, field.min);
    if (field.max !== undefined) n = Math.min(n, field.max);
    return n;
  },
  stringArray: (v, field) => [...new Set(v.map((x) => x.trim()).filter(Boolean))].slice(0, field.max ?? 50)
};

export function validateParams(schema, params) {
  const errors = [];
  const value = {};
  const input = params && typeof params === "object" ? params : {};
  for (const [name, field] of Object.entries(schema || {})) {
    const raw = input[name];
    if (raw === undefined || raw === null || raw === "") {
      if (field.required) errors.push(`缺少必填参数 ${name}`);
      continue;
    }
    if (!TYPE_CHECK[field.type](raw)) {
      errors.push(`参数 ${name} 类型应为 ${field.type}`);
      continue;
    }
    value[name] = CLAMP[field.type](raw, field);
  }
  return { ok: errors.length === 0, value, errors };
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node --test test/ai/schema.test.js`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/ai/schema.js test/ai/schema.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): 工具参数校验器 schema"
```

---

### Task 2: 全局记忆存储 `src/ai/memoryStore.js`

**Files:**
- Create: `src/ai/memoryStore.js`
- Test: `test/ai/memoryStore.test.js`

**Interfaces:**
- Produces: `class MemoryStore { constructor(filePath); list(); get(key); set(key, value); clear(key?) }`
  - `list()` → `[{ key, value, updatedAt }]`
  - `set(key, value)` 键匹配 `/^[\w\u4e00-\u9fa5-]{1,50}$/`，值 ≤500 字符，非法抛错

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import fs from "node:fs/promises";
import { MemoryStore } from "../../src/ai/memoryStore.js";

test("MemoryStore 读写/列出/清空", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "mem-"));
  const store = new MemoryStore(path.join(dir, "memory.json"));
  await store.set("默认库存", "100");
  await store.set("类别", "钓鱼用具");
  assert.equal(await store.get("默认库存"), "100");
  assert.equal((await store.list()).length, 2);
  await store.clear("默认库存");
  assert.equal(await store.get("默认库存"), null);
  await store.set("x", "y");
  await store.clear();
  assert.equal((await store.list()).length, 0);
  await assert.rejects(() => store.set("bad key!", "v"));
  await assert.rejects(() => store.set("ok", "v".repeat(501)));
  await fs.rm(dir, { recursive: true, force: true });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/memoryStore.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```js
import fs from "node:fs/promises";
import path from "node:path";

const KEY_RE = /^[\w\u4e00-\u9fa5-]{1,50}$/;

export class MemoryStore {
  constructor(filePath) {
    this.filePath = filePath;
  }

  async _read() {
    try {
      const raw = await fs.readFile(this.filePath, "utf8");
      const data = JSON.parse(raw);
      return data && typeof data === "object" ? data : {};
    } catch {
      return {};
    }
  }

  async _write(data) {
    await fs.mkdir(path.dirname(this.filePath), { recursive: true });
    const tmp = `${this.filePath}.tmp`;
    await fs.writeFile(tmp, JSON.stringify(data, null, 2), "utf8");
    await fs.rename(tmp, this.filePath);
  }

  async list() {
    const data = await this._read();
    return Object.entries(data).map(([key, entry]) => ({
      key,
      value: entry.value,
      updatedAt: entry.updatedAt
    }));
  }

  async get(key) {
    const data = await this._read();
    return data[key] ? data[key].value : null;
  }

  async set(key, value) {
    if (!KEY_RE.test(key)) throw new Error("记忆键不合法");
    if (typeof value !== "string" || value.length > 500) {
      throw new Error("记忆值需为不超过 500 字符的字符串");
    }
    const data = await this._read();
    data[key] = { value, updatedAt: new Date().toISOString() };
    await this._write(data);
    return data[key];
  }

  async clear(key) {
    const data = await this._read();
    if (key === undefined) {
      await this._write({});
      return "已清空全部记忆";
    }
    const existed = key in data;
    delete data[key];
    await this._write(data);
    return existed ? "已删除" : "键不存在";
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node --test test/ai/memoryStore.test.js`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/ai/memoryStore.js test/ai/memoryStore.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): 全局记忆存储"
```

---

### Task 3: 会话存储与上下文 `src/ai/sessionStore.js`

**Files:**
- Create: `src/ai/sessionStore.js`
- Test: `test/ai/sessionStore.test.js`

**Interfaces:**
- Produces: `class SessionStore { constructor(dir); create(); appendMessage(id, msg); readMessages(id); setSummary(id, text); getSummary(id); clear(id); buildContext(id, extra?) }`
  - `appendMessage` 的 msg 为 `{ role: "user"|"assistant", content }`
  - `buildContext(id, extra)` → `{ messages, truncated }`，保留最近 20 条；有摘要时在最前插入 `{ role: "system", content: "会话摘要：..." }`

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import fs from "node:fs/promises";
import { SessionStore } from "../../src/ai/sessionStore.js";

test("SessionStore 持久化与上下文裁剪", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "sess-"));
  const store = new SessionStore(path.join(dir, "sessions"));
  const id = await store.create();
  for (let i = 0; i < 25; i += 1) {
    await store.appendMessage(id, { role: "user", content: `m${i}` });
  }
  const ctx = await store.buildContext(id);
  assert.equal(ctx.truncated, true);
  assert.equal(ctx.messages.length, 20);
  await store.setSummary(id, "前面聊了库存");
  const ctx2 = await store.buildContext(id);
  assert.equal(ctx2.messages[0].content, "会话摘要：前面聊了库存");
  await store.clear(id);
  assert.equal((await store.readMessages(id)).length, 0);
  await fs.rm(dir, { recursive: true, force: true });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/sessionStore.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```js
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

const MAX_MESSAGES = 20;

export class SessionStore {
  constructor(dir) {
    this.dir = dir;
  }

  _file(id) {
    return path.join(this.dir, `${id}.jsonl`);
  }

  _metaFile(id) {
    return path.join(this.dir, `${id}.meta.json`);
  }

  async create() {
    const id = crypto.randomUUID();
    await fs.mkdir(this.dir, { recursive: true });
    await fs.writeFile(this._file(id), "", "utf8");
    return id;
  }

  async appendMessage(id, message) {
    await fs.mkdir(this.dir, { recursive: true });
    await fs.appendFile(this._file(id), `${JSON.stringify(message)}\n`, "utf8");
  }

  async readMessages(id) {
    try {
      const raw = await fs.readFile(this._file(id), "utf8");
      const messages = [];
      for (const line of raw.split("\n")) {
        const text = line.trim();
        if (!text) continue;
        try {
          messages.push(JSON.parse(text));
        } catch {
          // 跳过损坏行
        }
      }
      return messages;
    } catch {
      return [];
    }
  }

  async setSummary(id, summary) {
    const meta = await this._readMeta(id);
    meta.summary = summary;
    await this._writeMeta(id, meta);
  }

  async getSummary(id) {
    return (await this._readMeta(id)).summary || "";
  }

  async _readMeta(id) {
    try {
      return JSON.parse(await fs.readFile(this._metaFile(id), "utf8"));
    } catch {
      return {};
    }
  }

  async _writeMeta(id, meta) {
    await fs.mkdir(this.dir, { recursive: true });
    await fs.writeFile(this._metaFile(id), JSON.stringify(meta), "utf8");
  }

  async clear(id) {
    await fs.rm(this._file(id), { force: true });
    await fs.rm(this._metaFile(id), { force: true });
  }

  async buildContext(id, extra = []) {
    const messages = await this.readMessages(id);
    const summary = await this.getSummary(id);
    let kept = messages;
    let truncated = false;
    if (messages.length > MAX_MESSAGES) {
      kept = messages.slice(-MAX_MESSAGES);
      truncated = true;
    }
    const context = [];
    if (summary) context.push({ role: "system", content: `会话摘要：${summary}` });
    context.push(...kept, ...extra);
    return { messages: context, truncated };
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node --test test/ai/sessionStore.test.js`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/ai/sessionStore.js test/ai/sessionStore.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): 会话存储与上下文裁剪"
```

---

### Task 4: Shopify 管理操作 `src/ai/shopifyTools.js`

**Files:**
- Create: `src/ai/shopifyTools.js`
- Test: `test/ai/shopifyTools.test.js`

**Interfaces:**
- Consumes: `src/config.js` 的 `appConfig()`（cfg.shopify.* 字段）
- Produces:
  - `listProducts(cfg, { query?, limit? })` → `[{ id, handle, title, status, productType, category, variants, images }]`
  - `getProductDetail(cfg, id)` → 商品含 variants
  - `setInventoryQuantity(cfg, productIds, quantity)` → `{ inventoryItemCount, quantity }`
  - `setProductType(cfg, productIds, productType)` → `{ updated }`
  - `setProductCategory(cfg, productIds, categoryId)` → `{ updated }`
  - `setProductStatus(cfg, productIds, status)` → `{ updated }`
  - `assignCollections(cfg, productIds, collectionTitles)` → `{ results }`
  - `deleteProducts(cfg, productIds)` → `{ deleted, errors }`
- 内部复用 `src/shopify.js` 的 `graphql` 不可用（未导出），本模块自带 `graphql` 与 `rest` 私有 helper（与 `shopify.js` 同构，使用同一 token/域名/版本）。

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import * as tools from "../../src/ai/shopifyTools.js";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

test("listProducts 调用 GraphQL 并归一化", async () => {
  const calls = [];
  globalThis.fetch = async (url, opts) => {
    calls.push({ url, body: JSON.parse(opts.body) });
    return jsonResponse(200, {
      data: {
        products: {
          edges: [
            {
              node: {
                id: "gid://shopify/Product/1",
                handle: "a",
                title: "A",
                status: "DRAFT",
                productType: "",
                category: { id: "c1", fullName: "Fishing" },
                variantsCount: { count: 2 },
                images: { edges: [{ node: { id: "i1" } }] }
              }
            }
          ]
        }
      }
    });
  };
  const cfg = { shopify: { storeDomain: "s.myshopify.com", accessToken: "t", apiVersion: "2026-07" } };
  const result = await tools.listProducts(cfg, { limit: 50 });
  assert.equal(result[0].title, "A");
  assert.equal(result[0].variants, 2);
  assert.equal(result[0].images, 1);
  assert.match(calls[0].url, /graphql\.json/);
  delete globalThis.fetch;
});

test("setInventoryQuantity 用 REST 设置库存", async () => {
  const responses = [
    jsonResponse(200, { data: { nodes: [{ id: "gid://shopify/Product/1", variants: { edges: [{ node: { inventoryItem: { id: "gid://shopify/InventoryItem/9" } } }] } }] } }),
    jsonResponse(200, { locations: [{ id: 7, name: "主仓" }] }),
    jsonResponse(200, { inventory_item: { id: 9 } }),
    jsonResponse(200, { inventory_level: { available: 100 } })
  ];
  globalThis.fetch = async () => responses.shift();
  const cfg = { shopify: { storeDomain: "s.myshopify.com", accessToken: "t", apiVersion: "2026-07" } };
  const r = await tools.setInventoryQuantity(cfg, ["gid://shopify/Product/1"], 100);
  assert.equal(r.inventoryItemCount, 1);
  assert.equal(r.quantity, 100);
  delete globalThis.fetch;
});

test("deleteProducts 汇总成功与错误", async () => {
  let call = 0;
  globalThis.fetch = async () => {
    call += 1;
    return jsonResponse(200, call === 1 ? { data: { productDelete: { deletedProductId: "gid://shopify/Product/1", userErrors: [] } } } : { data: { productDelete: { deletedProductId: null, userErrors: [{ message: "拒绝" }] } } });
  };
  const cfg = { shopify: { storeDomain: "s.myshopify.com", accessToken: "t", apiVersion: "2026-07" } };
  const r = await tools.deleteProducts(cfg, ["gid://shopify/Product/1", "gid://shopify/Product/2"]);
  assert.equal(r.deleted, 1);
  assert.equal(r.errors.length, 1);
  delete globalThis.fetch;
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/shopifyTools.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```js
async function graphql(cfg, query, variables = {}) {
  const url = `https://${cfg.shopify.storeDomain}/admin/api/${cfg.shopify.apiVersion}/graphql.json`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Shopify-Access-Token": cfg.shopify.accessToken
    },
    body: JSON.stringify({ query, variables })
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.errors) {
    throw new Error(JSON.stringify(payload.errors || payload, null, 2));
  }
  return payload.data;
}

async function rest(cfg, path, options = {}) {
  const url = `https://${cfg.shopify.storeDomain}/admin/api/${cfg.shopify.apiVersion}${path}`;
  const response = await fetch(url, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Shopify-Access-Token": cfg.shopify.accessToken
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { raw: text };
  }
  if (!response.ok) {
    throw new Error(`Shopify REST ${options.method || "GET"} ${path} 失败：${text.slice(0, 200)}`);
  }
  return payload;
}

export async function listProducts(cfg, { query = "", limit = 50 } = {}) {
  const data = await graphql(
    cfg,
    `query($q: String, $n: Int!) {
      products(first: $n, query: $q) {
        edges { node {
          id handle title status productType
          category { id fullName }
          variantsCount { count }
          images(first: 1) { edges { node { id } } }
        } }
      }
    }`,
    { q: query || undefined, n: Math.min(limit, 250) }
  );
  return (data.products?.edges || []).map((e) => ({
    id: e.node.id,
    handle: e.node.handle,
    title: e.node.title,
    status: e.node.status,
    productType: e.node.productType || "",
    category: e.node.category?.fullName || "",
    variants: e.node.variantsCount?.count ?? 0,
    images: e.node.images?.edges?.length ?? 0
  }));
}

export async function getProductDetail(cfg, id) {
  const data = await graphql(
    cfg,
    `query($id: ID!) {
      product(id: $id) {
        id handle title status productType tags
        category { id fullName }
        variants(first: 100) { edges { node { id title sku price inventoryItem { id } } } }
      }
    }`,
    { id }
  );
  const product = data.product;
  if (!product) throw new Error("找不到商品");
  return { ...product, variants: (product.variants?.edges || []).map((e) => e.node) };
}

async function productIdsToVariants(cfg, productIds) {
  const data = await graphql(
    cfg,
    `query($ids: [ID!]!) {
      nodes(ids: $ids) {
        ... on Product { id variants(first: 100) { edges { node { id inventoryItem { id } } } } }
      }
    }`,
    { ids: productIds }
  );
  const inventoryItemIds = [];
  for (const node of data.nodes || []) {
    for (const edge of node?.variants?.edges || []) {
      inventoryItemIds.push(edge.node.inventoryItem.id);
    }
  }
  return inventoryItemIds;
}

export async function setInventoryQuantity(cfg, productIds, quantity) {
  const inventoryItemIds = await productIdsToVariants(cfg, productIds);
  const locations = await rest(cfg, "/locations.json");
  const locationId = locations.locations?.[0]?.id;
  if (!locationId) throw new Error("店铺没有可用的库存地点");
  for (const itemId of inventoryItemIds) {
    await rest(cfg, `/inventory_items/${itemId}.json`, {
      method: "PUT",
      body: { inventory_item: { tracked: true } }
    });
    await rest(cfg, "/inventory_levels/set.json", {
      method: "POST",
      body: { location_id: locationId, inventory_item_id: itemId, available: quantity }
    });
  }
  return { inventoryItemCount: inventoryItemIds.length, quantity };
}

async function updateField(cfg, productIds, field, value) {
  let updated = 0;
  for (const id of productIds) {
    const data = await graphql(
      cfg,
      `mutation($id: ID!, $v: String!) {
        productUpdate(input: { id: $id, ${field}: $v }) { userErrors { field message } }
      }`,
      { id, v: value }
    );
    const errors = data.productUpdate?.userErrors || [];
    if (errors.length) throw new Error(errors.map((e) => e.message).join("; "));
    updated += 1;
  }
  return { updated };
}

export function setProductType(cfg, productIds, productType) {
  return updateField(cfg, productIds, "productType", productType);
}

export function setProductStatus(cfg, productIds, status) {
  return updateField(cfg, productIds, "status", status);
}

export async function setProductCategory(cfg, productIds, categoryId) {
  let updated = 0;
  for (const id of productIds) {
    const data = await graphql(
      cfg,
      `mutation($id: ID!, $c: ID!) {
        productUpdate(input: { id: $id, category: $c }) { userErrors { field message } }
      }`,
      { id, c: categoryId }
    );
    const errors = data.productUpdate?.userErrors || [];
    if (errors.length) throw new Error(errors.map((e) => e.message).join("; "));
    updated += 1;
  }
  return { updated };
}

export async function assignCollections(cfg, productIds, collectionTitles) {
  const data = await graphql(
    cfg,
    `query { collections(first: 50) { edges { node { id title } } } }`
  );
  const byTitle = new Map((data.collections?.edges || []).map((e) => [e.node.title, e.node.id]));
  const results = [];
  for (const title of collectionTitles) {
    const collectionId = byTitle.get(title);
    if (!collectionId) {
      results.push({ collection: title, added: 0, error: "集合不存在" });
      continue;
    }
    const r = await graphql(
      cfg,
      `mutation($id: ID!, $pids: [ID!]!) {
        collectionAddProducts(id: $id, productIds: $pids) { userErrors { field message } }
      }`,
      { id: collectionId, pids: productIds }
    );
    const errors = r.collectionAddProducts?.userErrors || [];
    results.push({
      collection: title,
      added: productIds.length,
      error: errors.length ? errors.map((e) => e.message).join("; ") : ""
    });
  }
  return { results };
}

export async function deleteProducts(cfg, productIds) {
  let deleted = 0;
  const errors = [];
  for (const id of productIds) {
    try {
      const data = await graphql(
        cfg,
        `mutation($id: ID!) {
          productDelete(id: $id) { deletedProductId userErrors { field message } }
        }`,
        { id }
      );
      const errs = data.productDelete?.userErrors || [];
      if (errs.length) errors.push(errs.map((e) => e.message).join("; "));
      else deleted += 1;
    } catch (error) {
      errors.push(error.message);
    }
  }
  return { deleted, errors };
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node --test test/ai/shopifyTools.test.js`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/ai/shopifyTools.js test/ai/shopifyTools.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): Shopify 管理操作（库存/类别/集合/删除等）"
```

---

### Task 5: 工具注册表 `src/ai/tools.js`

**Files:**
- Create: `src/ai/tools.js`
- Test: `test/ai/tools.test.js`

**Interfaces:**
- Consumes: `validateParams`（Task 1）、`MemoryStore`（Task 2）、`shopifyTools`（Task 4）、`src/shopify.js` 的 `createShopifyProduct`
- Produces:
  - `TOOL_DEFINITIONS`（OpenAI function schema 数组，供 LLM 使用）
  - `TOOLS`（`{ [name]: { handler(args, ctx), requiresConfirmation?, paramsSchema } }`）
  - `runTool(name, args, ctx)` → `{ ok, data?, error? }`；未注册工具返回 `{ ok: false, error: "未知工具..." }`
  - ctx = `{ cfg, getBatch(id), memory: MemoryStore, shopify: shopifyTools }`

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { runTool, TOOLS, TOOL_DEFINITIONS } from "../../src/ai/tools.js";

const memory = {
  list: async () => [{ key: "库存", value: "100", updatedAt: "x" }],
  get: async () => "100",
  set: async (k, v) => ({ key: k, value: v }),
  clear: async () => "ok"
};

const shopify = {
  listProducts: async () => [{ id: "gid://shopify/Product/1", handle: "rod", title: "Rod" }],
  createShopifyProduct: async (cfg, product) => ({ id: "p1", title: product.title, variantCount: 1, imageCount: 0 }),
  setInventoryQuantity: async (cfg, ids, quantity) => ({ inventoryItemCount: ids.length, quantity }),
  setProductType: async () => ({ updated: 1 }),
  setProductCategory: async () => ({ updated: 1 }),
  setProductStatus: async () => ({ updated: 1 }),
  assignCollections: async () => ({ results: [] }),
  deleteProducts: async () => ({ deleted: 1, errors: [] })
};

const ctx = { cfg: {}, getBatch: () => ({ products: [{ id: "1", title: "T" }] }), memory, shopify };

test("未注册工具被拒绝", async () => {
  const r = await runTool("read_c_drive", {}, ctx);
  assert.equal(r.ok, false);
  assert.match(r.error, /未知工具/);
});

test("参数校验失败被拒绝", async () => {
  const r = await runTool("set_inventory", { handles: [], quantity: 100 }, ctx);
  assert.equal(r.ok, false);
});

test("memory_set 写入记忆", async () => {
  const r = await runTool("memory_set", { key: "默认库存", value: "100" }, ctx);
  assert.equal(r.ok, true);
});

test("delete_products 标记需要确认", () => {
  assert.equal(TOOLS.delete_products.requiresConfirmation, true);
  assert.equal(TOOLS.publish_products.requiresConfirmation, true);
});

test("create_products 创建草稿商品", async () => {
  const r = await runTool("create_products", { batchId: "b1", includeSkuImages: true }, ctx);
  assert.equal(r.ok, true);
  assert.equal(r.data.ok, 1);
});

test("TOOL_DEFINITIONS 覆盖全部 TOOLS", () => {
  const names = new Set(TOOL_DEFINITIONS.map((d) => d.function.name));
  for (const name of Object.keys(TOOLS)) assert.ok(names.has(name));
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/tools.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```js
import { validateParams } from "./schema.js";
import { createShopifyProduct } from "../shopify.js";
import * as shopifyTools from "./shopifyTools.js";

export const FISHING_CATEGORY_ID = "gid://shopify/TaxonomyCategory/sg-4-6";

const params = {
  batchId: { type: "string", required: true },
  handles: { type: "stringArray", required: true, max: 50 },
  quantity: { type: "int", required: true, min: 0, max: 100000 },
  productType: { type: "string", max: 100 },
  categoryId: { type: "string", max: 200 },
  collections: { type: "stringArray", required: true, max: 20 },
  query: { type: "string", max: 200 },
  limit: { type: "int", min: 1, max: 250 },
  key: { type: "string", max: 50 },
  value: { type: "string", max: 500 },
  includeSkuImages: { type: "string" }
};

async function resolveProductIds(ctx, handles) {
  const products = await ctx.shopify.listProducts(ctx.cfg, { limit: 250 });
  const byHandle = new Map(products.map((p) => [p.handle, p.id]));
  const ids = [];
  const missing = [];
  for (const handle of handles) {
    const id = byHandle.get(handle);
    if (id) ids.push(id);
    else missing.push(handle);
  }
  return { ids, missing };
}

const handlers = {
  async get_batch_summary(args, ctx) {
    const batch = ctx.getBatch(args.batchId);
    if (!batch) throw new Error("找不到批次，请先上传 Excel");
    return {
      id: batch.id,
      fileName: batch.fileName,
      summary: batch.summary,
      products: batch.products.map((p) => ({
        id: p.id,
        title: p.title,
        variants: p.variants.length,
        errors: p.errors,
        warnings: p.warnings
      }))
    };
  },

  async list_products(args, ctx) {
    return ctx.shopify.listProducts(ctx.cfg, { query: args.query || "", limit: args.limit || 50 });
  },

  async get_product_detail(args, ctx) {
    const list = await ctx.shopify.listProducts(ctx.cfg, { limit: 250 });
    const hit = list.find((p) => p.handle === args.handles[0] || p.id === args.handles[0]);
    if (!hit) throw new Error("找不到商品");
    return ctx.shopify.getProductDetail(ctx.cfg, hit.id);
  },

  async create_products(args, ctx) {
    const batch = ctx.getBatch(args.batchId);
    if (!batch) throw new Error("找不到批次，请先上传 Excel");
    const products =
      args.includeSkuImages === "false"
        ? batch.products.map((p) => ({
            ...p,
            variants: p.variants.map((v) => ({ ...v, skuImageFilePath: undefined, skuImage: undefined }))
          }))
        : batch.products;
    const results = [];
    for (const product of products) {
      try {
        const created = await ctx.shopify.createShopifyProduct(ctx.cfg, product, { status: "DRAFT" });
        results.push({ id: product.id, title: product.title, ok: true, shopify: created });
      } catch (error) {
        results.push({ id: product.id, title: product.title, ok: false, error: error.message });
      }
    }
    return {
      productCount: products.length,
      ok: results.filter((r) => r.ok).length,
      failed: results.filter((r) => !r.ok).length,
      results
    };
  },

  async set_inventory(args, ctx) {
    const { ids, missing } = await resolveProductIds(ctx, args.handles);
    if (!ids.length) throw new Error(`找不到商品：${missing.join(", ")}`);
    const result = await ctx.shopify.setInventoryQuantity(ctx.cfg, ids, args.quantity);
    return { ...result, missing };
  },

  async set_product_type(args, ctx) {
    const { ids, missing } = await resolveProductIds(ctx, args.handles);
    if (!ids.length) throw new Error(`找不到商品：${missing.join(", ")}`);
    return { ...(await ctx.shopify.setProductType(ctx.cfg, ids, args.productType)), missing };
  },

  async set_product_category(args, ctx) {
    const { ids, missing } = await resolveProductIds(ctx, args.handles);
    if (!ids.length) throw new Error(`找不到商品：${missing.join(", ")}`);
    const categoryId = args.categoryId || FISHING_CATEGORY_ID;
    return { ...(await ctx.shopify.setProductCategory(ctx.cfg, ids, categoryId)), categoryId, missing };
  },

  async assign_collections(args, ctx) {
    const { ids, missing } = await resolveProductIds(ctx, args.handles);
    if (!ids.length) throw new Error(`找不到商品：${missing.join(", ")}`);
    return { ...(await ctx.shopify.assignCollections(ctx.cfg, ids, args.collections)), missing };
  },

  async delete_products(args, ctx) {
    const { ids, missing } = await resolveProductIds(ctx, args.handles);
    if (!ids.length) throw new Error(`找不到商品：${missing.join(", ")}`);
    return { ...(await ctx.shopify.deleteProducts(ctx.cfg, ids)), missing };
  },

  async publish_products(args, ctx) {
    const { ids, missing } = await resolveProductIds(ctx, args.handles);
    if (!ids.length) throw new Error(`找不到商品：${missing.join(", ")}`);
    return { ...(await ctx.shopify.setProductStatus(ctx.cfg, ids, "ACTIVE")), missing };
  },

  async memory_get(args, ctx) {
    return { key: args.key || null, value: args.key ? await ctx.memory.get(args.key) : null };
  },

  async memory_set(args, ctx) {
    return ctx.memory.set(args.key, args.value);
  },

  async memory_list(args, ctx) {
    return { memories: await ctx.memory.list() };
  },

  async memory_clear(args, ctx) {
    return { result: await ctx.memory.clear(args.key) };
  }
};

const paramSchemas = {
  get_batch_summary: { batchId: params.batchId },
  list_products: { query: params.query, limit: params.limit },
  get_product_detail: { handles: params.handles },
  create_products: { batchId: params.batchId, includeSkuImages: params.includeSkuImages },
  set_inventory: { handles: params.handles, quantity: params.quantity },
  set_product_type: { handles: params.handles, productType: params.productType },
  set_product_category: { handles: params.handles, categoryId: params.categoryId },
  assign_collections: { handles: params.handles, collections: params.collections },
  delete_products: { handles: params.handles },
  publish_products: { handles: params.handles },
  memory_get: { key: params.key },
  memory_set: { key: params.key, value: params.value },
  memory_list: {},
  memory_clear: { key: params.key }
};

export const TOOLS = {};
for (const [name, handler] of Object.entries(handlers)) {
  TOOLS[name] = {
    handler,
    paramsSchema: paramSchemas[name],
    requiresConfirmation: name === "delete_products" || name === "publish_products"
  };
}

const descriptions = {
  get_batch_summary: "查看已上传 Excel 批次的汇总与商品列表",
  list_products: "列出店铺商品（可按标题/状态查询）",
  get_product_detail: "查看某个商品的变体、SKU、价格、库存、类别详情",
  create_products: "把已上传批次的商品创建到 Shopify（固定草稿 DRAFT，可含 SKU 图片）",
  set_inventory: "设置商品全部变体的库存数量",
  set_product_type: "设置商品的产品类型（空字符串表示清除）",
  set_product_category: "设置商品的标准分类（默认钓鱼分类）",
  assign_collections: "把商品加入指定集合（按集合标题）",
  delete_products: "删除商品（高风险，需用户确认）",
  publish_products: "把商品公开上架为 ACTIVE（高风险，需用户确认）",
  memory_get: "读取一条长期偏好记忆",
  memory_set: "写入一条长期偏好记忆",
  memory_list: "列出全部长期偏好记忆",
  memory_clear: "清除一条或全部长期偏好记忆"
};

const TYPE_TO_JSON = {
  string: { type: "string" },
  int: { type: "integer" },
  stringArray: { type: "array", items: { type: "string" } }
};

export const TOOL_DEFINITIONS = Object.entries(handlers).map(([name]) => {
  const schema = paramSchemas[name] || {};
  const properties = {};
  const required = [];
  for (const [paramName, field] of Object.entries(schema)) {
    properties[paramName] = TYPE_TO_JSON[field.type];
    if (field.required) required.push(paramName);
  }
  return {
    type: "function",
    function: {
      name,
      description: descriptions[name],
      parameters: { type: "object", properties, required }
    }
  };
});

export async function runTool(name, args, ctx) {
  const tool = TOOLS[name];
  if (!tool) return { ok: false, error: "未知工具，不在能力范围内" };
  const check = validateParams(tool.paramsSchema, args);
  if (!check.ok) return { ok: false, error: `参数校验失败：${check.errors.join("；")}` };
  try {
    const data = await tool.handler(check.value, ctx);
    return { ok: true, data };
  } catch (error) {
    return { ok: false, error: error.message };
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node --test test/ai/tools.test.js`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/ai/tools.js test/ai/tools.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): 工具白名单注册表"
```

---

### Task 6: DeepSeek 客户端 `src/ai/llmClient.js`

**Files:**
- Create: `src/ai/llmClient.js`
- Test: `test/ai/llmClient.test.js`

**Interfaces:**
- Consumes: `appConfig()` 的 `cfg.ai.{ baseUrl, apiKey, chatModel }`
- Produces: `createLlm(cfg, client?)` → `{ streamChat(messages, tools), summarize(messages) }`
  - `streamChat` 返回 OpenAI 流式响应（可异步迭代）
  - 未配置 key 时抛错 `"未配置 AI_API_KEY"`

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { createLlm } from "../../src/ai/llmClient.js";

test("未配置 key 抛错", () => {
  assert.throws(() => createLlm({ ai: { apiKey: "", baseUrl: "https://api.deepseek.com", chatModel: "deepseek-chat" } }), /AI_API_KEY/);
});

test("streamChat 透传模型与 tools 并流式返回", async () => {
  const calls = [];
  const fakeClient = {
    chat: {
      completions: {
        create: async (opts) => {
          calls.push(opts);
          return {
            async *[Symbol.asyncIterator]() {
              yield { choices: [{ delta: { content: "你" } }] };
              yield { choices: [{ delta: { content: "好" } }] };
            }
          };
        }
      }
    }
  };
  const llm = createLlm({ ai: { apiKey: "k", baseUrl: "https://api.deepseek.com", chatModel: "deepseek-chat" } }, fakeClient);
  const stream = await llm.streamChat([{ role: "user", content: "hi" }], [{ type: "function" }]);
  let text = "";
  for await (const chunk of stream) text += chunk.choices[0].delta.content;
  assert.equal(text, "你好");
  assert.equal(calls[0].model, "deepseek-chat");
  assert.equal(calls[0].stream, true);
  assert.equal(calls[0].tools.length, 1);
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/llmClient.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```js
import OpenAI from "openai";

export function createLlm(cfg, client) {
  if (!cfg.ai.apiKey) throw new Error("未配置 AI_API_KEY，请在 .env 中填写");
  const openai =
    client ||
    new OpenAI({
      apiKey: cfg.ai.apiKey,
      baseURL: cfg.ai.baseUrl || "https://api.deepseek.com"
    });
  return {
    async streamChat(messages, tools) {
      return openai.chat.completions.create({
        model: cfg.ai.chatModel,
        messages,
        tools: tools && tools.length ? tools : undefined,
        stream: true
      });
    },
    async summarize(messages) {
      const response = await openai.chat.completions.create({
        model: cfg.ai.chatModel,
        messages: [
          { role: "system", content: "把以下对话压缩成简洁的中文摘要，保留关键事实与用户偏好，不超过 300 字。" },
          ...messages
        ],
        max_tokens: 400
      });
      return response.choices?.[0]?.message?.content || "";
    }
  };
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node --test test/ai/llmClient.test.js`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/ai/llmClient.js test/ai/llmClient.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): DeepSeek 客户端（流式+摘要）"
```

---

### Task 7: 聊天控制器 `src/ai/chatController.js`

**Files:**
- Create: `src/ai/chatController.js`
- Test: `test/ai/chatController.test.js`

**Interfaces:**
- Consumes: `TOOL_DEFINITIONS/TOOLS/runTool`（Task 5）、`createLlm`（Task 6）、`SessionStore`（Task 3）、`MemoryStore`（Task 2）
- Produces: `class ChatController { constructor({ cfg, llm, sessionStore, memoryStore, getBatch, toolRunner? }); async handle({ sessionId, message, confirm, onEvent }) }`
  - onEvent 事件：`{ type: "text", delta }`、`{ type: "tool", name, status, result? }`、`{ type: "confirmation", name, args, summary }`、`{ type: "note", text }`、`{ type: "done", text }`、`{ type: "error", error }`

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { ChatController } from "../../src/ai/chatController.js";

function fakeStore() {
  const messages = [];
  return {
    create: async () => "s1",
    appendMessage: async (id, m) => messages.push(m),
    readMessages: async () => messages,
    setSummary: async () => {},
    getSummary: async () => "",
    clear: async () => {},
    buildContext: async () => ({ messages: [...messages], truncated: false })
  };
}

function fakeLlm(script) {
  let calls = 0;
  return {
    streamChat: async (messages) => {
      const step = script[Math.min(calls, script.length - 1)];
      calls += 1;
      return {
        async *[Symbol.asyncIterator]() {
          for (const chunk of step(messages)) yield chunk;
        }
      };
    }
  };
}

test("普通回复：文本流式返回", async () => {
  const events = [];
  const llm = fakeLlm([
    () => [{ choices: [{ delta: { content: "你好" } }] }]
  ]);
  const c = new ChatController({ cfg: { ai: { chatModel: "m" } }, llm, sessionStore: fakeStore(), memoryStore: { list: async () => [] } });
  await c.handle({ sessionId: "s1", message: "你好", onEvent: (e) => events.push(e) });
  assert.equal(events.find((e) => e.type === "done").text, "你好");
});

test("工具调用：memory_set 被执行并回填", async () => {
  const events = [];
  const llm = fakeLlm([
    () => [{ choices: [{ delta: { tool_calls: [{ index: 0, id: "c1", function: { name: "memory_set", arguments: JSON.stringify({ key: "库存", value: "100" }) } }] } }] }],
    (messages) => {
      assert.ok(JSON.stringify(messages).includes("库存"));
      return [{ choices: [{ delta: { content: "记住了" } }] }];
    }
  ]);
  const memory = {
    list: async () => [],
    set: async (k, v) => ({ key: k, value: v })
  };
  const c = new ChatController({ cfg: { ai: { chatModel: "m" } }, llm, sessionStore: fakeStore(), memoryStore: memory });
  await c.handle({ sessionId: "s1", message: "记住库存100", onEvent: (e) => events.push(e) });
  assert.equal(events.find((e) => e.type === "tool").status, "ok");
  assert.equal(events.find((e) => e.type === "done").text, "记住了");
});

test("确认门：delete_products 先确认后执行", async () => {
  const events = [];
  const executed = [];
  const llm = fakeLlm([
    () => [{ choices: [{ delta: { tool_calls: [{ index: 0, id: "c1", function: { name: "delete_products", arguments: JSON.stringify({ handles: ["rod"] }) } }] } }] }]
  ]);
  const c = new ChatController({
    cfg: { ai: { chatModel: "m" } },
    llm,
    sessionStore: fakeStore(),
    memoryStore: { list: async () => [] },
    toolRunner: async (name, args) => {
      executed.push(name);
      return { ok: true, data: { deleted: 1 } };
    }
  });
  await c.handle({ sessionId: "s1", message: "删掉 rod", onEvent: (e) => events.push(e) });
  assert.equal(executed.length, 0);
  assert.equal(events.find((e) => e.type === "confirmation").name, "delete_products");
  await c.handle({ sessionId: "s1", confirm: "confirm", onEvent: (e) => events.push(e) });
  assert.deepEqual(executed, ["delete_products"]);
});

test("确认门：取消不执行", async () => {
  const events = [];
  const executed = [];
  const llm = fakeLlm([
    () => [{ choices: [{ delta: { tool_calls: [{ index: 0, id: "c1", function: { name: "delete_products", arguments: "{}" } }] } }] }]
  ]);
  const c = new ChatController({
    cfg: { ai: { chatModel: "m" } },
    llm,
    sessionStore: fakeStore(),
    memoryStore: { list: async () => [] },
    toolRunner: async (name) => { executed.push(name); return { ok: true, data: {} }; }
  });
  await c.handle({ sessionId: "s1", message: "删", onEvent: () => {} });
  await c.handle({ sessionId: "s1", confirm: "cancel", onEvent: (e) => events.push(e) });
  assert.equal(executed.length, 0);
  assert.ok(events.some((e) => e.type === "note" && e.text.includes("取消")));
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/chatController.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```js
import { TOOLS, TOOL_DEFINITIONS, runTool } from "./tools.js";

const MAX_TOOL_ITERATIONS = 10;

export class ChatController {
  constructor({ cfg, llm, sessionStore, memoryStore, getBatch, toolRunner }) {
    this.cfg = cfg;
    this.llm = llm;
    this.sessions = sessionStore;
    this.memory = memoryStore;
    this.getBatch = getBatch || (() => undefined);
    this.toolRunner = toolRunner || runTool;
    this.pending = new Map();
  }

  async systemPrompt() {
    const memories = await this.memory.list();
    const memoryText = memories.length
      ? "用户长期偏好：\n" + memories.map((m) => `- ${m.key}: ${m.value}`).join("\n")
      : "（暂无长期偏好记忆）";
    return [
      "你是这个 Shopify 批量上货工具里的 AI 助手，只负责上货与商品管理：解析 Excel、创建草稿商品、修改库存/类别/产品类型/集合、删除商品、公开上架、查询商品与批次、管理长期记忆。",
      "删除商品、公开上架必须等待用户确认（工具会触发确认卡片），确认前绝不执行。",
      "除此之外的请求（读取电脑文件、访问网站、执行命令、写代码、闲聊无关话题等）一律礼貌拒绝，并说明不在能力范围内。",
      "回答使用中文，简洁直接。",
      memoryText
    ].join("\n");
  }

  async _ctx() {
    return {
      cfg: this.cfg,
      getBatch: this.getBatch,
      memory: this.memory,
      shopify: (await import("./shopifyTools.js"))
    };
  }

  async handle({ sessionId, message, confirm, onEvent }) {
    const emit = onEvent || (() => {});
    if (!this.llm) {
      emit({ type: "error", error: "未配置 AI_API_KEY，请在 .env 中填写" });
      return;
    }
    if (confirm === "confirm" || confirm === "cancel") {
      await this._handleConfirm(sessionId, confirm, emit);
      return;
    }
    if (!message || !message.trim()) {
      emit({ type: "error", error: "消息不能为空" });
      return;
    }
    await this.sessions.appendMessage(sessionId, { role: "user", content: message });
    const system = await this.systemPrompt();
    const { messages } = await this.sessions.buildContext(sessionId);
    await this._loop([{ role: "system", content: system }, ...messages], sessionId, emit, 0);
  }

  async _handleConfirm(sessionId, confirm, emit) {
    const pending = this.pending.get(sessionId);
    if (!pending) {
      emit({ type: "error", error: "当前没有待确认的操作" });
      return;
    }
    this.pending.delete(sessionId);
    if (confirm === "cancel") {
      await this.sessions.appendMessage(sessionId, { role: "assistant", content: "已取消该操作。" });
      emit({ type: "note", text: "已取消该操作" });
      emit({ type: "done", text: "已取消该操作。" });
      return;
    }
    const ctx = await this._ctx();
    emit({ type: "tool", name: pending.name, status: "running" });
    const result = await this.toolRunner(pending.name, pending.args, ctx);
    emit({ type: "tool", name: pending.name, status: result.ok ? "ok" : "error", result: result.ok ? result.data : result.error });
    await this.sessions.appendMessage(sessionId, {
      role: "user",
      content: `（用户已确认）工具 ${pending.name} 执行结果：${result.ok ? JSON.stringify(result.data) : result.error}`
    });
    const system = await this.systemPrompt();
    const { messages } = await this.sessions.buildContext(sessionId);
    await this._loop([{ role: "system", content: system }, ...messages], sessionId, emit, 0);
  }

  async _loop(llmMessages, sessionId, emit, iteration) {
    if (iteration >= MAX_TOOL_ITERATIONS) {
      emit({ type: "note", text: "已达到最大工具调用次数，停止。" });
      return;
    }
    const toolCalls = [];
    let text = "";
    let stream;
    try {
      stream = await this.llm.streamChat(llmMessages, TOOL_DEFINITIONS);
    } catch (error) {
      emit({ type: "error", error: `AI 调用失败：${error.message}` });
      return;
    }
    for await (const chunk of stream) {
      const delta = chunk.choices?.[0]?.delta;
      if (delta?.content) {
        text += delta.content;
        emit({ type: "text", delta: delta.content });
      }
      for (const tc of delta?.tool_calls || []) {
        const existing = toolCalls.find((t) => t.index === tc.index);
        if (existing) {
          if (tc.function?.name) existing.name += tc.function.name;
          if (tc.function?.arguments) existing.arguments += tc.function.arguments;
          if (tc.id) existing.id = tc.id;
        } else {
          toolCalls.push({
            index: tc.index,
            id: tc.id || "",
            name: tc.function?.name || "",
            arguments: tc.function?.arguments || ""
          });
        }
      }
    }
    const calls = toolCalls.filter((t) => t.name);
    if (!calls.length) {
      await this.sessions.appendMessage(sessionId, { role: "assistant", content: text });
      emit({ type: "done", text });
      return;
    }
    const ctx = await this._ctx();
    for (const call of calls) {
      let args = {};
      try {
        args = call.arguments ? JSON.parse(call.arguments) : {};
      } catch {
        args = {};
      }
      const tool = TOOLS[call.name];
      if (!tool) {
        llmMessages.push({ role: "tool", tool_call_id: call.id, content: "错误：未知工具，不在能力范围内" });
        emit({ type: "tool", name: call.name, status: "error", result: "未知工具" });
        continue;
      }
      if (tool.requiresConfirmation) {
        this.pending.set(sessionId, { name: call.name, args });
        emit({
          type: "confirmation",
          name: call.name,
          args,
          summary: call.name === "delete_products" ? `将删除 ${args.handles?.length || 0} 个商品` : `将公开 ${args.handles?.length || 0} 个商品`
        });
        return;
      }
      emit({ type: "tool", name: call.name, status: "running" });
      const result = await this.toolRunner(call.name, args, ctx);
      llmMessages.push({
        role: "tool",
        tool_call_id: call.id,
        content: result.ok ? JSON.stringify(result.data) : `错误：${result.error}`
      });
      emit({ type: "tool", name: call.name, status: result.ok ? "ok" : "error", result: result.ok ? result.data : result.error });
    }
    await this._loop(llmMessages, sessionId, emit, iteration + 1);
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node --test test/ai/chatController.test.js`
Expected: PASS（工具调用测试依赖 `_ctx()` 动态 import；controller 测试中 `toolRunner` 被注入，不真正执行 shopifyTools）

- [ ] **Step 5: 提交**

```bash
git add src/ai/chatController.js test/ai/chatController.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): 聊天控制器与确认门"
```

---

### Task 8: 服务端接入（config + 路由 + 本地监听）

**Files:**
- Modify: `src/config.js`（新增 `cfg.ai`）、`src/server.js`（挂载 `/api/chat`、`/api/chat/upload`、`/api/memory`、`/api/chat/clear`，监听 127.0.0.1）
- Modify: `.env.example`（新增 AI 配置示例）
- Test: `test/ai/config.test.js`

**Interfaces:**
- Produces: `cfg.ai = { baseUrl, apiKey, chatModel, contextMaxTokens }`
- `POST /api/chat` body `{ sessionId?, message?, confirm? }` → SSE；`POST /api/chat/upload`（multipart file）→ `{ batchId, summary }`；`GET /api/memory` → 列表；`DELETE /api/memory?key=` → 删除；`POST /api/chat/clear` body `{ sessionId }` → `{ ok: true }`

- [ ] **Step 1: 写失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { appConfig } from "../../src/config.js";

test("appConfig 提供 AI 配置默认值", () => {
  const cfg = appConfig();
  assert.equal(cfg.ai.baseUrl, "https://api.deepseek.com");
  assert.equal(cfg.ai.chatModel, "deepseek-chat");
  assert.equal(cfg.ai.contextMaxTokens, 12000);
});
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test test/ai/config.test.js`
Expected: FAIL（`cfg.ai` 为 undefined）

- [ ] **Step 3: 修改 config.js**

在 `appConfig()` 返回值中加入：

```js
    ai: {
      baseUrl: process.env.AI_BASE_URL || "https://api.deepseek.com",
      apiKey: process.env.AI_API_KEY || "",
      chatModel: process.env.AI_CHAT_MODEL || "deepseek-chat",
      contextMaxTokens: Number(process.env.AI_CONTEXT_MAX_TOKENS || 12000)
    },
```

- [ ] **Step 4: 修改 server.js**

在 import 区加入：

```js
import { SessionStore } from "./ai/sessionStore.js";
import { MemoryStore } from "./ai/memoryStore.js";
import { createLlm } from "./ai/llmClient.js";
import { ChatController } from "./ai/chatController.js";
import { runTool } from "./ai/tools.js";
```

在 `const upload = multer(...)` 之后初始化：

```js
const chatSessions = new SessionStore(path.join(paths.data, "chat", "sessions"));
const memoryStore = new MemoryStore(path.join(paths.data, "chat", "memory.json"));
const chatController = new ChatController({
  cfg,
  llm: cfg.ai.apiKey ? createLlm(cfg) : null,
  sessionStore: chatSessions,
  memoryStore,
  getBatch: (id) => batches.get(id),
  toolRunner: runTool
});
```

在 `app.listen` 前加入路由：

```js
app.post("/api/chat", async (req, res) => {
  if (!cfg.ai.apiKey) {
    res.status(400).json({ error: "未配置 AI_API_KEY，请在 .env 中填写" });
    return;
  }
  const { sessionId, message, confirm } = req.body || {};
  const sid = sessionId || (await chatSessions.create());
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();
  const onEvent = (event) => {
    res.write(`data: ${JSON.stringify(event)}\n\n`);
  };
  try {
    await chatController.handle({ sessionId: sid, message, confirm, onEvent });
  } catch (error) {
    onEvent({ type: "error", error: error.message || "请求失败" });
  }
  res.end();
});

app.post("/api/chat/upload", upload.single("file"), async (req, res, next) => {
  try {
    if (!req.file) throw new Error("请上传 xlsx 文件。");
    const fieldMap = readFieldMap();
    const parsed = await parseWorkbook(req.file.path, fieldMap);
    const products = mapRowsToProducts(parsed, fieldMap, {
      vendor: cfg.shopify.defaultVendor,
      status: cfg.shopify.defaultStatus,
      optionName: cfg.shopify.defaultOptionName
    });
    const id = crypto.randomUUID();
    const extractedImages = await extractCellImages(req.file.path, products, path.join(paths.uploads, id));
    const batch = {
      id,
      fileName: req.file.originalname,
      uploadedPath: req.file.path,
      parsed: { sheetNames: parsed.sheetNames, selectedSheet: parsed.selectedSheet, headers: parsed.headers },
      extractedImages,
      products,
      summary: summarizeBatch(products),
      createdAt: new Date().toISOString()
    };
    batches.set(id, batch);
    res.json({ batchId: id, fileName: req.file.originalname, summary: batch.summary });
  } catch (error) {
    next(error);
  }
});

app.get("/api/memory", async (_req, res, next) => {
  try {
    res.json({ memories: await memoryStore.list() });
  } catch (error) {
    next(error);
  }
});

app.delete("/api/memory", async (req, res, next) => {
  try {
    const key = typeof req.query.key === "string" ? req.query.key : undefined;
    res.json({ result: await memoryStore.clear(key) });
  } catch (error) {
    next(error);
  }
});

app.post("/api/chat/clear", async (req, res, next) => {
  try {
    const { sessionId } = req.body || {};
    if (!sessionId) throw new Error("缺少 sessionId");
    await chatSessions.clear(sessionId);
    res.json({ ok: true });
  } catch (error) {
    next(error);
  }
});
```

把 `app.listen` 改为：

```js
app.listen(cfg.port, "127.0.0.1", () => {
  console.log(`Shopify bulk uploader running at http://localhost:${cfg.port}`);
});
```

修改 `.env.example`，追加：

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=sk-xxxxxxxxxxxxxxxx
AI_CHAT_MODEL=deepseek-chat
AI_CONTEXT_MAX_TOKENS=12000
```

- [ ] **Step 5: 运行确认通过**

Run: `node --test test/ai/config.test.js`
Expected: PASS

- [ ] **Step 6: 手动冒烟**

Run: `npm test`
Expected: 全部既有测试 + 新增测试通过

- [ ] **Step 7: 提交**

```bash
git add src/config.js src/server.js .env.example test/ai/config.test.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): 服务端路由与配置接入"
```

---

### Task 9: 前端聊天侧边栏

**Files:**
- Modify: `public/index.html`、`public/styles.css`
- Create: `public/chat.js`

**Interfaces:**
- `POST /api/chat`（SSE 流式）、`POST /api/chat/upload`、`GET /api/memory`、`DELETE /api/memory?key=`、`POST /api/chat/clear`

- [ ] **Step 1: 修改 index.html**

在 `<main class="app">` 内部末尾、`</main>` 之前加入侧边栏容器；在 `</body>` 前引入脚本：

```html
      <aside id="chatPanel" class="chat-panel">
        <header class="chat-header">
          <h2>AI 上货助手</h2>
          <div class="chat-header-actions">
            <button id="memoryBtn" title="记忆管理">记忆</button>
            <button id="clearSessionBtn" title="清空会话">清空</button>
          </div>
        </header>
        <div id="memoryPanel" class="memory-panel hidden"></div>
        <div id="chatMessages" class="chat-messages"></div>
        <div id="chatConfirm" class="chat-confirm hidden"></div>
        <footer class="chat-input-row">
          <label class="chat-attach">
            <input id="chatFileInput" type="file" accept=".xlsx,.xls">
            📎
          </label>
          <input id="chatInput" type="text" placeholder="告诉 AI 你要做什么…" autocomplete="off">
          <button id="chatSendBtn">发送</button>
        </footer>
      </aside>
```

```html
    <script src="/chat.js" type="module"></script>
```

- [ ] **Step 2: 修改 styles.css**

在文件末尾追加：

```css
.chat-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 360px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f7f7f8;
  border-left: 1px solid #ddd;
  z-index: 50;
  font-size: 14px;
}
.chat-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: #fff; border-bottom: 1px solid #ddd; }
.chat-header h2 { margin: 0; font-size: 15px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.chat-msg { max-width: 90%; padding: 8px 10px; border-radius: 8px; white-space: pre-wrap; word-break: break-word; }
.chat-msg.user { align-self: flex-end; background: #008060; color: #fff; }
.chat-msg.ai { align-self: flex-start; background: #fff; border: 1px solid #ddd; }
.chat-msg.tool { align-self: flex-start; background: #fff8e6; border: 1px solid #f0d98c; font-size: 12px; }
.chat-confirm { padding: 10px; background: #fff; border-top: 1px solid #ddd; }
.chat-confirm p { margin: 0 0 8px; }
.chat-input-row { display: flex; gap: 6px; padding: 10px; background: #fff; border-top: 1px solid #ddd; }
.chat-input-row input[type="text"] { flex: 1; padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; }
.chat-attach input { display: none; }
.memory-panel { padding: 10px; background: #eef6ff; border-bottom: 1px solid #bcd9f7; font-size: 12px; }
.memory-panel .mem-item { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.hidden { display: none; }
```

- [ ] **Step 3: 实现 chat.js**

```js
const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#chatMessages");
const confirmEl = $("#chatConfirm");
const inputEl = $("#chatInput");
const sendBtn = $("#chatSendBtn");
const fileInput = $("#chatFileInput");
const memoryBtn = $("#memoryBtn");
const memoryPanel = $("#memoryPanel");
const clearSessionBtn = $("#clearSessionBtn");

const SESSION_KEY = "chatSessionId";
let sessionId = localStorage.getItem(SESSION_KEY) || crypto.randomUUID();
localStorage.setItem(SESSION_KEY, sessionId);
let pendingConfirm = null;

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `chat-msg ${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function showConfirm(name, summary, args) {
  pendingConfirm = { name, args };
  confirmEl.innerHTML = "";
  const p = document.createElement("p");
  p.textContent = `⚠️ ${summary}，确认执行吗？`;
  const ok = document.createElement("button");
  ok.textContent = "确认";
  ok.onclick = () => sendConfirm("confirm");
  const cancel = document.createElement("button");
  cancel.textContent = "取消";
  cancel.onclick = () => sendConfirm("cancel");
  confirmEl.append(p, ok, cancel);
  confirmEl.classList.remove("hidden");
}

async function sendConfirm(decision) {
  confirmEl.classList.add("hidden");
  await postChat({ confirm: decision });
}

async function postChat(body) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, ...body })
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    addMessage("ai", payload.error || "请求失败");
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let aiEl = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === "text") {
        if (!aiEl) aiEl = addMessage("ai", "");
        aiEl.textContent += event.delta;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      } else if (event.type === "tool") {
        addMessage("tool", `[工具 ${event.name}] ${event.status === "running" ? "执行中…" : event.status === "ok" ? "完成" : "失败"}${event.result ? " " + JSON.stringify(event.result).slice(0, 300) : ""}`);
      } else if (event.type === "confirmation") {
        showConfirm(event.name, event.summary, event.args);
      } else if (event.type === "note") {
        addMessage("tool", `ℹ️ ${event.text}`);
      } else if (event.type === "done") {
        addMessage("ai", event.text);
        aiEl = null;
      } else if (event.type === "error") {
        addMessage("ai", `❌ ${event.error}`);
      }
    }
  }
}

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  addMessage("user", text);
  await postChat({ message: text });
}

sendBtn.onclick = sendMessage;
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  addMessage("user", `📎 上传文件：${file.name}`);
  try {
    const resp = await fetch("/api/chat/upload", { method: "POST", body: form });
    const payload = await resp.json();
    if (!resp.ok) throw new Error(payload.error || "上传失败");
    addMessage("user", `文件已解析：${file.name}（批次 ${payload.batchId}，共 ${payload.summary.productCount} 个商品）`);
  } catch (error) {
    addMessage("ai", `❌ ${error.message}`);
  }
  fileInput.value = "";
});

async function renderMemory() {
  const resp = await fetch("/api/memory");
  const payload = await resp.json();
  memoryPanel.innerHTML = "";
  if (!payload.memories?.length) {
    memoryPanel.textContent = "暂无记忆";
  }
  for (const item of payload.memories) {
    const row = document.createElement("div");
    row.className = "mem-item";
    const label = document.createElement("span");
    label.textContent = `${item.key}: ${item.value}`;
    const del = document.createElement("button");
    del.textContent = "删";
    del.onclick = async () => {
      await fetch(`/api/memory?key=${encodeURIComponent(item.key)}`, { method: "DELETE" });
      renderMemory();
    };
    row.append(label, del);
    memoryPanel.appendChild(row);
  }
}

memoryBtn.onclick = async () => {
  memoryPanel.classList.toggle("hidden");
  if (!memoryPanel.classList.contains("hidden")) renderMemory();
};

clearSessionBtn.onclick = async () => {
  await fetch("/api/chat/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId })
  });
  sessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sessionId);
  messagesEl.innerHTML = "";
  addMessage("ai", "会话已清空，可以重新开始。");
};

addMessage("ai", "你好，我是上货助手。可以上传 Excel 让我解析，或直接告诉我创建草稿、改库存、改类别等操作。");
```

- [ ] **Step 4: 手动验证**

Run: 重启服务后打开 `http://localhost:3001`，确认右侧侧边栏出现、可发送消息（未配置 key 时显示错误提示）、附件按钮可用。

- [ ] **Step 5: 提交**

```bash
git add public/index.html public/styles.css public/chat.js
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat(ai): 前端聊天侧边栏"
```

---

### Task 10: 文档与端到端验收

**Files:**
- Modify: `README.md`（新增 AI 助手说明与配置）

- [ ] **Step 1: 修改 README.md**

在"准备配置"的 env 示例后追加：

```markdown
## AI 上货助手

页面右侧内置 AI 聊天窗口（DeepSeek）。先在 `.env` 配置：

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=sk-你的 DeepSeek Key
AI_CHAT_MODEL=deepseek-chat
```

AI 只能通过内置白名单工具操作：解析 Excel、创建草稿商品、修改库存/类别/产品类型/集合、删除商品、公开上架（后两项需在聊天中确认）、管理长期记忆。超出范围的要求会被拒绝。会话历史与记忆保存在 `data/chat/`。
```

- [ ] **Step 2: 端到端手工验收清单**

在真实 DeepSeek Key 下逐项验收：

1. 启动服务，右侧侧边栏出现，未配置 key 时提示"未配置 AI_API_KEY"；
2. 配置 key 后发送"你好"，AI 正常流式回复；
3. 聊天中上传 Excel，AI 能通过 `get_batch_summary` 看到批次信息；
4. 让 AI"把这个批次创建为草稿"，确认创建成功（商品为 DRAFT）；
5. 让 AI"把所有商品库存设为 100"，确认成功；
6. 让 AI"把所有商品类别改为钓鱼"，确认成功；
7. 让 AI"删除商品 X"，出现确认卡片，取消不执行、确认后执行；
8. 让 AI"读取 C 盘文件 / 访问某个网址"，确认被拒绝；
9. 让 AI"记住库存默认 100"，记忆面板出现该条目，新会话仍生效；
10. 长对话（>20 条）后确认摘要生成、上下文不丢。

- [ ] **Step 3: 提交**

```bash
git add README.md
git -c user.name="Codex" -c user.email="codex@local" commit -m "docs: AI 上货助手使用说明"
```

---

## Self-Review

- **Spec 覆盖**：白名单 14 工具（Task 5）、确认门（Task 7）、会话上下文与摘要（Task 3）、全局记忆（Task 2 + Task 5 记忆工具）、SSE/UI（Task 8/9）、127.0.0.1（Task 8）、配置与测试（Task 8/10）——全部有对应任务。
- **占位扫描**：全文档无 TBD/TODO；Task 4 半成品函数已删除，只保留 `updateField` 与完整导出。
- **类型一致性**：`validateParams`、`MemoryStore`、`SessionStore`、`createLlm`、`runTool`、`ChatController` 的名称与签名在 Task 1-8 间一致；`ctx.shopify` 在 Task 5 与 Task 7 的 `_ctx()` 中均为 `shopifyTools` 模块对象。
