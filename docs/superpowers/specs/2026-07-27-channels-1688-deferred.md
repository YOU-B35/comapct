# 视频号 + 1688 — 下期占位（Deferred）

> 日期：2026-07-27  
> 状态：**视频号仍延期**；**1688 真后端已启动**  
> **更新 2026-08-17：** 1688 真后端已启动，见 `2026-08-17-alibaba1688-ops-design.md` 与 `docs/superpowers/plans/2026-08-17-alibaba1688-ops.md`。本文仅视频号延期条款继续有效。  
> 上级：`2026-07-27-platform-ops-master-design.md`  
> 排期：Q3 60 工作日 **不分配**人日（视频号）；1688 另开分册实施

---

## 1. 为何延期

| 平台 | 原因 |
|------|------|
| 视频号 | 与抖音同构；须先交付抖音模板再复制，避免双线探测 |
| 1688 | 采购视角，不挡卖货主线七平台演示 |

本期「正常使用」定义只覆盖 **7** 平台；本文件保证前端壳子可继续 Demo，但 **不得** 被算作 M7 签字项。

---

## 2. 视频号（下期草案摘要）

### 2.1 预期复用
- Shared kit + **抖音分册全文复制**，前缀改为 `channels` / `shipinhao`（**下期开写时锁定一个 platform key**，与路由 `ChannelsModuleView` 对齐）。  
- 任务：`channels_session_probe` / `channels_login_open` / `channels_sync`。  
- Tab：今日订单 + 内容预警（现有壳子）。

### 2.2 本期禁止
- 新建 `/api/channels` 当真后端并加入 `BACKEND_OPERATIONAL_PLATFORMS`。  
- 把抖音人日挪来做视频号真实同步（除非老板书面改 7/9 范围）。

### 2.3 现有壳子路径
- `dev/vue-site/src/views/channels/ChannelsModuleView.vue`
- domestic / Demo 常量（若有）

---

## 3. 1688（下期草案摘要）

### 3.1 预期范围（未设计细表）
- 采购单列表 + 供应商/异常预警（PRD backlog）。  
- 可能非 domestic 双 Tab；需独立分册，**不要**假设与抖音同表。

### 3.2 本期禁止
- Java 真同步入库冒充已交付。  
- 占用拼多多/Walmart 工期。

### 3.3 现有壳子路径
- `dev/vue-site/src/views/alibaba1688/Alibaba1688ModuleView.vue`

---

## 4. 若老板要求「9/9 全开」

按三月排期降级表：

| 要求 | 代价 |
|------|------|
| 加视频号真实同步 | 砍独立站或 Walmart 整块 |
| 加 1688 | 缩拼多多或 Walmart |
| 坚持 7/9 | **推荐**；本文件维持 |

变更须改 Master §1 与日历，并新建正式 design（本占位不算开发契约）。

---

## 5. 验收（本期）

| ID | 期望 |
|----|------|
| DEF-A01 | M7 签字清单 **不含** 视频号/1688 真同步 |
| DEF-A02 | 两平台仍可为 Demo-only；黄条/提示诚实 |
| DEF-A03 | 现状表写明「纳入 7 / 下期 2」 |

---

## 6. 下期启动条件

1. 抖音主路径验收通过并稳定 ≥1 周。  
2. 书面确认 platform key 与人日来源。  
3. 复制抖音分册 → `YYYY-MM-DD-channels-ops-design.md` 再开发。

---

## 7. 自检

- [x] 无「顺便做一点真同步」模糊口子  
- [x] 指向现有 Vue 壳子  
- [x] 变更代价写死  
