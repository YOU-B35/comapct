# CrossHub 开发交接文档

> **唯一活文档**：任何 Agent / 开发者接手本项目时**必须先读本文**，开发结束前**必须更新本文**。  
> **最后更新**：2026-08-27（Asia/Shanghai，生产拼多多 404 修复）  
> **更新人**：开发会话（完整基建交接文档）  
> **Git 分支**：`feat/amazon-v2-ops-crawl` · 最近提交 `1091976`（其后有未提交 JP/自启/并发/托盘等）  
> **全量快照**：`docs/progress-snapshot-2026-07-30.md`  
> **全量交接提示词**：`全量项目交接提示词.md`（根目录，可粘贴给下一任 Agent）  
> **完整基建交接**：`docs/完整项目交接文档-2026-07-31.md`（Docker / Nginx / 对外地址 / 服务器）  
> **残留 PRD/Spec**：`docs/superpowers/specs/2026-07-29-temu-m0-residual-close-prd.md` · `...-design.md`  
> **A06 证据**：`docs/superpowers/specs/attachments/2026-07-29-temu-m0-residual-evidence.md` · `2026-07-29-a06-jp-discover.json`  
> **RC-AUTO**：`docs/superpowers/specs/attachments/2026-07-29-rc-auto-checklist.md`；任务名 `CrossHub-Sync-Helper`

---

## 0. 如何维护本文（强制）

| 时机 | 动作 |
|------|------|
| **开工前** | 通读全文，确认「下一动作」与阻塞项仍成立 |
| **开发中** | 阻塞/假设变化时即时改 §5、§6 |
| **收工前** | 更新 §1～§8，在 §9 **追加一条**交接记录（日期 + 做了什么 + 剩什么） |
| **包 DONE** | 同步改清单 Excel + 在 §4 改状态；**不以快照代替本文** |

日快照（可选）：`docs/progress-snapshot-YYYY-MM-DD.md` — 仅作存档，**交接以本文为准**。

---

## 1. 下一动作（接手后第一件事）

1. Temu 日批 job `ec6fbfb9-...` 仍可能因卖家未登录停在 running——需人工确认 Chrome 登录后看是否 success。  
2. **按 Bug Spec 修 Temu Profile 误迁移**：`docs/superpowers/specs/2026-07-30-temu-profile-migration-account-isolation-design.md`。  
3. 清理已污染目录 `backend/python/.temu-browser-profile/tenant-5/account-13861260796`，再对 `YONI / 13861260796` 做干净首次登录回归。  
4. AE `CRAWL_PYTHON_ENV` 架构债（应 Agent 化）与 Profile Sync AP-01/AP-02 证据收口（后续项）。  
5. 【2026-08-20】爬虫已默认改用 Playwright 内置 Chromium（未提交）；重建 Helper exe 部署前，目标机需先 `py -m playwright install chromium`（无内置浏览器时冻结 exe 会自动回退本机 Chrome/Edge）。  
6. 【2026-08-27】生产拼多多/淘宝 404 已修复：根因是生产 Nginx 反代片段（`/opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf`）缺 `/api/pdd`、`/api/taobao`、`/api/sync-logs` 三个转发块；本地 `deploy/crosshub-proxy.conf` 已补齐并同步上线（备份 `.bak.20260827T08362`）。**以后新增平台后端接口，必须同步在 `deploy/crosshub-proxy.conf` 增加对应 `location` 块并部署，否则生产会 404。**  

---

## 2. 当前里程碑

| 里程碑 | 目标日 | 范围 | 状态 |
|--------|--------|------|------|
| **M0 Temu 收口** | 2026-07-29 | TM-P1～P5、TM-A01～A07 | 🔧 进行中 |

### 工作包状态（Temu）

| 包 ID | 状态 | 备注 |
|-------|------|------|
| TM-P1 | ✅ DONE | 基线取证 → `docs/superpowers/specs/attachments/temu-hardening-baseline.md` |
| TM-P2a | ✅ DONE | P0 假在线 → `agentPresence.js` + 双态 UI |
| TM-P2 | ✅ DONE（已 commit `1091976`） | session 语义 / probe / 前端文案 / Java enrich |
| TM-P3 | ✅ DONE（已 commit `1091976`） | 登录引导：助手离线禁用按钮 + TEMU_AGENT_OFFLINE 文案；`pollTemuSessionUntilReady` 2s→5s 退避 / 默认最多 20 次 |
| TM-P4 | ✅ DONE | ingest 401 已消除；session.ready 前置校验；**A04 端到端 success**（job `9164c244`，`report_time=2026-07-28`） |
| TM-P5 | ✅ DONE（清单已勾） | A06 竞店冒烟绿：`fishing`/`jp` → candidates=1、sample×10、¥价；证据 residual-evidence + a06-jp-discover.json；**亏损 Tab 待 RC-COST（后期）** |

---

## 3. 环境与命令

| 服务 | 端口 | 启动 |
|------|------|------|
| Java API | `18080` | `powershell -File scripts/restart-java-api.ps1` |
| Vue | `5173` | `cd dev/vue-site && npm run dev` |
| Agent | 运维机 `.exe` | `powershell -File scripts/build-sync-helper-exe.ps1` → `dist/CrossHub-Sync-Helper/.../CrossHub-Sync-Helper.exe`；`setup-sync-helper-config.ps1` 写 token |
| Express | `3000` | `cd script/api-server && npm start` |

**改 `backend/java/` 后必须重启 Java**（见上脚本）。

**DB**：`backend/data/crosshub.db`（SQLite，生产验证优先用此库）。

**文档**：`docs/` 仅本地，**不上传 GitHub**（根 `README.md` 除外）。

---

## 4. 测试账号（Temu M0 默认）

| 用途 | 账号 | 租户 | 说明 |
|------|------|------|------|
| **M0 验收（推荐）** | `HangZhouYiTuo` / `HangZhouYiTuo` | **5** | 本机助手心跳绑定此租户 |
| 演示 Boss | `admin@crosshub.cn` / `12345678` | **1** | 助手**未**绑此租户 → 会显示离线 |

店铺示例（tenant5）：Gourami `shop_id=634418211126671`。

---

## 5. 活跃阻塞项（按优先级）

| # | 阻塞 | 影响 | 负责包 |
|---|------|------|--------|
| 1 | **`cost=0`** 仍是生产现状（**后期 RC-COST**） | 未导入前亏损 Tab 仍 0 条，A05/A10 不能全绿 | 数据 / TM-P5 |
| 2 | ~~生产 `frontend-login/open` 404~~ | **已消**：2026-07-29 12:32 部署（`CROSSHUB_SKIP_DB_UPLOAD=1`）；接口 **200 queued** | ✅ 部署 |
| 3 | 侧栏 SKU/销量口径与页面不一致 | 同步状态展示误导 | TM-P5 |
| 4 | ~~肉机 Helper 未设开机自启~~ | **已消**：计划任务 `CrossHub-Sync-Helper`（Source 模式）；见 RC-AUTO checklist | ✅ RC-AUTO |
| 5 | AE 日批在服务器跑 → `CRAWL_PYTHON_ENV` | 容器无 `python3`；日批 AE 必失败 | 架构/运维 |
| 6 | Amazon 紫鸟会话偶发过期 | 模拟日批后 `AMAZON_LOGIN_REQUIRED` | 运维 |
| 7 | 日批 Amazon 入队偶发 `SQLITE_BUSY` | force 全平台并发写库 | Java/DB |

---

## 6. 现场数据摘要（2026-07-28 12:00 · **生产**）

- **前端**：`https://www.yoto.work/crosshub/`  
- **API**：`https://www.yoto.work/api/*`（含 `POST /api/platform/daily-sync/run?force=true`）  
- **肉机 Helper / Agent**：已确认源码 Agent 用 `https://www.yoto.work` 可领取 `temu_competitor_discover`；旧 Helper 曾因版本/配置问题导致 “未支持的任务类型”  
- **模拟日批**（不必等 09:30）：`POST .../daily-sync/run?force=true`  
  - Temu job `a8d2b61c` → **success** rows=**430** shops=2（03:54:58～03:57:12）  
  - AE → **failed** `CRAWL_PYTHON_ENV`（预期）  
  - Amazon 日批入队 → `SQLITE_BUSY`；另 `POST /api/amazon/sync` force → `AMAZON_LOGIN_REQUIRED`  
- 日批 schedule：enabled，next **07-29 09:30** Asia/Shanghai  
- **部署注意**：`CROSSHUB_SKIP_DB_UPLOAD=1`（勿用本机 DB 覆盖线上）。2026-07-28 本次全量部署曾把线上 SQLite 打成坏库导致 `crosshub-java` 502，已用本地健康库重传恢复；后续上线必须显式跳过 DB 上传  

---

## 7. 本迭代已交付（累计能力）

- 租户心跳 vs 本机进程双态（`dev/vue-site/src/utils/agentPresence.js`）  
- Session：`error_hint` 区分未登录 / 未选店（Python + Java enrich + `TemuLoginGuide`）  
- Agent probe：cache-only 不 ready → live（`backend/python/agent/temu_tasks.py`）  
- 四 Tab：`temuServerAlgo.js` 不再清空滞销估算  
- 成本真输入：`temu_sku_cost` + `POST /api/temu/sku-costs` + `TemuOperationalServiceImpl` overlay  
- 竞店 Discover：`temu_competitor_discover` 已改走 Agent 任务，不再依赖服务器本地 Python  
- Discover 生产排障结论：已依次定位并恢复
  - 生产 Java 502 根因：远端 `crosshub.db` 损坏
  - 旧 Helper 根因：不支持 `temu_competitor_discover`
  - 当前代码态：`seller_login_assist` / `agent.temu_tasks.open_login_window` / `competitor_discovery` 已改为复用 agent 进程内 tenant live browser runtime；并已消除跨线程复用 Playwright sync 对象的问题
- 竞店 Monitor：冷却拆 scope（Task1–5）；本地 ACC 见 `attachments/2026-07-29-monitor-cooldown-url-evidence.md`（ACC-2/6 PARTIAL）；未 commit；生产 SKIP_DB 待部署  
- tenant5 在线验收证据：`docs/superpowers/specs/attachments/2026-07-28-temu-m0-acceptance-evidence.md`
- Git：docs 本地化策略（commit `a2d761e`）

---

## 8. 未提交 Git 的主要变更

> **业务主链路已 commit**：`1091976`（117 files）。分支相对 origin **ahead 1**（未 push）。

仍留在工作区、**刻意未提交**（临时探针 / 可能含敏感信息）：

| 类型 | 路径 |
|------|------|
| Cookie 临时文件 | `scripts/_dxm_cookie_tmp.txt`（禁止提交） |
| DXM 探针脚本 | `scripts/_probe_dxm_*.py` |
| SSH/运维探针 | `scripts/_ssh_*.js`、`_peek_*`、`_poll_*`、`_monitor_*` 等 |

可选：日批观察后再重建 `CrossHub-Sync-Helper.exe`（当前用源码 `run-agent.ps1`）。

---

## 9. 关键文件索引

| 主题 | 路径 |
|------|------|
| 排期（权威） | `docs/platform-ops-dev-schedule-engineering.md` |
| 清单 Excel | `docs/CrossHub多平台运营-清单消除表.xlsx` |
| Temu 硬化 Plan | `docs/superpowers/plans/2026-07-27-temu-hardening.md` |
| **Temu M0 缺口 Spec（续）** | `docs/superpowers/specs/2026-07-28-temu-m0-gap-close-design.md` |
| **Temu M0 验收 Spec** | `docs/superpowers/specs/2026-07-28-temu-m0-acceptance-spec.md` |
| **Temu M0 验收证据** | `docs/superpowers/specs/attachments/2026-07-28-temu-m0-acceptance-evidence.md` |
| **全量工作快照（2026-07-28）** | `docs/progress-snapshot-2026-07-28.md` |
| TM-P1 证据 | `docs/superpowers/specs/attachments/temu-hardening-baseline.md` |
| TM-P2 证据 | `docs/superpowers/specs/attachments/temu-hardening-tm-p2-evidence.md` |
| Temu 运营页 | `dev/vue-site/src/views/temu/TemuModuleView.vue` |
| 四 Tab 算法合并 | `dev/vue-site/src/utils/temuServerAlgo.js` |
| Session API | `backend/java/.../TemuSessionServiceImpl.java` |
| Crawl | `backend/java/.../TemuCrawlServiceImpl.java` |
| Ingest | `backend/java/.../agent/controller/AgentController.java` |
| 冒烟脚本 | `scripts/_tm_p5_smoke.mjs` |
| 店小秘探测（勿提交 cookie） | `scripts/_probe_dxm_*.py`（`DXM_COOKIE` 环境变量） |

---

## 9.1 店小秘（DXM）数据源评估（2026-07-27，复审）

**结论不变：Cookie 有效，但店小秘 Temu 数据链路是「Temu 官方 Token + 浏览器采集插件 + ERP 内部统计」三层混合，且当前账号配置不完整；不能替代 CrossHub Temu Agent 作为主数据源。**

### 官方文档要点（已读 help.dianxiaomi.com）

| 文档 | 链接 | 核心结论 |
|------|------|----------|
| Temu 全托管店铺授权 | [article/2347](https://help.dianxiaomi.com/article/2347) | 用 Temu 服务市场 **产品库存 Token**（商品）+ 可选 **合规 API Token**（订单）；Token **90 天**过期；免费版仅 1 个全托管店 |
| Temu 全托管销量 | [dataAnalytics/2874](https://help.dianxiaomi.com/article/dataAnalytics/2874) | Listing 销量前提：**仓库→Temu全托管→销售管理** 先有数据；来源二选一：① 每晚 **22:00 后** API 拉当日销量 ② **采集插件** 拉近 30 天（不含今天） |
| 采集插件教程 | [financialManagement/2928](https://help.dianxiaomi.com/article/financialManagement/2928) | **手动**采集申报价/财务/销量；仅 `seller.kuajingmaihuo.com` 有入口（`agentseller.temu.com` 无）；单次最多 31 天；付款销售额**必须**插件采申报价才算 |
| 平台结算 | [financialManagement/2594](https://help.dianxiaomi.com/article/financialManagement/2594) | 结算数据也是**插件手动采集**；半托管结算不支持；数据仅供参考 |
| Listing 销量说明 | 帮助中心搜索 | Listing = 整链接汇总；SKU 销量 = 变种维度；Temu 全托**不支持**退款统计 |

**无对外「开发文档 / Open API」**：店小秘未提供第三方可调用的公开 API；对外集成方式是卖家在 ERP 内授权 Temu Token + 安装浏览器插件。CrossHub 若接店小秘，实质是 **Cookie 反代内部 `/api/*`** 或 **再爬 Temu 后台（与现状同类问题）**。

### 复审实测（同一 Cookie，2026-07-27 17:23）

| 项 | 结果 | 与文档对照 |
|----|------|------------|
| 会话 | ✅ `userInfo` 正常，账号 Ashuan | — |
| 绑定店 | `徐铨金牌店` / pddkj | 与 tenant5 的 Gourami **不是同一店铺** |
| `lastSyncTime*` | **全部为 null** | 订单/产品/消息从未同步到店小秘 |
| 采集插件记录 | `pluginCrawlView` → **0 条** | 从未跑过插件采集（文档要求的申报价/30 天销量/结算都没有） |
| Listing 销量 | ✅ 42 条（近 7 天） | 有聚合销量，但口径是**付款/备货统计**，非卖家中心今日/7/30 |
| SKU 销量 | ❌ 0 条 | 文档：需「销售管理」有 SKU 或插件采过 |
| 库存表现 | ❌ 0 条 | 店小秘自有仓，不是 Temu 卖家中心 `warehouse_available_stock` |
| 利润 API | ❌ 全 0 | 文档：需插件采申报价 + 财务模块设采购成本 |

### 与 CrossHub 四 Tab 字段对照

| CrossHub 需要 | 店小秘能否提供 | 说明 |
|---------------|---------------|------|
| `son_today_sales` / 7日 / 30日 | ❌ | 店小秘是「当日 API 快照」或「插件 30 天历史」，不是卖家中心 subOrderList 口径 |
| `warehouse_available_stock` | ❌ | 卖家中心仓内库存；店小秘只有 ERP 自有仓 |
| `cost` / 亏损 Tab | △ | 需在店小秘手工维护采购成本 + 插件采价；当前为 0 |
| 滞销 / 库存预警算法 | ❌ | 依赖上述字段，无法直接复用 |
| 竞店发现（TM-A06） | ❌ | 店小秘无此模块 |
| 多租户隔离 | ❌ | 每租户需独立店小秘账号 + Cookie/Token |

### 最终建议

1. **主链路**：继续 Temu 卖家后台 Agent（先 TM-P4 修 ingest 401）  
2. **店小秘**：仅作**可选财务补充**（结算/利润），且须：同一 Temu 店授权到店小秘 → 销售管理点「更新数据」→ 安装插件完成采集 → 在店小秘录入成本  
3. **不建议**把 CrossHub 运营四 Tab 迁到店小秘：数据模型、实时性、多租户、竞店均不满足  
4. **即使**未来接店小秘，也是新适配层（字段映射 + Cookie 池），工作量不小于修好现有 Agent，收益更低  

---

## 10. 验收用例速查（TM-A*）

| ID | 状态 | 说明 |
|----|------|------|
| A01 | ✅ | 助手离线禁用 |
| A02 | ✅ | 未登录/未选店文案 |
| A03 | ✅ | 浏览器：引导展示→登录选店→就绪 |
| A04 | ✅ | job `9164c244` success；`report_time=2026-07-28`；无 ingest 401 |
| A05 | ⚠️ | 有数；滞销已修待重载前端 |
| A06 | 🔧 | 代码修复：遇登录关 Playwright 空白页 → 开真实 Chrome；错误码 `COMPETITOR_LOGIN_REQUIRED`；API `POST /api/temu/frontend-login/open`；待 Helper 重建 + 人工登录后复验 |
| A07 | ⚠️ | 可入队，未 success |

---

## 11. 交接记录（按时间追加，勿删历史）

### 2026-07-31（午·完整基建交接文档）

- **产出**：`docs/完整项目交接文档-2026-07-31.md`  
  含外部访问地址、服务器 Docker（crosshub-java/express）、Nginx `crosshub.conf` 反代表、宿主机目录、禁止端口、Helper 铁律、下一动作与事故索引。  
- **实勘**：`crosshub-java` → `127.0.0.1:18080`；`crosshub-express` → `127.0.0.1:18081`；SPA → `/opt/1panel/www/sites/www.yoto.work/index/crosshub/`；反代 → `.../proxy/crosshub.conf`。  
- **关联**：根目录 `全量项目交接提示词.md`（可粘贴开工指令）。

### 2026-07-31（早·SOE 修复 + force 补跑结局）

- **修复**：
  - `TemuAgentService`：旧扁平 snapshot 本地升级为 `sessions[]`；`mergeSessionRow` 改读 `loadStoredSessionBaseline`，切断死递归。
  - `PlatformDailySyncService`：`catch (Throwable)` 隔离单租户 Error。
  - 单测 `TemuAgentServiceSessionSnapshotTest`：先红 StackOverflow → 后绿 2 passed。
- **部署**：JAR-only 重建 `crosshub-java`（SKIP_DB）。
- **Force 补跑**（HangZhou tid=5）：
  - Temu：`enqueued` → Helper 领取 `temu_crawl`（**SOE 已消失**）
  - Amazon：二次补跑 `amz_sync_f0456a3e` → **success**
  - AE：`CRAWL_PYTHON_ENV`（已知，非本次范围）
- **故事文档结局已补**：根目录 `2026-07-31-daily-sync-stackoverflow-bug-story.md` §11。

### 2026-07-31（早·09:30 日批监控）

- **Helper**：在线、`agent_status=running`、紫鸟在线、心跳新鲜；**未领到今日任务**（队列空、`last_task` 空）。  
- **调度**：`01:30:00Z`（上海 09:30）已触发，注册租户 2 个。  
  - tenant **1**：`temu/amazon=failed_agent_offline`，AE 无账号。  
  - tenant **5（HangZhou）**：处理中触发 **`StackOverflowError`**，日批中断，**无今日入队**。  
- **根因**：`TemuAgentService.readSessionSnapshot` 在无 `sessions` 字段时调 `mergeSessionRow`，后者再调 `readSessionSnapshot` → 死递归。  
- **面试复盘文档（仓库根目录）**：`2026-07-31-daily-sync-stackoverflow-bug-story.md`  
- **下一步**：先修该递归并 redeploy，再补跑今日日批。

### 2026-07-31（早·线上部署 amazon/sync-jobs）

- **动作**：`mvn -DskipTests package` → `_deploy_java_jar_only.js` 上传 `/data/crosshub/app.jar` 并重建 `crosshub-java`（**SKIP_DB**，未覆盖生产库）。  
- **验收**：`GET https://www.yoto.work/api/agent/amazon/sync-jobs?tenant_id=5` → **200**，返回 `items`/`unread`；本机面板 `/api/ops/messages?tenant_id=5` 已走远端数据，不再回退本地空表。

### 2026-07-31（早·Helper 强制线上后端）

- **用户铁律**：Sync Helper **默认必须走线上** `https://www.yoto.work` 真实联调；**除非用户主动要求**，禁止切 `localhost:18080`。  
- **现场根因**：面板「Agent 异常」= Helper 误配 `java_api_url=http://localhost:18080`，本机 Java 未起 → WinError 10061。  
- **处置**：
  - 已改 `dist/.../config.json` → `https://www.yoto.work`
  - 代码默认值同步：`agent/config.py`、`sync_helper_app.py` 不再静默回落本地
  - 规则写入 `AGENTS.md` / `CLAUDE.md` / `D:\NIUBI\AGENTS.md` / 本交接 §1
- **验证**：Helper 已重启；`API=https://www.yoto.work`；面板 `agent_status=running`；`/api/tenants` 已拉到线上租户（含 tid=5）；生产 heartbeat 200。

### 2026-07-30（晚·保存当前工作全量快照）

- **动作**：按当前工作区状态落盘快照 `docs/progress-snapshot-2026-07-30.md`，用于冻结现场并支持后续接手续作。  
- **快照信息**：分支 `feat/amazon-v2-ops-crawl`，HEAD `1091976`；工作区统计 `total=155`（`modified=65`，`untracked=90`）。  
- **包含内容**：本轮关键产出（Amazon 回收重试/运维日志修复、Temu 串号 Bug Spec）、当前焦点与最短续跑路径。  
- **说明**：快照仅存档，不替代 commit；交接主文档仍以 `docs/dev-handover.md` 为准。  

### 2026-07-30（晚·Temu 多账号 Profile 误迁移 Bug Spec）

- **问题确认**：用户新增 `YONI / 13861260796` 后点击 Temu 同步，浏览器登录页带出了旧账号 `18061740604` 的自动填充信息，属于**跨账号本地 Profile 污染**。  
- **已收集证据**：
  - `helper-runtime.log` 出现 `[Profile] migrated legacy tenant-5 → account-13861260796`；
  - `tenant-5/.crosshub-session.json` 指向旧店铺 `Gourami`；
  - `tenant-5/Default/Login Data`、`account-18061740604/Default/Login Data`、`account-13861260796/Default/Login Data` 的 SHA256 完全一致；
  - `account-13861260796` 目录体量异常大，证明不是空白首次建档。
- **根因定性**：`backend/python/app/temu/profile_migration.py` 的 `maybe_migrate_legacy_temu_profile()` 仅依据 `ready` / Cookie 大小 / 目标目录空不空就执行 `copytree`，**没有校验 legacy profile 的账号归属**，把旧共享目录直接迁进了新账号目录。  
- **本轮产出**：新增正式修复 Spec  
  `docs/superpowers/specs/2026-07-30-temu-profile-migration-account-isolation-design.md`
  ，明确要求：
  - 不再迁移“无法证明归属”的 legacy flat profile；
  - 即使允许迁移，也不复制 `Login Data`；
  - 已污染账号目录必须清理后重登；
  - 新账号首次 cache 不能继承旧账号 `ready/mall_id`。
- **下一步**：按该 Spec 落代码，随后删除 `account-13861260796` 脏目录并做真实登录回归。

### 2026-07-30（晚·修复两条审查缺陷）

- **证据 1（迟到完成回写）**：新增 `backend/java/src/test/java/com/crosshub/agent/service/impl/AgentServiceImplTest.java`；红灯阶段 `completeTaskIgnoresLateCompletionForAlreadyFailedTask` 失败为 `expected: failed but was: success`，证明超时回收后的旧任务仍会被迟到成功回写。  
- **修复 1**：
  - `AgentServiceImpl.completeTask` 对已终态（非 pending/running）任务直接忽略迟到 completion，不再覆写状态、不再触发 bridge。
  - `AmazonSyncServiceImpl.onAgentTaskCompleted` 增加 `ACTIVE` 防线，避免已终态 job 再次被置回 `running`。
- **证据 2（运维日志数据源）**：新增 `backend/python/tests/test_tray_ops_messages.py`；红灯阶段在 mock 远端 API 成功时仍返回 `unread=0`，stderr 明确打印 `should not touch local db`，证明面板当时仍在读本地 SQLite。  
- **修复 2**：
  - Java 新增 Agent 端接口 `GET /api/agent/amazon/sync-jobs?tenant_id=...`，由服务端统一从 `amazon_sync_job` 返回最近 60 条任务、失败原因、失败时间、重试次数、是否重试耗尽。
  - Helper `tray_app.py` 改为**优先走远端 API** 拉取运维日志，仅在 API 异常时才回退本地 DB。
- **验证**：
  - `mvn -f backend/java/pom.xml -Dtest=AgentServiceImplTest test` → **PASS**
  - `PYTHONPATH=backend/python py -m pytest backend/python/tests/test_tray_ops_messages.py -q` → **1 passed**
- **运行态补充**：
  - `restart-java-api.ps1` 已执行，本地 `:18080` 已换到新代码。
  - 重建 Helper exe 后，`dist/.../config.json` 会回落成占位 token + `https://www.yoto.work`；本次已手动恢复为本地联调值（`agent_token=7903...6805`、`java_api_url=http://localhost:18080`）并重启 Helper。
  - 冒烟：`GET http://127.0.0.1:18080/api/agent/amazon/sync-jobs?tenant_id=5` 与 `GET http://127.0.0.1:18766/api/ops/messages?tenant_id=5` 均已返回 Amazon 任务列表，不再是本地空库。
- **下一步**：重启 Java / Helper 后做一次真实 Amazon 同步验证，确认面板日志与远端任务状态一致。

### 2026-07-30（晚·Amazon 超时回收 + 重试 + 运维日志入口）

- **问题复盘**：`amazon_sync` 存在旧 `running` 任务长时间不回收，Agent 侧触发新同步时在 `/api/agent/amazon/sync` 落成 500「服务器繁忙」，面板无法区分是冲突还是其他异常。  
- **Java 修复**：
  - `AgentController` 对 `AmazonSyncConflictException` 显式返回 **409** + `AMAZON_SYNC_IN_PROGRESS`，不再走全局 500。
  - `AmazonSyncServiceImpl` 将 Amazon 活跃任务 TTL 收敛到 **6 分钟**（pending 3 分钟），并在任务失败后按 `retry_count` 自动补发下一次任务，**最多重试 2 次**。
  - 失败/成功都会把 `retry_count`、`max_retry_count`、`retry_exhausted`、`last_failed_at` 写入 `result_summary`，供面板展示。
  - `AgentServiceImpl` 对 `amazon_sync` 的 stale TTL 调整为 **6 分钟**，超时任务会被回收为 failed，并触发 Amazon 桥接逻辑进入自动重试链路。
- **Helper 修复**：
  - 新增 `/api/ops/messages?tenant_id=`，读取 `amazon_sync_job` + `platform_account`，输出任务状态/失败原因/失败时间/重试次数/是否重试耗尽。
  - 面板 `index.html` 顶栏新增「**运维日志**」按钮和红点；右侧抽屉展示 Amazon 同步状态列表，含失败详情与重试进度。
- **本地校验**：`mvn -f backend/java/pom.xml -DskipTests compile` 通过；`py -m compileall backend/python/agent/tray_app.py` 通过。  
- **下一步**：重建 Helper exe 并点击 Amazon「↻ 同步」做实测，验证 409 提示、6 分钟超时回收、重试耗尽红点与日志明细。

### 2026-07-30（午·重建 Sync Helper.exe）

- **根因**：旧 exe 托盘模式 `run_agent_loop` **无 heartbeat** → 面板在、线上 `agent_online=false`；打包默认 URL 曾误写 `/crosshub-api`
- **修复**：`agent/tray_app.py` 补心跳线程；`build-sync-helper-exe.ps1` 默认 `https://www.yoto.work`
- **动作**：重建 exe + `setup-sync-helper-config` 写回 token；自启改为 **Mode=Exe**；启动新 exe
- **验证**：`18765/health=ok`；面板 `18766` status=running；生产 HangZhou Agent 心跳新鲜、`agent_online=true`
- **下一**：盯 07-31 09:30 日批；可评估 DY-P0

### 2026-07-29（晚·Agent 任务并发上限）

- **完成**：
  - Java `AgentTaskConcurrency` + `pollTasks`：按 `session_key`/`browser_id` 互斥；默认 Temu≤3 / AE≤2 / Amazon≤1 / 全局≤5（`crosshub.agent.concurrency`）
  - Helper / `agent.main`：`ThreadPoolExecutor(AGENT_DISPATCH_WORKERS=5)` 并行 dispatch，轮询不阻塞在途任务
  - Temu 多会话爬取：`crawl_temu_sales_all_sessions` 线程池并行（`TEMU_CRAWL_MAX_PARALLEL` 默认 3）；单 Job 模型不变
- **验证**：`AgentTaskConcurrencyTest` PASS；`test_agent_dispatch_parallel` PASS；本地 Java `:18080` 已重启；Helper 已重打包
- **配置**：`application.yml` → `crosshub.agent.concurrency.*`；Helper 环境变量 `AGENT_DISPATCH_WORKERS`
- **下一**：重启本机 Helper 冒烟日批/刷新；生产 Java 已 JAR-only 重建 `crosshub-java`（全量 deploy 上传卡住后改用 `_deploy_java_jar_only.js`）

### 2026-07-29（晚·全平台 Profile 隔离 + Helper 矩阵）

- **完成**：
  - 通用 `app/session_scope.py`：`build_session_key` / `resolve_platform_profile_dir`
  - Temu + AliExpress Profile：`tenant-{id}/account-{session_key}`（兼容旧扁平目录）
  - Amazon：仍按紫鸟 `browser_id`/oauth 隔离（无本地 Profile）
  - Helper 托盘面板：选租户 → 全平台矩阵 → 「+ 添加账户」写 `platform_account`（与 Boss 绑定同源）
  - Agent API：`/api/agent/tenants`、`GET/POST/DELETE /api/agent/platform-accounts`
- **验证**：`tests/test_session_scope.py` + `test_temu_session_scope.py` PASS；Helper 已重打包重启 `18765/health=ok`
- **下一**：面板实测多账号登录隔离；Boss 刷新核对绑定；Amazon 同步仍走紫鸟

### 2026-07-29（午·生产部署 + 竞店 URL 说明 UI）

- **部署**：`deploy-server.ps1` + `CROSSHUB_SKIP_DB_UPLOAD=1` exit 0（Java V17 + Python worker + FE）  
- **UI**：竞品分析「手动添加竞店」增加黄条格式说明 + 输入框实时校验 + 示例 mall 链接  
- **下一**：强刷验收 UI；铅坠等历史行改 mall URL  

### 2026-07-29（午·SDD 收口 + 终审修复）

- **Tasks 1–5**：本地实现完成（未 commit）；证据 `attachments/2026-07-29-monitor-cooldown-url-evidence.md`；ACC 1/3/4/5/7 PASS，2/6 PARTIAL  
- **终审 Critical C1**：去掉 FE `assertPlatformCrawlAllowed` 对 monitor trigger 的平台 3h 误拦  
- **终审 Important I1**：`analyzeBackendCompetitors` 跳过非 mall URL  
- **下一**：用户确认后 **commit（仅本包文件）** → 生产 `CROSSHUB_SKIP_DB_UPLOAD=1` 部署 Java+Python+FE → 浏览器 ACC-6 / 铅坠改 mall URL  

### 2026-07-29（午·Monitor cooldown Task 5 ACC）

- **完成**：本地 ACC-1/3/4/5/7 **PASS**；ACC-2 **PARTIAL**（DB 模拟 `monitor:{id}` 冷却，无 Helper success 闭环）；ACC-6 **PARTIAL**（FE 单测 + 代码确认强制对话框，无浏览器 E2E）  
- **证据**：`docs/superpowers/specs/attachments/2026-07-29-monitor-cooldown-url-evidence.md`  
- **Spec 状态** → 已实施 · 本地验收中；报告 `.superpowers/sdd/task-5-report.md`  
- **未 commit / 未生产部署**（须 `CROSSHUB_SKIP_DB_UPLOAD=1`）  
- **运营**：历史商品 URL（铅坠等）需人工改为 mall；本包不自动修  
- **下一动作**：DY-P0 评估 / RC-COST；或生产 SKIP_DB 部署后补绿 ACC-2/6  

### 2026-07-29（午·Monitor cooldown Task 4）

- **完成**：`temuMonitorUrl.js`（mall_id / 拒商品页）；`saveBackendCompetitor` 前端校验 `MONITOR_TARGET_URL_INVALID`；`analyzeBackendCompetitors` 默认 `force:false`；`CompetitorAnalysis` 冷却二次确认强制刷新 +「链接非店铺」标签  
- **测试**：`temuMonitorUrl` / `temuCompetitorsApi.routes` / `appErrorCode.monitor` 均 PASS  
- **报告**：`.superpowers/sdd/task-4-report.md`  
- **未 commit**（用户未要求）  
- **下一动作**：ACC-2 / 浏览器联调验收

### 2026-07-29（午·Monitor cooldown Task 3）

- **完成**：`record_monitor_crawl_success(conn, tenant_id, target_id)` 写入 `scope=monitor:{target_id}` + `ON CONFLICT(tenant_id, scope)`；monitor 成功路径停用旧 `record_tenant_crawl_success`（platform / `ON CONFLICT(tenant_id)`）
- **测试**：`py -m pytest backend/python/tests/test_monitor_cooldown_scope.py -q` → 3 passed（需 `PYTHONPATH=backend/python` 或 cwd=`backend/python`）
- **报告**：`.superpowers/sdd/task-3-report.md`
- **部署注意**：须先有 Java V17 表结构再跑 worker；未 commit
- **下一动作**：Task 4（FE）

### 2026-07-29（午·Monitor cooldown Task 2）

- **完成**：`TemuMonitorUrlValidator`（mall_id / 拒 `-g-\d+.html`）；`AppErrorCode.MONITOR_TARGET_URL_INVALID`；`createTarget`/`updateTarget` 对 temu+shop+store_listing 校验并 canonicalize；`trigger` 改 `assertAllowed(..., monitorScope(id), force||bypass)`  
- **验证**：`TemuMonitorUrlValidatorTest` 2 PASS；ACC-4 商品 URL→400；ACC-5 mall URL→200；报告 `.superpowers/sdd/task-2-report.md`  
- **未 commit**（用户未要求）  
- **下一**：Plan Task 3（Python worker 写 `monitor:{id}`）  

### 2026-07-29（午·Monitor cooldown Task 1）

- **完成**：`V17TenantCrawlCooldownScopeMigration`（`(tenant_id, scope)` PK）；`TenantCrawlCooldownService` scope API（platform 3h / `monitor:*` 30min）；`CrawlCooldownException`+`ApiExceptionHandler` 按 scope 文案  
- **验证**：`TenantCrawlCooldownServiceTest` PASS；重启 Java 后 `PRAGMA table_info` 含 `scope`；报告 `.superpowers/sdd/task-1-report.md`  
- **未 commit**（用户未要求）  
- **下一**：Plan Task 2（URL 校验 + Monitor trigger scope）  

### 2026-07-29（午·竞店冷却/URL Plan）

- **Plan**：`docs/superpowers/plans/2026-07-29-monitor-cooldown-url.md`（5 Tasks）  
- **要点**：V17 scope PK；Monitor 不查 platform；Python success 改写 `monitor:{id}`（今日发现误写 platform）；FE 去默认 force + 强制确认  
- **下一**：选执行方式开工  

### 2026-07-29（午·竞店冷却/URL Spec）

- **产出**：`docs/superpowers/specs/2026-07-29-monitor-cooldown-url-design.md`（待评审）  
- **方案**：冷却 scope=`platform` | `monitor:{id}`；Temu shop URL 强制 mall_id；去掉长期默认 force  
- **下一**：用户确认 §10 → writing-plans  

### 2026-07-29（午·竞店 trigger 429 冷却）

- **现象**：`POST .../targets/mt_84d36ece…/trigger` → 429 `CRAWL_COOLDOWN`；该 target **尚无** `monitor_job`  
- **原因**：租户级 3h 冷却（`tenant_crawl_cooldown` tid=5 `last_success_at=2026-07-29 03:24:51`，来自店铺全量同步）误伤竞店手动分析；UI 传 `force/bypass=false`  
- **修复**：`analyzeBackendCompetitors` 默认 `force+bypassCooldown`、不记冷却；trigger 请求对齐；Java `force||bypass`（本地已改，待下次全量部署）  
- **部署**：前端热更  

### 2026-07-29（午·竞店列表空表假象）

- **结论**：**已入库**（`monitor_target` tenant5 含 `mt_84d36ece…` 铅坠等；`GET /api/monitor/targets?platform=temu` → 5 条）  
- **根因**：`SearchableTable` 传 `() => props.data`，`useFuzzySearchPagination` 用 `unref(fn)` 得到函数，`Function.length===0` → 恒显示空态  
- **修复**：composables 支持 getter；SearchableTable 改 `computed(() => props.data)`；已前端热更部署  

### 2026-07-29（午·Helper 重打包连生产）

- **动作**：停源码 Agent → `build-sync-helper-exe.ps1 -JavaApiUrl https://www.yoto.work` → 写回 config → 启动 exe  
- **验证**：`18765/health=ok`；exe PID 在线；生产 `agent_online=true`（HangZhou Agent）

### 2026-07-29（午·部署四 Tab 口径更新）

- **部署**：`CROSSHUB_SKIP_DB_UPLOAD=1` → `deploy-server.ps1` 成功  
- **验收**：`/api/health=200`；`overload_products` 已按 isHot 公式收敛（不再固定 Top300）  
- **含**：爆款/备货公式对齐 + 全部店铺 UI + 前端 dist

### 2026-07-29（午·四 Tab 口径对齐）

- **爆款**：Java `overloadProducts` 改为与前端 `isHot` 同公式；列表改滤 `isHot`；`applyServerAlgorithms` 以后端 overload 覆盖 `isHot`  
- **备货**：前端 `calcRestockPlan` / `RESTOCK_CONFIG` 对齐 Java `calcReplenish`（0.7/0.3、lead=7、buffer=3、目标 15 天）  
- **选店**：支持「全部店铺」；未选店时 info 提示，不再静默空表  
- **测试**：`TemuWarningServiceImplTest`；`dev/vue-site/tests/temuOpsAlignment.test.mjs`  
- **生效**：前端改本地 Vite 即可；**Java 需再部署**（`CROSSHUB_SKIP_DB_UPLOAD=1`）后生产 overload 口径才更新

### 2026-07-29（午·Temu 四 Tab 验收 + 一致性排查）

- **Helper**：本机源码 Agent 已在线 `18765/health=ok`，生产 `agent_online=true`  
- **运营 API**（tenant5 / `report_time=2026-07-29`）：products=**424**；lose=**0**；low=**156**；inv=**72**；overload=**300**；**cost>0 = 0**  
- **结论摘要**：滞销/备货链路可用；亏损 Tab 因无成本空态（预期）；爆款徽标=前端 `isHot`，列表=「今日销量>0」，与 Java `overload`（近7日销量 Top300）**三口径不一致**  
- **并发**：同租户 crawl 有 active-job 互斥；ingest 按 shop DELETE+INSERT 事务；生产 SQLite 仍有跨平台 `SQLITE_BUSY` 历史；Profile 锁降低浏览器争用  
- **抓取≠展示风险**：ingest 覆盖 `cost` 列（展示靠 `temu_sku_cost` overlay）；只含部分店铺时仅删改这些 shop 的当日行；字段映射分→元在前端  
- **下一**：RC-COST；可选统一爆款口径

### 2026-07-29（午·生产部署 SKIP_DB）

- **命令**：`CROSSHUB_SKIP_DB_UPLOAD=1` + `scripts/deploy-server.ps1`（未上传本机 `crosshub.db`）  
- **远端**：`crosshub-java` / `crosshub-express` Up；`public_crosshub=200` `public_java=200`  
- **验收**：`POST /api/temu/frontend-login/open` → **200** `code=0 queued=true`（不再 404）；`/api/temu/shops` count=2；`agent_online=true`  
- **备注**：python-worker 镜像缺失跳过；远端 `.monitor-smoke.env` 未写，monitor API smoke 跳过  
- **下一**：可评估 DY-P0；RC-COST 后期；可选 commit

### 2026-07-29（午·RC-AUTO 开机自启）

- **交付**：`install/uninstall/start-sync-helper-autostart.ps1`；checklist `2026-07-29-rc-auto-checklist.md`  
- **本机**：已注册计划任务 **CrossHub-Sync-Helper**（At logon / Mode=Source）；`Start-ScheduledTask` → `18765/health=ok`  
- **测试**：`tests/test_sync_helper_autostart.py`  
- **下一**：生产 Java 部署；RC-COST 后期；可评估 DY-P0

### 2026-07-29（午·A06 证据落盘）

- **证据**：`attachments/2026-07-29-temu-m0-residual-evidence.md`（RC-A06 ✅）；原始 JSON `2026-07-29-a06-jp-discover.json`  
- **验收**：`POST .../discover` `fishing`/`jp`/`force` → code=0 candidates=1 sample×10 价 ¥649/603/890/1395/618  
- **清单**：Excel「清单消除」`TM-P5` → **DONE**（备注含证据路径；亏损 Tab 注明待 RC-COST）  
- **延期**：RC-COST 按用户要求后期再做  
- **下一**：RC-AUTO → 生产 Java 部署（frontend-login）；可评估 DY-P0

### 2026-07-29（午·专门排 JP 搜索页抽取）

- **根因**：`PRICE_RE` / JS `pricePattern` 只认 `$`/`R`，JP 的 `¥`/`￥`/`円` 价被滤成 0 → `COMPETITOR_DISCOVERY_NO_RESULTS`  
- **改动**：
  - `competitor_crawler.py`：日元符号/后缀；`extract_price` 取任意捕获组  
  - `competitor_discovery.py`：严格抽取同款价模式；`is_product_url` 丢掉裸 `/jp` 等非商品链  
  - 测试：`tests/test_jp_price_extraction.py`（含候选保留 + URL 过滤）  
- **验收**：源码 Agent + `POST .../competitors/discover` `{"keyword":"fishing","region":"jp","limit":10,"force":true}` → **code=0 candidates=1**，sample 价如 649/603/890/1275（¥）  
- **剩**：A06 证据附件；RC-COST；RC-AUTO；生产 frontend-login 部署

### 2026-07-29（午·Temu 残留收口开工）

- **文档**：PRD `2026-07-29-temu-m0-residual-close-prd.md`；Design `...-design.md`；证据底稿 `attachments/2026-07-29-temu-m0-residual-evidence.md`  
- **A06 启动**：Helper ok；生产 `frontend-login/open` → **404**（未部署）；discover force → **CRAWL_TIMEOUT**（90s）  
- **绕过**：本机已 `frontend_login.py --tenant-id 5 --mode manual --open-only` 拉 Chrome，待用户登录关窗后复跑 discover  
- **下一**：用户登录 → 复跑 discover；确认后 `CROSSHUB_SKIP_DB_UPLOAD=1` 部署 Java

### 2026-07-29（早·重建并重启 Helper · 含 Amazon 登录等待）

- **动作**：停旧 exe/子进程 → `build-sync-helper-exe.ps1 -JavaApiUrl https://www.yoto.work` → 写回 config → 启动新 exe  
- **验证**：`18765/health=ok`；生产心跳 `status=ok`（node `88aa865e-…`）；PID **3764** @ 09:45:30  
- **含**：Amazon `ensure_seller_logged_in_with_wait`（最多 3 次刷新 / 默认等 180s）  
- **下一**：手动/force 再跑 Amazon sync，观察 2FA 是否进入等待而非立刻 failed

### 2026-07-29（早·Amazon 登录/2FA 等待重试）

- **问题**：日批 Amazon 遇两步验证页立刻 `AMAZON_LOGIN_REQUIRED`；用户记忆的「3 次」实为 complete 上报重试，非业务重爬  
- **改动**：
  - `app/amazon/session_context.py`：`ensure_seller_logged_in_with_wait`（默认最多 **3** 次刷新检测，总等待 `AMAZON_LOGIN_WAIT_SECONDS=180`）
  - `crawl_pipeline.run_crawl`：登录检测改为等待/重试；仍失败才 failed，并保留紫鸟窗口
  - 配置：`AMAZON_LOGIN_MAX_ATTEMPTS` / `AMAZON_LOGIN_POLL_SECONDS` / `AMAZON_LOGIN_WAIT_SECONDS`
  - 测试：`tests/test_amazon_login_wait.py` **3 passed**
- **生效**：需**重建并重启** Sync Helper exe（当前运行中的旧包无此逻辑）
- **下一**：重建 exe → 手动/force 再跑 Amazon sync 验证 2FA 等待

### 2026-07-29（早·09:30 日批现场监控）

- **Helper**：exe PID 在线，`18765/health=ok`，`agent_online=true`，紫鸟 `ziniao_online=true`  
- **Temu**：job `ed165852-…` **success**，`trigger=daily_schedule`，`report_time=2026-07-29`，rows=**424** shops=**2**（01:30:01～01:32:01 UTC ≈ 09:30～09:32 CST）  
- **AE**：job `2398cdc4-…` **failed** `CRAWL_PYTHON_ENV`（预期，容器无 Python）  
- **Amazon**：job `amz_sync_47ab5c90-…` **failed** `AMAZON_LOGIN_REQUIRED`（截图落 Helper `data/amazon-captures/..._login_*.png`）  
- **顶栏**：`has_error=true` 被 AE 的 `CRAWL_PYTHON_ENV` 占位；Temu 分平台 `has_error=false`  
- **下一**：Amazon 紫鸟重新登录；AE skip 化 / Agent 化；继续 A06 / 自启文档

### 2026-07-29（早·重建 Sync Helper exe）

- **动作**：`build-sync-helper-exe.ps1 -JavaApiUrl https://www.yoto.work`（约 45s，exit 0）  
- **路径**：`dist/CrossHub-Sync-Helper/CrossHub-Sync-Helper/CrossHub-Sync-Helper.exe`；已从备份写回 tenant5 `config.json`  
- **日批策略**：源码 Agent 仍占 `18765` 待命 09:30；**未切换**到新 exe（避免双实例抢端口/任务）  
- **下一**：日批结束后可停源码 Agent，再双击新 exe；或现在确认是否立即切换

### 2026-07-29（早·提交 + 源码 Agent 待命 09:30）

- **Commit**：`1091976 feat(temu): Close M0 agent sync, daily batch, and discover path`（117 files；未含 `_dxm_cookie_tmp.txt` / `_probe_dxm_*` / `_ssh_*`）  
- **Agent**：`scripts/run-agent.ps1` → `JAVA_API_URL=https://www.yoto.work`；本机 `127.0.0.1:18765/health=ok`；`POST /api/agent/heartbeat` → `status=ok`（node `88aa865e-…`）  
- **为何源码而非 exe**：赶 09:30 日批；源码含最新 discover/Chrome 修复，无需等 PyInstaller  
- **未做**：push；A06 人工登录；成本导入  
- **下一**：盯日批结果 → A06 / 成本

### 2026-07-28（晚·重建 Sync Helper）

- **动作**：`build-sync-helper-exe.ps1 -JavaApiUrl https://www.yoto.work`；写回 tenant5 `config.json`（profile / token / API）  
- **路径**：`D:\NIUBI\SaaS-HZ_WEB_Demo\dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper\CrossHub-Sync-Helper.exe`  
- **下一**：用户启动 exe → 竞店 Discover 在线验收（遇登录应弹普通 Chrome）

### 2026-07-28（晚·buyer 空白页 + Discover 链路修复）

- **根因**：Playwright 控制页渲染 Temu 买家 `login.html` 常为空白；Discover 遇登录却「留空白页」且抛 `COMPETITOR_FRONTEND_LOGIN_REQUIRED`，Java/前端映射成 UNKNOWN，与已有 `COMPETITOR_LOGIN_REQUIRED`（应已开真实 Chrome）断链  
- **修复**：
  - 新增 `app/browser/manual_chrome.py`：释放 Playwright runtime → 开**普通 Chrome** + tenant profile  
  - `competitor_discovery.discover_raw_items`：登录/空白页检测后关 Playwright 页并自动唤起真实 Chrome，抛 `COMPETITOR_LOGIN_REQUIRED`  
  - Agent：`temu_frontend_login_open` + `open_frontend_login_window`；Java `POST /api/temu/frontend-login/open`；`AppErrorCode` 解析 `CODE: detail`  
  - Vue：竞店「打开买家前台登录」+ 登录错误告警；错误码别名贯通  
- **验证**：`pytest` 相关 **17 passed**；本地 Java `18080` 已重启  
- **未做**：Helper.exe 未重建；tenant5 人工买家登录 + A06 在线 success 未跑  
- **下一**：§1（重建 Helper → 登录 → 复跑 discover）

### 2026-07-28（午·Temu M0 缺口 Spec）

- **产出**：`docs/superpowers/specs/2026-07-28-temu-m0-gap-close-design.md`  
- **拍板**：① P0 **做真算法、禁止空态顶替**；② Discover Agent 化 **排在抖音前**（挡 DY-P0）  
- **影响**：抖音开工预估顺延 +2～3 工作日；原 TM-P5=0.25 不足  
- **下一**：出实施 plan 并按 Algo → Discover → Ops 开工  

### 2026-07-28（午后·Temu P0 接线继续）

- **前端**：修复 `mapReptileSaleToTemuProduct.js` 断裂 import/JSDoc；确认 `localStock` 可空、`daysWithoutSale` 走共享 `temuSlowAlgo`
- **算法**：`TemuWarningServiceImpl` 去掉旧 `s30==0` 门槛，改为与前端一致的「在线 + 官方仓有货 + 今日/7日无销」候选
- **成本**：新增 `V16TemuSkuCostMigration`、`TemuSkuCostService`、`POST /api/temu/sku-costs`；`TemuOperationalServiceImpl` 在 DTO 前 overlay 成本
- **竞店**：新增 `temu_competitor_discover` task type；Java `TemuCompetitorServiceImpl` 改为 insert `agent_task` + 轮询 ≤90s；Python `agent/handlers.py` 已支持执行 discover
- **验证**：`npm run build` 通过；`powershell -File scripts/restart-java-api.ps1` 通过，Java `18080` 本地已就绪
- **仍缺**：tenant5 真实成本导入、Discover 在线冒烟、如需上线则再做前端部署

### 2026-07-28（午后·Temu M0 验收 Spec）

- **新增**：`docs/superpowers/specs/2026-07-28-temu-m0-acceptance-spec.md`
- **内容**：把 TM-A04R / A05R / A06R / A08 / A09 / A10 的前置条件、执行步骤、通过标准、失败分流、证据清单单独落文
- **定位**：该文件是现场验收剧本；设计与实现仍以上级 gap-close design spec 为准
- **下一**：按验收 Spec 跑 tenant5 在线验证，补成本导入样例与 Discover Agent 结果

### 2026-07-28（午后·tenant5 在线验收）

- **产出**：`docs/superpowers/specs/attachments/2026-07-28-temu-m0-acceptance-evidence.md`
- **A04R**：通过。bearer 调 `GET /api/temu/operational` → `status=200`、`tenant_id=5`、`report_time=2026-07-28`、`products=430`
- **A08**：通过。`GET /api/platform/sync-status` 显示 `platforms.temu.has_error=false`，AE/Amazon 失败未拖红 Temu
- **A05/A10**：仅部分通过。页面已有 `133 滞销 / 16 爆款 / 62 待备货`；但全库 `cost=0`，亏损项因未导入真实成本不能判通过
- **A06R**：未通过。`POST /api/temu/competitors/discover` → `400 CRAWL_PROCESS_FAILED`；页面“暂无抓取任务记录”
- **下一**：先排查生产 Discover，再补真实成本样例复验亏损 Tab

### 2026-07-28（下午·tenant5 Discover 生产排障）

- **全量部署**：已执行 `scripts/deploy-server.ps1`
- **生产事故**：部署后 `https://www.yoto.work/api/auth/login` / `/api/temu/shops` 出现 `502`；远端 `crosshub-java` 容器重启失败，日志为 `SQLITE_CORRUPT: database disk image is malformed`
- **恢复**：备份远端坏库后，重传本地通过 `PRAGMA integrity_check=ok` 的 `backend/data/crosshub.db`，`crosshub-java` 恢复，`/api/health=200`
- **Discover 调试 1**：Java debug 透传后，生产明确返回 `未支持的任务类型: temu_competitor_discover`，确认旧 Helper/Agent 版本未接入新 task type
- **Discover 调试 2**：仅重启旧 `CrossHub-Sync-Helper.exe` 无效；改用源码 Agent 并修正 `JAVA_API_URL=https://www.yoto.work` 后，终端已看到 `执行任务: temu_competitor_discover`
- **Discover 调试 3**：本机直跑 `app.crawler.competitor_discovery.discover_competitor_candidates(tenant_id=5, ...)`，稳定复现 `COMPETITOR_BROWSER_PROFILE_UNAVAILABLE`；Playwright 根栈为 `launch_persistent_context()` → `TargetClosedError`
- **当前结论**：A06 剩余根因已收敛到 tenant5 买家侧持久化浏览器 Profile 启动失败；接口对外表现仍是 `400 CRAWL_TIMEOUT`
- **下一**：优先修 `open_temu_context()` 外围超时/报错与 tenant-5 buyer profile 可用性，再回跑 A06

### 2026-07-28（下午·tenant5 Discover live runtime 复用）

- **设计切换**：不再让 Discover happy-path 每次 `open_temu_context()` 新开 buyer-side `launch_persistent_context()`；改为复用 agent 进程内按 tenant 缓存的 live browser runtime
- **实现**：
  - `app/browser/runtime.py` 新增 stale runtime 判定后自动重建
  - `app/browser/context.py` 新增 `ManagedBrowserContext`、`get_or_create_temu_runtime()`、`close_temu_runtime()`
  - `seller_login_assist.py` 登录完成后**不再关浏览器**，保留 runtime 给 discover / 后续同步复用
  - `agent/temu_tasks.py` 的 `open_login_window()` 改为当前 agent 进程内起登录线程，不再源码态走额外子进程
  - `app/crawler/competitor_discovery.py` 改为从 live runtime `new_page()`；仅 profile 异常重试时才 close runtime + force-close profile
- **验证**：`py -m pytest tests/test_browser_runtime.py tests/test_competitor_discovery.py tests/test_context_login_wait.py -q` → **13 passed**
- **未做**：helper.exe 尚未重建/重启，tenant5 A06 线上尚未复跑
- **下一**：重建 helper、登录 tenant5、在线复跑 `POST /api/temu/competitors/discover`

### 2026-07-28（下午·tenant5 Discover 线程断点修复 + helper 复验）

- **新根因**：live runtime 接上后，线上 discover 不再报 `COMPETITOR_BROWSER_PROFILE_UNAVAILABLE`，而是先暴露 `cannot switch to a different thread (which happens to have exited)`；原因是 `temu_login_open` 在线程 A 建了 Playwright sync runtime，`discover` 在线程池线程 B 复用同对象
- **修复**：
  - `agent/temu_tasks.py`：`open_login_window()` 改为当前 agent 线程直接打开 seller 页面并创建 runtime，不再后台线程持有 Playwright
  - `agent/handlers.py`：`handle_temu_competitor_discover()` 改为当前线程直跑，不再包 `ThreadPoolExecutor`
  - 新增回归：`tests/test_temu_task_threading.py`
- **本地验证**：`py -m pytest tests/test_temu_task_threading.py tests/test_browser_runtime.py tests/test_competitor_discovery.py tests/test_context_login_wait.py -q` → **15 passed**
- **helper 复验**：
  - 重新 `build-sync-helper-exe.ps1 -JavaApiUrl https://www.yoto.work`
  - `setup-sync-helper-config.ps1` 写回线上 token / profile root
  - `CrossHub-Sync-Helper.exe` 启动后本机 `http://127.0.0.1:18765/health` → `ok`
- **tenant5 线上结果**：
  - `POST /api/temu/login/open` 成功入队
  - `POST /api/temu/competitors/discover`（`force=true`）已不再报 profile/thread 错
  - 当前返回：`COMPETITOR_FRONTEND_LOGIN_REQUIRED: Temu frontend login or verification is required before discovering competitors.`
- **结论**：方案 2 已落地并通过线上链路验证；A06 剩余阻塞从“架构断点”收敛为“buyer-side frontend 真实登录前置条件”

### 2026-07-28（傍晚·buyer 空白页 + 全量快照暂停）

- **现象**：唤起后 seller（商家中心）正常；buyer 页一度自动关闭（已修：`FRONTEND_LOGIN_REQUIRED` 时不关页）；随后 buyer `login.html` **整页空白**（tab 标题日文「ログイン」）
- **处置**：停 helper，改 `frontend_login.py --tenant-id 5 --mode manual --open-only` 拉真实 Chrome；用户选择暂停，不再继续人工登录
- **回归**：留页测试后相关套件 **16 passed**；helper 曾重建并仍可能在线（快照时 PID 47416 health ok）
- **产出**：`docs/progress-snapshot-2026-07-28.md`（全量快照）
- **下一接手**：§1；优先真实 Chrome buyer 登录 → 复跑 A06；并行准备 SKU 成本导入

### 2026-07-28（午·Temu 备货/爆款/滞销显示修复）

- **现象**：备货「暂无数据」但合计有数；爆款 `+99800%` 乱序；滞销官方仓有货但 7 日销量全 0  
- **根因**：`RestockPlanner` 绑了未解构的 `filtered`；`Math.round(s7/7)` 抹零 + 增幅哨兵 999；overload TopN 误标 `isHot`；`s7/today=0` 即判滞销忽略 s30  
- **修复**：`mapReptileSaleToTemuProduct` / `temu.js` / `temuServerAlgo` + `RestockPlanner`/`HotProductBroadcast`/`SlowMovingPanel`  
- **热修**：`enrichTemuProduct` 误写 `getSlowMovingTier`（应为 `getSlowMovingTiers`）→ 已 rebuild 部署  
- **热修2**：滞销判定过严（有 s30 即排除）导致 Tab 全空；改为「近7日无销→15日动销放缓；近30日无销→按上架天数 15/30/45」  
- **部署**：`npm run build` + `_upload_frontend_only.js` → `crosshub/`（HTTP 200）  
- **下一**：硬刷新验收；继续 TM-P5 竞店/双刷  

### 2026-07-28（午·生产部署 + 肉机→服务器闭环）

- **部署**：`deploy-server.ps1` + `CROSSHUB_SKIP_DB_UPLOAD=1`；Java/Express/前端已上线；Nginx 增加 `/api/platform`  
- **prod 配置**：`application-prod.yml` 显式 `daily-sync` 09:30；Helper example/`setup-sync-helper-config` 默认 API 改为 `https://www.yoto.work`  
- **肉机**：config 指线上；用 `.env` 的 HangZhou Agent token 心跳成功；`agent_online=true`  
- **验收**：线上 Temu crawl `7df17c5f` success（430 行）；Amazon `amz_sync_9468afa7` success  
- **未完**：开机自启；明早 09:30 现场盯日志；TM-P5；AE 未强制冒烟  

### 2026-07-28（午·重建 exe + Amazon 复测）

- **重建**：`build-sync-helper-exe.ps1` 成功；`config.json` 指向本地 `18080` + tenant5 token `7c9a75e6…` + `project_root`/Profile  
- **启动**：health `:18765` ok；紫鸟 WebDriver `:16851` open  
- **Amazon**：`POST /api/amazon/sync` `force=true` scope=`account_health` → job `amz_sync_50506b4d` **success**（~15s；home ok；不再报缺 ZINIAO_*）  
- **说明**：无 force 时可能被 `CRAWL_COOLDOWN` 429；复测需 `force/record_cooldown`  

### 2026-07-28（午·紫鸟配置核查）

- **结论**：`backend/python/.env` **已有**完整 `ZINIAO_COMPANY/USERNAME/PASSWORD/CLIENT_PATH/SOCKET_PORT`；客户端 `C:\Program Files\ziniao\ziniao.exe` 存在  
- **早前 Amazon 失败原因**：冻结 exe 未可靠注入该 `.env`（不是「项目没配紫鸟」）  
- **加固**：`ZiniaoConfig.from_env()` 每次读 `os.environ` 并按需 `load_dotenv`；`sync_helper_app` 启动时显式加载项目 `.env` 并打印「紫鸟账号配置: 已就绪/缺失」  

### 2026-07-28（午·销售管理「该区暂无权限」）

- **现象**：爬虫停在页面文案「该区暂无权限」，未纠正仍用 API 取数  
- **根因**：默认打开旧路径 `mmsos/sales-stock-management/sales-management`；全托管官方侧栏是 `stock/fully-mgt/sale-manage/main`（首页菜单实测）  
- **修复**：`TEMU_SALES_PAGE` 改官方路径；新增 `temu_nav.py` 检测「该区暂无权限」并跳转/点侧栏；失败抛错 `TEMU_REGION_NO_PERMISSION`；前端文案已加  
- **验证**：从旧 mmsos 页出发 → 自动纠正到 `fully-mgt/sale-manage/main`，`noperm=False`，可见 SKU 表；`tests.test_temu_nav` OK  
- **注意**：运维需 `build-sync-helper-exe.ps1` **重建 exe** 后生效  

### 2026-07-28（早·exe Profile/Cookie 路径）

- **根因**：冻结 exe 把 Profile 写到 `_internal\.temu-browser-profile`（空），未用历史 `backend/python\.temu-browser-profile`（含 Cookie/Login Data）  
- **修复**：`config.json` 增加 `project_root` / `temu_profile_root`；`sync_helper_app` 启动前注入 `TEMU_PROFILE_ROOT`；`config.py` 冻结态优先项目 Profile  
- **验证**：Chrome `user-data-dir` → `backend\python\.temu-browser-profile\tenant-5`；约 10s 后 `session.ready=true`（mall=Gourami，免重登）；crawl `cbec598c`/`f2cbef22` **success** rows=430 shops=2  

### 2026-07-28（早·exe 实测）

- **启动**：`CrossHub-Sync-Helper.exe` + config token tenant5；health `:18765` ok；心跳在线  
- **修复**：冻结态 Playwright 误找 `chromium_headless_shell` → `context.py` 强制本机 Chrome `executable_path`；`handle_temu_login_open` 不再立刻 live probe（避免与有头登录争用卡死）  
- **打开页面**：`POST /api/temu/login/open` → task success；本机 **Chrome 已打开** Temu `agentseller.temu.com/auth/authentication`（tenant-5 profile）  
- **抓数阻塞**：当前 Temu **会话过期**（需在已打开的 Chrome 里人工登录并选店）；登录完成后即可再 `POST /api/temu/crawl?force` 验 ingest  
- **下一步**：用户在已开 Chrome 完成登录 → 复测 crawl success  

### 2026-07-28（早·Sync Helper 独立 .exe）

- **产品**：浏览器定时任务改为运维机独立程序；**不再在运营前端展示**下载入口 / 侧栏「数据同步」日批面板 /「本机同步助手」菜单  
- **打包**：`scripts/build-sync-helper-exe.ps1` → `dist/CrossHub-Sync-Helper/CrossHub-Sync-Helper/CrossHub-Sync-Helper.exe`（已成功构建）；入口 `backend/python/scripts/sync_helper_app.py`；配置 `config.json`（`setup-sync-helper-config.ps1`）  
- **前端**：侧栏 `PlatformSyncLogPanel` 移除；菜单过滤 `boss.agent_nodes`；Temu/Amazon 引导改为「联系运维启动 exe」；AgentNodesView 仅运维状态说明（无下载）  
- **注意**：exe 需本机 Chrome；Amazon 可选紫鸟；服务端仍 09:30 日批下发  

### 2026-07-28（早·全平台日批澄清）

- **产品澄清**：每天 09:30 **不是只 Temu**，而是 **Temu + 速卖通 + Amazon** 全平台数据同步  
- **后端**：`PlatformDailySyncScheduler` 编排；AE `enqueueDailyCrawl`、Amazon `enqueueDailySync`；`GET /api/platform/sync-status` 聚合分平台 last_job/错误；删除仅 Temu 的 `TemuDailySyncScheduler`  
- **前端**：侧栏文案改为「全平台每天 09:30」；分平台展示最近任务/错误；登录打开应用三平台均不 force 爬  
- **验证**：Java 已重启；`/api/platform/sync-status` 返回 `schedule.scope_label=全平台` + `platforms.{temu,aliexpress,amazon}`  

### 2026-07-28（早·Temu 日批 09:30）

- **产品**：每天一次 09:30；打开应用只读库 + 展示同步情况/错误；手动「重新同步」仍可 force 爬  
- **后端**：`TemuDailySyncScheduler` cron `0 30 9 * * *` zone `Asia/Shanghai`；`TemuDailySyncService` 对已注册助手租户入队（离线/未登录写 failed job）；`GET /api/temu/sync-status`；配置 `crosshub.crawler.daily-sync`  
- **前端**：侧栏「数据同步」展示计划/最近任务/助手在线/错误；登录 hydrate 不 force Temu 爬  
- **验证**：Java 已重启；tenant5 `sync-status` → schedule enabled、next `07-29 09:30`、last_job `9164c244` success、`data_report_time=2026-07-28`、agent_online true  
- **注意**：日批依赖本机 Agent 常驻（有头浏览器）；明早 09:30 看 Java 日志 `Temu daily sync triggered`  

### 2026-07-28（早·TM-P3）

- **完成**：`temuApi.js` session/profile 轮询退避（2s→5s）；`TemuLoginGuide` 助手离线禁用「打开登录窗口/我已完成登录」+ `TEMU_AGENT_OFFLINE` 文案；引导可见时轻量轮询最多 20 次；`TemuModuleView`/`platformSync` 刷新路径放宽 attempts 以支持数分钟登录  
- **结论**：TM-P3 代码完成；清单待标 DONE  
- **另**：就「未开网站是否丢日数据」给出全局分析（见对话汇报）；现状依赖登录后侧栏自动同步 / 手动刷新，**无服务端日批**  

### 2026-07-29（Temu 多卖家账号会话）

- **完成**：一租户多 Temu 卖家账号 — Profile 按登录账号分组（`tenant-{id}/account-{key}`）；`temu_crawl` 遍历 `seller_sessions` 逐账号 `switch_mall`；前端登录引导按卖家账号展示状态/打开登录  
- **关键文件**：`app/temu/session_scope.py`、`TemuSellerSessionService.java`、`temu_crawler.py`（`crawl_temu_sales_all_sessions`）、`TemuLoginGuide.vue`  
- **兼容**：旧 Profile `tenant-{id}` 在 `default` 会话仍可用；需 **重打包 Helper** + 重启 Java 后生效  
- **操作**：设置→账户绑定 登记各店（同账号 `account` 字段一致）→ 登录引导里每个卖家账号点「打开登录」→ 全部就绪后刷新数据  

### 2026-07-28（午·隐藏运营同步/助手入口）

- **产品口径**：任何成员只看数；同步仅肉机 Helper + 服务端 09:30 日批；网页不展示手动同步/助手下载  
- **实现**：`opsSyncPolicy.js`（`OPS_MANUAL_SYNC_ENABLED=false`）  
  - Temu：隐藏「刷新数据」+ `TemuLoginGuide`；空态改只读提示  
  - 侧栏：去掉「重新同步」；助手文案改为「运维节点」；登录不再 auto-crawl  
  - Amazon：隐藏一键刷新/集成引导入口；错误文案改为联系运维  
- **部署**：已 `npm run build` + 上传 `www.yoto.work/crosshub/` 静态资源  
- **下一**：用户硬刷新验收 UI；继续 TM-P5  

### 2026-07-28（午·模拟日批下发）

- **动作**：生产 `POST /api/platform/daily-sync/run?force=true`（tenant 5 / HangZhouYiTuo），不等 09:30  
- **Temu**：`a8d2b61c` **success** 430 行 / 2 店；session 当时 `ready=true`  
- **AE**：`CRAWL_PYTHON_ENV`（服务器无 Python，预期失败）  
- **Amazon**：日批 INSERT `SQLITE_BUSY`；随后 manual force 入队成功但执行 `AMAZON_LOGIN_REQUIRED`（紫鸟需重登）  
- **注意**：二次 force 时 Temu session 未 ready → 又写了一条 failed last_job（`979bdb1e`）；真实成功以 `a8d2b61c` 为准  
- **结论**：服务器→Helper→Temu 回传链路可用；明早 09:30 仍需 Helper 常驻 + Amazon 登录态  

### 2026-07-28（早·TM-A04 端到端通过）


- **完成**：用户登录 Temu 卖家后台并选店后，点「我已完成登录」→「刷新数据」  
- **结果**：job `9164c244` **success**（09:26:26～09:28:15）；`report_time` **2026-07-27 → 2026-07-28**；sale 3177→3607  
- **页面**：今日销量 41 / 库存 8717 / 300 SKU；侧栏「已同步 430 条销售数据」；登录引导消失  
- **结论**：TM-P4 / TM-A04 闭环；下一动作 TM-P3 或 TM-P5  

### 2026-07-27（晚·TM-P4 浏览器测试）

- **完成**：`HangZhouYiTuo` tenant5 全流程浏览器测试；记录见 `docs/browser-test-tm-p4-2026-07-27.md`  
- **页面变化**：刷新前黄色登录引导 →「正在检查 Temu 登录状态」→「登录已完成，正在同步」→ 侧栏 temu泰州 同步中 → 失败顶栏 `Failed to fetch`  
- **验证**：job `94c9d05c` **未再出现 ingest 401**；TM-P4 拦截路径修复有效  
- **阻塞**：Playwright 在 Temu 页内 fetch kwcdn 失败；`report_time` 仍 2026-07-22  
- **待办**：排除网络/会话后复测 A04 success  

### 2026-07-27（晚·TM-P4）

- **完成**：定位 ingest 401 根因：`WebConfig` 未把 `/api/agent/temu/**` 纳入 `AgentAuthInterceptor`，`agentContext` 为空导致 `Agent 未认证`  
- **修复**：`backend/java/src/main/java/com/crosshub/config/WebConfig.java` 增加 `"/api/agent/temu/**"` 拦截路径  
- **修复**：`backend/java/src/main/java/com/crosshub/temu/service/impl/TemuCrawlServiceImpl.java` 在 `triggerCrawl` 增加 `session.ready` 前置校验（未登录/未选店直接返回业务错误，不再入队）  
- **验证**：两次 `mvn -f backend/java/pom.xml -DskipTests compile` 通过；重启 Java 后 `POST /api/agent/temu/ingest`（携带 Agent Token）smoke 返回 200  
- **待办**：tenant5 登录选店后复跑 A04（确认真实 crawl success）  

### 2026-07-30（Agent Profile Sync M0 代码）

- **完成**：按 `docs/superpowers/plans/2026-07-30-agent-profile-sync.md` 落地 Java V18 `agent_browser_profile`、`AgentProfileService` + `/api/agent/profiles`；Python `profile_bundle.py` / `profile_sync.py` + context/login/Helper 挂点；`TemuAgentService` 读聚合（有 bundle 行）；docker-compose + `crosshub-proxy.conf` 12m  
- **测试**：`AgentProfileServiceTest` 5 passed；`test_profile_bundle.py` + `test_profile_sync.py` 7 passed  
- **本地**：`restart-java-api.ps1` → `18080` ready  
- **剩**：生产部署；Helper 重建 exe；AP-01/AP-02 证据；面板 M0.5 云端状态卡片  

### 2026-07-27（晚·复审）

- **完成**：阅读店小秘官方 Temu 文档（授权/销量/采集插件/平台结算）；对照复审 Cookie 实测  
- **文档结论**：店小秘 Temu 数据 = Temu 官方 Token（销售管理每晚同步）+ **浏览器插件手动采集**（申报价/30 天销量/结算）；**无第三方 Open API**  
- **实测补充**：`lastSyncTime*` 全 null、插件采集记录 0 条 → 当前账号只配置了店铺授权，**未完成销售管理同步与插件采集**  
- **建议维持**：不切换主数据源；优先 TM-P4  

### 2026-07-27（晚）

- **完成**：店小秘 Cookie 实测 — 会话有效；`statSalesPageList` 可拉 61 条 Listing 销量；评估结论写入 §9.1  
- **发现**：店小秘账号店铺与 tenant5（Gourami）不匹配；运营四 Tab 所需字段无法从店小秘完整获取  
- **建议**：不切换主数据源；优先 TM-P4 ingest 401  

### 2026-07-27

- **完成**：TM-P1 基线；TM-P2a P0 假在线；TM-P2 session 语义与文案；TM-P5 滞销 Tab bug 修复；docs 快照；Git docs 忽略策略  
- **验收**：四 Tab / 竞店 / 双刷冒烟 — A05 部分、A06/A04 失败  
- **遗留**：TM-P4 ingest 401（最高优先级）；TM-P3 退避；TM-P5 余量；大量代码未 commit  
- **下一接手**：§1 下一动作  

---

### 2026-08-20（爬虫浏览器内置化：默认改用 Playwright 内置 Chromium）

- **背景**：用户反馈爬虫依赖本机公共 Chrome 的流程太麻烦，改为调用 Playwright 内置 Chromium，无需本机安装浏览器
- **改动**（9 文件，未提交）：
  - `app/config.py`：`TEMU_BROWSER_CHANNEL` 默认由 `chrome` 改为空（内置 Chromium）；显式设 `chrome`/`msedge` 仍可切回系统浏览器
  - `app/browser/context.py`：新增 `_bundled_chromium_ready()` 探测内置浏览器；Temu `_launch_kwargs` 默认内置，冻结态且内置缺失时回退本机 Chrome/Edge
  - `app/browser/aliexpress_context.py`：AE 工厂同逻辑切换
  - `agent/douyin_tasks.py`：抖音工厂同逻辑切换（原先无视 `BROWSER_CHANNEL`，现已对齐）
  - `.env` / `.env.example`：`TEMU_BROWSER_CHANNEL=` 置空
  - `README.md` / `backend/README.md`：`playwright install chrome` → `install chromium`
  - `scripts/build-sync-helper-exe.ps1` / `setup-temu-login.ps1`：文案同步
- **不动**：1688 与竞品快照本就用内置 Chromium；Amazon 走紫鸟 WebDriver + CDP（账号隔离架构，不改）；`manual_chrome.py` 买家侧人工登录刻意用真实 Chrome（Playwright 页面登录空白问题），保留
- **验证**：本机 Playwright 1.60 所需 chromium-1223 已缓存；三平台 launch kwargs 实测无 channel/executable_path；`TEMU_BROWSER_CHANNEL=chrome` 覆盖生效；相关 21 测试通过；全量测试失败 8 项均为改动前既有问题（HEAD 基线 11 项），零新增回归
- **遗留**：① 部署/重建 Helper exe 的目标机需先 `py -m playwright install chromium`（冻结态无内置浏览器时自动回退本机浏览器，不会崩）；② 若后续发现内置 Chromium 被 Temu/AE 风控识别，可用 `TEMU_BROWSER_CHANNEL=chrome` 一键切回；③ 本次改动未提交，与既有未提交面（agent/main.py、tray_app.py、sync_helper_app.py、crosshub-proxy.conf）并存

---

### 2026-08-27（生产事故修复：拼多多导航 404）

- **现象**：线上 https://www.yoto.work/crosshub/ 点击「拼多多」导航，`/api/pdd/session`、`/api/pdd/orders`、`/api/pdd/product-analytics`、`/api/pdd/peer-bestsellers`、`/api/pdd/products`、`/api/pdd/issues`、`/api/pdd/operations/overview` 全部 404
- **根因**：不是部署漏传文件。生产 Java 容器（`crosshub-java`，`/app/app.jar`）含完整拼多多控制器（本机直连 18080 返回 401 而非 404）；真正原因是生产 Nginx 反代片段 `crosshub.conf` 只有 18 个 location，缺 `/api/pdd`、`/api/taobao`、`/api/sync-logs` 三个转发块，请求没被转给 Java
- **修复**：本地 `deploy/crosshub-proxy.conf` 补上三个 location（pdd/taobao 带 600s 超时），上传替换生产配置，备份 `.bak.20260827T08362`，`openresty -t` 通过后 `openresty -s reload`（容器 `1Panel-openresty-UN3Y`）
- **验证**：HangZhouYiTuo 登录取 token 后，9 个端点全部 200（pdd session/orders/product-analytics/products/issues/peer-bestsellers/operations/overview、taobao session、sync-logs）
- **教训**：新平台接入时，后端控制器 + 前端代理（Vite）+ 生产 Nginx 反代三处必须同步，缺一即生产 404

---

*本文路径固定：`docs/dev-handover.md` — AGENTS.md 强制读写。*

---

### 2026-08-28（拼多多同步加固 + 部署上线）

- **背景**：上一位 AI（千问）断连时遗留未提交的拼多多改动；本次收尾、提交并部署生产。
- **改动**（commit `c975163`，7 文件）：
  - `pdd_tasks.py`：频控重试 3→5 次、退避 5s→8s+随机抖动；订单最大页数 60→200；新增 d90 窗口；默认同步窗口 today→d90；非订单爬取间隔 0.3s→1.5s
  - `PddOpsService.ingestProducts`：商品入库改为全量替换（先删旧再写，含下架），按 product_key 去重，空列表不删除防误清空
  - 新增 `V73PddOrderIndexMigration`：pdd_order / pdd_product 查询索引（生产日志已确认 applied）
  - 三处 Java 注释补 d90；版本 `2026.08.28.1` → `2026.08.28.2`
- **测试**：pytest 拼多多 37 passed；Java `mvn compile` 通过
- **部署**：
  - Java：`_deploy_java_pdd_20260828.js`（仿 `_deploy_java_only.js`，无 glob 依赖）上传 jar + Dockerfile → docker build → `crosshub-java` 重建；`/api/helper/update-info` 返回 2026.08.28.2
  - Helper：main 仓库 dist 重建 + 打包 zip（95.9MB，SHA256 `ceefc727…`）上传生产 `/crosshub/downloads/CrossHub-Sync-Helper.zip`
  - 本机 Helper：工作树 `sync-helper-bat-session` 源码重建（含新 pdd_tasks.py + 未提交 connect-ticket 改动），配置 token 原样保留
- **遗留**：
  - 工作树 `feat/sync-helper-bat-session` 的 connect-ticket SDD 改动仍未提交（17 文件，独立于本次 PDD 范围）
  - 前端 d90 预设未加（PddDashboardPanel/PddOrderDetailsPanel 仍只到 d30）；agent 侧默认 d90 已生效
  - `~/.codex/config.toml` 的 wire_api 曾为非法值 `chat/completions` 导致沙箱异常，已修复为 `responses`（与本仓库无关）
