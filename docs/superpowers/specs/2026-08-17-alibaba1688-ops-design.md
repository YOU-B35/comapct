# 1688 运营真后端 Design Spec

> 日期：2026-08-17  
> 状态：**已批准 · 实施中（Tasks 1–10 代码落地；Day0 真人探测与提交待用户）**  
> 实施计划：`docs/superpowers/plans/2026-08-17-alibaba1688-ops.md`  
> 验收：`docs/superpowers/specs/attachments/1688-acceptance.md`  
> 上级：`2026-07-27-platform-ops-master-design.md`  
> 取代关系：启动本分册后，`2026-07-27-channels-1688-deferred.md` 中 **1688 延期条款作废**（视频号延期仍有效）  
> 参考实现：AliExpress 垂直包（`com.crosshub.aliexpress` + Playwright crawl/job）  
> UI 壳子：`dev/vue-site/src/views/alibaba1688/Alibaba1688ModuleView.vue`（**扩展，不新建模块**）

---

## 1. 背景与目标

### 1.1 现状
- 路由 `/boss/1688`、`/employee/1688` 与菜单已存在。  
- Tab：采购单 + 供应商预警；数据走 `alibaba1688*.js` Demo / Local。  
- `platformOperationalMode.js` 将 `1688` 视为 Demo-only。  
- Java **无** `com.crosshub.alibaba1688` 包、**无** `/api/1688`。  
- 账户绑定已支持 `platform=1688`；推仓入口已挂在采购面板。

### 1.2 目标（可勾选）
1. 本机 Windows 上 Playwright 完成登录探活与采购数据同步。  
2. Java 编排 crawl job、SQLite 持久化、提供 operational 读接口。  
3. Vue 壳子在后端可用时走真数据；后端不可用时诚实回退 Demo + 提示。  
4. 面板覆盖：采购单、供应商预警、到货时效、缺货/延期预警、复购供应商排行、Boss 总览四指标。  
5. 员工端店铺范围与现有 `scopeStores` / 运营绑定一致。

### 1.3 非目标（本期禁止）
| 不做 | 说明 |
|------|------|
| 采购对账（应付/已付/差异） | 明确二期 |
| 线上服务器跑 Playwright | 仅本机开发机 |
| 1688 开放平台官方 API | 本期不做 |
| 抽取 AE 公共爬虫框架 | 避免先重构再交付 |
| 新建第三个「排行」主导航 Tab | 排行放在供应商 Tab 上半区 |
| 视频号真同步 | 仍见 deferred 文档 |

### 1.4 已锁定决策
| 项 | 选择 |
|----|------|
| 交付形态 | 真运营后端（非加深 Demo） |
| 数据接入 | Playwright 浏览器自动化（对齐 AE） |
| MVP 范围 | 最小闭环 + 细面板 1/2/4 |
| 细面板 | 到货时效/物流异常；缺货/延期未发；复购供应商排行 |
| 爬虫运行位置 | 仅本机 Windows |
| 实现路线 | AE 垂直复制（方案 1） |
| platform key | 路由/菜单/账户：`1688`；Java 包：`alibaba1688`；API：`/api/1688` |

---

## 2. 架构与数据流

```text
[Vue Alibaba1688ModuleView]
        │  /api/1688/*  +  /api/platform-accounts?platform=1688
        ▼
[Java com.crosshub.alibaba1688]
  · POST /crawl | /sync → 创建 CrawlJob
  · 轮询 GET /crawl/{jobId}
  · GET /operational（采购单、预警、时效、排行、overview）
        │  启动/等待本机进程
        ▼
[Python Playwright · 本机]
  · profile：backend/python/.1688-browser-profile/tenant-{tenantId}
  · login_probe → 采购单列表 → 物流/发货状态 → 回传 JSON
        │
        ▼
[SQLite]
  · alibaba1688_crawl_job
  · alibaba1688_purchase_order
  · alibaba1688_supplier_alert
  · alibaba1688_supplier_stat
```

店铺主数据不新建表，继续使用 **`platform_account` where platform = `1688`**。

---

## 3. 用户流程

### 3.1 首次就绪
1. Boss 在「账户绑定」绑定 `platform=1688` 店铺（已有）。  
2. 打开「1688 运营」→ 若无可用 session：触发 `login_probe`（有头浏览器）。  
3. 未登录：job 状态 `need_login`，前端引导人工登录；登录完成后再次 probe 至成功。  
4. 用户点「同步」→ `crawl`/`sync` job → 成功后拉 `GET /operational`。

### 3.2 日常同步
1. `POST /api/1688/crawl`（或 `/sync`）→ `202` + `jobId`。  
2. 前端轮询 `GET /api/1688/crawl/{jobId}`。  
3. 同租户同 `job_type` 互斥；冲突返回明确错误（对齐 AE `CrawlConflictException`）。  
4. 成功：upsert 采购单 → 规则生成/更新 alert → 重算 supplier_stat → 刷新面板。

### 3.3 推仓
沿用现有 `PlatformShipPushDialog` + `platformShipRequests`；本期不把推仓升为一等验收硬项，但入口保持可用。

---

## 4. 数据模型

### 4.1 `alibaba1688_crawl_job`
| 字段 | 说明 |
|------|------|
| id, tenant_id, store_id? | 任务主键与范围 |
| status | pending / running / success / failed / need_login / partial |
| job_type | login_probe / crawl / sync |
| progress, message | 进度与可读错误 |
| started_at, finished_at | 时间戳 |

### 4.2 `alibaba1688_purchase_order`
| 字段 | 说明 |
|------|------|
| tenant_id, store_id, order_no | 唯一键建议 `(tenant_id, store_id, order_no)` |
| status, pay_status, ship_status | 归一后状态 + 可保留原文截断 |
| supplier_name, supplier_id? | 供应商 |
| amount, currency | 金额 |
| expected_arrival_at, actual_ship_at? | 时效 |
| logistics_status | 物流文案/枚举 |
| is_delayed, is_stockout | 规则字段 |
| raw_json, synced_at | 原始快照与同步时间 |

**延期规则：** `expected_arrival_at < now` 且未签收（或等价终态未达）。  
**缺货规则：** 爬取状态文案/标记映射为 `is_stockout=true`（具体关键词在 Day0 探测后写入常量，禁止空猜上线）。

### 4.3 `alibaba1688_supplier_alert`
| 字段 | 说明 |
|------|------|
| type | delay / stockout / quality / other |
| supplier_name, related_order_no? | 关联 |
| level, message, is_open | 展示与任务用 |
| created_at, resolved_at? | 生命周期 |

同步结束时由规则生成/更新快照（便于总览与 `employeeTasks`）。

### 4.4 `alibaba1688_supplier_stat`
| 字段 | 说明 |
|------|------|
| supplier_key, supplier_name | 排行主键 |
| order_count, total_amount, on_time_rate | 指标 |
| last_order_at, window | 默认窗口 **90 日** |
| tenant_id, store_id | 隔离 |

每次 sync 按采购单重算窗口统计。

### 4.5 store_id 映射
- 对外 `store_id` = `platform_accounts.id`。  
- 爬虫侧店铺标识写入 `external_shop_id`（若绑定已填则用于上下文；多店未映射则 job failed，错误码可读）。

---

## 5. API

前缀：`/api/1688`（鉴权 + `tenant_id` 隔离，与现有平台一致）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/crawl` | body 含 `jobType`：`login_probe` \| `crawl` \| `sync` → 202 + jobDto（**钉死**：不单独做 `/login/probe`） |
| POST | `/sync` | 可选别名，等价 `jobType=sync` 的 `/crawl` |
| GET | `/crawl/{jobId}` | 轮询 |
| GET | `/crawl` | 最近 job 列表（对齐 AE，默认 limit 20） |
| GET | `/operational` | 聚合读模型 |

### 5.1 `GET /operational` 读模型

```json
{
  "syncedAt": "ISO-8601",
  "purchaseOrders": [],
  "supplierAlerts": [],
  "supplierRanking": [],
  "overview": {
    "pendingPurchase": 0,
    "openAlerts": 0,
    "delayedCount": 0,
    "stockoutCount": 0
  }
}
```

`purchaseOrders` 项须含前端已用/将用字段：`isActionNeeded`、`isDelayed`、`isStockout`、ETA 相关字段。  
`supplierAlerts` 项含 `isOpen`。  
`supplierRanking` 项含 `orderCount`、`totalAmount`、`onTimeRate`。

---

## 6. Playwright / 本机约束

- Profile 目录：`backend/python/.1688-browser-profile/tenant-{tenantId}`，与 AE/Temu/抖音档案隔离。  
- `login_probe`：有头；`sync`：默认有头更稳（可用 config 开关，默认有头）。  
- 同步策略：**upsert，禁止成功路径整表 wipe**；超时/失败保留上次 `syncedAt` 数据。  
- 页面结构变更导致部分字段缺失：job 可 `partial` + warning，不得清空已有有效单。  
- Day0：须用真实 1688 买家账号探测采购列表/物流字段，产物写入 `docs/superpowers/specs/attachments/`（可截断敏感信息）；未探测完成前禁止假装同步已通。

---

## 7. 前端改动清单

| 项 | 说明 |
|----|------|
| `api/alibaba1688Api.js` | 真接口 facade：crawl/poll/operational |
| `api/alibaba1688.js` | 统一入口：后端可用走 Api，否则 Demo |
| `platformOperationalMode.js` | `1688` 加入 `BACKEND_OPERATIONAL_PLATFORMS` |
| `Alibaba1688ModuleView` | 同步按钮 + job 轮询；连通后不再强制 Demo |
| `Alibaba1688PurchasePanel` | ETA / 延期 / 缺货展示 |
| `Alibaba1688SupplierPanel` | 上半区复购排行 + 下半区预警 |
| `Alibaba1688BossOverview` | 接 overview 四指标 |
| `operationsOverview.js` / `employeeTasks` | 有后端时读真运营数据 |

不改：菜单结构、路由、账户绑定对话框结构、推仓对话框结构。

---

## 8. 错误处理与降级

| 情况 | 表现 |
|------|------|
| Python/浏览器未就绪 | job failed，message 可读 |
| 未登录 | `need_login`，引导打开登录，禁止假成功 |
| 同租户任务冲突 | 409 / 明确冲突提示，不双开爬虫 |
| 页面改版抓不全 | partial + 保留旧数据 |
| 超时 | failed；保留上次成功数据 |
| Java 未启动 | Api facade → Local Demo + 黄条提示 |

---

## 9. 测试与验收

### 9.1 自动化（最低）
- Java：job 互斥、operational 聚合、延期/缺货规则单元测。  
- 前端：后端不可达时 facade 回退 Demo（可测纯函数/mock）。

### 9.2 验收标准

| ID | 期望 |
|----|------|
| A01 | 本机完成 login_probe → 人工登录 → session 可用 |
| A02 | sync 成功后采购单入库，面板非 Demo 随机数 |
| A03 | 延期/缺货在采购列表高亮，并出现在 supplier_alert |
| A04 | 供应商 Tab 可见 90 日复购排行（频次/金额/准时率） |
| A05 | 总览四指标与列表一致 |
| A06 | 同步中再次同步有冲突提示 |
| A07 | Java 挂掉时可进模块并提示 + Demo 回退 |
| A08 | 员工只见绑定范围内 1688 店 |
| A09 | 不含采购对账；不含线上服务器爬虫 |

---

## 10. 组件边界（实现时遵守）

| 单元 | 职责 | 依赖 |
|------|------|------|
| `Alibaba1688CrawlService` | 创建/互斥/启动 Python/更新 job | job repo, process runner |
| `Alibaba1688OperationalService` | 读聚合 + 规则派生 overview | order/alert/stat repos |
| Python `1688` crawl script | 浏览器抓取与 JSON 输出 | Playwright profile |
| `alibaba1688Api.js` | HTTP + 错误归一 | Java `/api/1688` |
| ModuleView | Tab 编排、同步 UX、店铺选择 | Api + panels |

各单元通过 DTO/JSON 契约交互；禁止 Vue 直连 SQLite 或直接 spawn Python。

---

## 11. 自检记录

- [x] 无 TBD/TODO 占位要求  
- [x] 与「仅本机 Playwright / 不做对账 / 扩展现壳」决策一致  
- [x] 范围可落入单一实施计划（Day0 探测 → Java → Python → Vue → 验收）  
- [x] API 前缀与 platform key `1688` 无歧义  
- [x] 登录探活钉死为 `POST /crawl` + `jobType=login_probe`（见 §5）
