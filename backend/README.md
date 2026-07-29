# CrossHub Temu 后端（项目内独立）

Python 负责 **爬数 + 入库**，Java 负责 **读 API + 预警算法 + JWT 认证**。  
共用 SQLite：`backend/data/crosshub.db`。

## 架构

```
py login.py          ← 首次手动登录 Temu（持久化 Cookie）
py crawl.py          ← Playwright 调卖家后台 API 爬数（或页面点「刷新」由 Java 调用）
    ↓ 写入 SQLite
backend/data/crosshub.db
    ↓ JPA 读取
Java API (:18080)
    ↓
Vue TemuModuleView（刷新数据 → POST /api/temu/crawl → 轮询 → 重载）
```

---

## 0. 安装 JDK / Maven（本机未装时）

```powershell
cd d:\NIUBI\SaaS-HZ_WEB_Demo
powershell -ExecutionPolicy Bypass -File scripts\setup-java.ps1
. .\scripts\env-java.ps1
```

JDK 与 Maven 会安装到 `tools/jdk-17`、`tools/maven`（便携，不改系统环境）。

---

## 1. Python 环境与 Playwright

```powershell
cd backend/python
py -m pip install -r requirements.txt
py -m playwright install chrome
```

复制配置：`copy .env.example .env`

### 首次登录 Temu（必做）

```powershell
py login.py
```

- 默认 **有头模式** + **本机 Chrome**（`TEMU_BROWSER_CHANNEL=chrome`）
```powershell
py login.py --tenant-id 1
```

- 登录态保存在 `backend/python/.temu-browser-profile/tenant-{id}`（勿删）
- 登录后需在后台 **选好店铺**，终端里应能看到 `agentseller-mall-info-id`

### 爬取入库

```powershell
py crawl.py --tenant-id 1
# 或
powershell -File scripts/crawl-tenant.ps1 -TenantId 1 -Seed
```

| 参数 | 说明 |
|------|------|
| `--tenant-id` | **必填**（或环境变量 `TENANT_ID`） |
| `--date 2026-06-25` | 指定上报日期 |
| `--seed` | 不打开浏览器，用 demo 种子数据 |
| `--json` | 成功时 stdout 输出单行 JSON（Java 调用时使用） |

### 反检测要点（Temu 易识别自动化）

| 措施 | 说明 |
|------|------|
| 持久化 Profile | 复用真实登录 Cookie，避免每次新环境 |
| 有头 + 本机 Chrome | `TEMU_HEADLESS=0`，优先 `channel=chrome` |
| 去 webdriver 特征 | `--disable-blink-features=AutomationControlled` + init script |
| 浏览器内发 API | `page.request.post`，不用裸 httpx |
| 随机间隔 | 默认 0.8–2.2s  между请求 |

爬取逻辑对齐 Commander Agent：  
`agentseller.temu.com/mms/venom/api/supplier/sales/management/listOverall`

---

## 2. Java API

包结构见 [`backend/java/PACKAGES.md`](java/PACKAGES.md)（`controller` / `service`+`impl` / `dto` / `mapper`）。

```powershell
. ..\..\scripts\env-java.ps1
mvn -f backend/java/pom.xml spring-boot:run
```

或：`powershell -File scripts\run-java-api.ps1`

### 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册企业并创建租户 |
| POST | `/api/auth/login` | 登录，返回 JWT（含 `tid` / `warehouse_scope`） |
| GET | `/api/auth/session` | 当前会话（续期校验） |
| GET | `/api/platform-accounts` | 租户内店铺绑定（JWT） |
| GET | `/api/temu/shops` | 店铺列表 |
| GET | `/api/temu/operational?shop_id=` | 商品 + 四类预警 |
| GET | `/api/temu/trend?days=7` | 销量趋势 |
| POST | `/api/temu/crawl` | 触发异步爬取（JWT；可选 `seed` / `report_time`） |
| GET | `/api/temu/crawl/{jobId}` | 爬取任务状态 |
| GET | `/api/warehouse/orders` | 出库单列表 + 统计 |
| GET | `/api/warehouse/orders/{id}` | 出库单详情 |
| POST | `/api/warehouse/orders` | 新建出库单（管理员 / 员工） |
| POST | `/api/warehouse/orders/{id}/review` | 仓库审批（可发 / 暂不可发） |
| POST | `/api/warehouse/orders/{id}/release` | 暂不可发 → 确认可发 |
| POST | `/api/warehouse/orders/{id}/ship` | 标记已发货 |
| POST | `/api/warehouse/orders/{id}/cancel` | 取消订单 |
| DELETE | `/api/warehouse/orders/{id}` | 删除订单（仅企业管理员） |
| GET | `/api/warehouse/sites` | 分仓列表（`?activeOnly=true` 仅启用） |
| POST | `/api/warehouse/sites` | 新增分仓（仅企业管理员） |
| PUT | `/api/warehouse/sites/{id}` | 更新分仓 |
| PATCH | `/api/warehouse/sites/{id}/status` | 启用 / 停用分仓 |
| DELETE | `/api/warehouse/sites/{id}` | 删除分仓（无关联订单时） |
| GET | `/api/warehouse/members` | 仓库人员列表（**仅企业管理员**） |
| POST | `/api/warehouse/members` | 新增仓库人员 + 分仓权限 |
| PUT | `/api/warehouse/members/{id}` | 更新仓库人员 |
| PATCH | `/api/warehouse/members/{id}/status` | 启用 / 停用 |
| DELETE | `/api/warehouse/members/{id}` | 删除仓库人员 |
| GET/POST/PUT | `/api/tenant/members` | 运营人员 CRUD（**运营绑定**） |

数据表（启动时 `TenantSchemaMigration` 自动迁移 + 种子）：

| 表 | 说明 |
|----|------|
| `warehouse_order` | 出库单（含 `warehouse_id` / `warehouse_name`） |
| `warehouse_site` | 分仓主数据 |
| `user_warehouse_scope` | 仓管 ↔ 分仓 |
| `user_platform_scope` | 运营 ↔ 平台（独立站用 `dtc`） |
| `user_menu_grant` | 运营扩展权限（如 `employee.warehouse` 仓库下单） |
| `app_user` | 全角色账号（`role=admin/user/warehouse`） |

Demo 分仓：**泰州1号仓**、**泰州邮政仓**、**安徽仓库**。

### 演示账号（`app_user`，爬虫初始化时写入）

| 角色 | 账号 | 密码 | 说明 |
|------|------|------|------|
| Boss | `admin@crosshub.cn` | `12345678` | 企业管理员 |
| 员工 | `wangyiming@yituo-outdoor.com` | `Emp@Demo123` | |
| 员工 | `liting@yituo-outdoor.com` | `Emp@Demo456` | Temu 运营 |
| 员工 | `liuyang@yituo-outdoor.com` | `Emp@Demo987` | 独立站（`dtc`） |
| 仓库 | `warehouse@yituo-outdoor.com` | `Wh@Demo123` | 张仓管 · 仓库管理员（泰州1号仓 + 邮政仓） |
| 仓库 | `picker@yituo-outdoor.com` | `Wh@Demo456` | 李拣货 · 仓库管理员（安徽仓库） |

### 仓库端口菜单（`sys_menu` portal=warehouse）

| 菜单 | 路径 |
|------|------|
| 待审核 | `/warehouse/pending-review` |
| 待发货 | `/warehouse/pending-shipment` |
| 已发货 | `/warehouse/shipped` |
| 任务中心 | `/warehouse/tasks` |

> 仓库端口**无**「设置 / 员工绑定」菜单；人员与分仓均在 Boss **设置 → 仓库人员 / 仓库设置** 维护。登录响应含 `warehouse_scope_names`，前端 `WarehouseScopePanel` 展示负责分仓。

> **任务分配**（Boss → 运营/仓管）当前为前端 Demo（`assignedTasksLocal` + `opsFeedbackLocal`），与 Java 出库单 API 独立；员工/仓管反馈通过 `syncAssignedTaskFeedback` 在 localStorage 内串联。

### 企业管理员设置菜单（`sys_menu` portal=boss，节选）

| 菜单 | 路径 |
|------|------|
| 运营总览 | `/boss/dashboard` |
| 任务分配 | `/boss/tasks` |
| 运营绑定 | `/boss/employees` |
| 仓库设置 | `/boss/warehouse-sites` |
| 仓库人员 | `/boss/warehouse-staff` |
| 账户绑定 | `/boss/accounts` |

### 员工端仓库权限

管理员在 **运营绑定** 中开启 **仓库下单**（写入 `user_menu_grant` → `employee.warehouse`），员工侧栏才会出现 **仓库下单**。

### 仓管分仓权限

- 登录 JWT 携带 `warehouse_scope`（来自 `user_warehouse_scope`）
- 出库单列表 / 审批 / 发货仅作用于已分配分仓
- 新建出库单时运营须指定 `warehouseId`（目标分仓）

### 独立站平台键

- 运营绑定平台 scope 使用 **`dtc`**（独立站）
- 账户绑定店铺仍为 `shopify` / `wordpress`；`MenuService` 与 `MemberScopeService` 将 `dtc` 与二者互通

---

## 3. 前端

```powershell
cd dev/vue-site
npm run dev
```

Boss 登录后进入 **Temu 运营**，应显示「后端实时数据」；点击 **刷新数据** 将触发 Java → Python 异步爬取（详见 `docs/temu-crawl/`）。  
启动 Java API 后，**仓库下单** 三端登录将写入 SQLite（`warehouse_order`）；未启动时仍走浏览器 localStorage Demo。

**Demo 默认**：`dev/vue-site/.env` 中 `VITE_USE_TEMU_BACKEND=false`（纯 localStorage）。联调 Java 时改为 `true` 并确保 API 已启动。
