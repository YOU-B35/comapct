# 机器码租户助手（一台电脑一绑）Design Spec

> 日期：2026-08-11  
> 状态：**待实现**  
> 上级：`2026-08-11-user-local-helper-temu-sync-design.md`、`2026-08-11-amazon-aliexpress-user-local-helper-design.md`  
> 拍板：同公司（同租户）换号共用一台助手；登录态按店铺隔离；安装探测 = 进程 → 安装痕迹 → 再引导下载绑定

### 拍板记录

| # | 决策 |
|---|------|
| 1 | 绑定身份改为 **`(tenant_id, machine_fingerprint)`**，一台电脑 × 一家公司 = 一条助手 |
| 2 | 同公司老板/员工换号 **无需重新绑定**；跨租户仍需换绑（本期不做跨公司共用） |
| 3 | Temu / AliExpress 浏览器 profile 按 **店铺 / `session_key`** 隔离，不按 CrossHub `user_id` |
| 4 | 同公司能进平台模块的人 **都能点** 同步 / 打开登录（共用机器助手执行） |
| 5 | 网站离线引导：进程探测 → 安装痕迹 → 才确认下载+绑定；网页不直接扫磁盘 |

---

## 0. 一句话结论

把 Sync Helper 从「一用户一绑」改为「一机器一租户一绑」：Java 用机器码登记助手；同租户任意成员看到同一在线态；店铺登录态按卖家账号目录共用；状态条在不确定时先确认本机是否已装/可启动，避免误导反复下载。

---

## 1. 背景与问题

现状：

- 绑定 upsert 键为 `(bound_user_id, machine_fingerprint)`。
- `GET /api/agent/me/status` 只统计 **当前用户** 的 agent。
- 本机 `config.json` 只有一个 `agent_token`，故换 CrossHub 账号后显示离线，必须清除绑定再绑。
- `machine_fingerprint` 已存在，但只用于去重同一用户的多台机，**不参与**在线判定与任务路由。
- Profile 目录含 `user-{bound_user_id}`，强化了「一人一份登录」。

用户目标：同公司多人共用一台电脑时，**真正一台电脑绑一次**；登录态跟店铺走；没装才引导下载。

---

## 2. 目标与非目标

### 2.1 目标

1. **机器码租户助手**：唯一键 `(tenant_id, machine_fingerprint)`；本机一份 token。  
2. **同租户在线共享**：任意成员心跳期内看到 `online=true`，任务派到该机器助手。  
3. **店铺级 profile**：`tenant-{tid}/account-{session_key}`，去掉 CrossHub user 层。  
4. **状态条分级引导**：在线 → 进程在跑需绑当前公司 → 已装请启动 → 下载+绑定。  
5. **文案**：弱化「当前账号未绑定」，强调「本机未绑定/未启动助手」。

### 2.2 非目标

| 不做 | 说明 |
|------|------|
| 跨租户共用一台助手 token | 换公司仍换绑 |
| 浏览器直接枚举桌面/下载目录 | 沙箱不允许；用安装痕迹 + 端口 |
| 多 Helper 进程并行绑同一 `(tenant, fingerprint)` | 仍单进程单 token |
| 改变平台店铺菜单授权模型 | 「都能点」指模块内操作走机器助手，不另开超管后门 |
| 本期强制全量生产部署 | 实现与验收以本地/约定环境为准，上线另批 |

---

## 3. 架构

### 3.1 绑定身份

```text
Website (JWT user ∈ tenant T)
  → POST /api/agent/me/bind-code
  → Helper POST /api/agent/bind { code, machine_fingerprint }
  → Java upsert integration_agent WHERE tenant_id=T AND machine_fingerprint=F
  → agent_token → config.json（单份）
```

- `bound_user_id`：可选，记「最近一次绑定操作人」，**不参与**在线路由。  
- 同 `(T, F)` 再次绑定：同一 `agent.id`，轮换 `agent_token`（与现行为一致）。  
- 清除绑定：仍允许；同公司换号 **默认不需要** 清除。

### 3.2 在线与任务路由

| 能力 | 行为 |
|------|------|
| `GET /api/agent/me/status` | 查当前用户 `tenant_id` 下心跳有效（≤90s）的机器助手；`recommended_agent_id` = 最新心跳那条 |
| Temu / AE / Amazon 手动任务 | `agent_id` = 该租户在线机器助手；无则 fail-closed（错误码可沿用 `*_USER_HELPER_OFFLINE`，文案改为机器向） |
| Agent poll/claim | 保持租户范围；任务带明确 `agent_id` 时仅该助手领取 |
| 日批 / `triggeredBy≤0` | `agent_id` 为空时：仅允许 **本租户内有心跳的机器助手** 领取；若同租户误留多条历史 agent，迁移后只应剩一条 canonical，避免双助手抢任务 |

**权限**：同租户、已能进入对应平台模块的用户均可触发同步/登录；执行落在机器助手；店铺数据可见性仍受现有店铺授权约束（若某用户本来看不到某店，不因机器助手而扩大读权限）。「都能点」= 不因「未绑到自己的 user agent」而拦截操作。

### 3.3 Profile（店铺隔离）

```text
{TEMU|AE}_PROFILE_ROOT / tenant-{tenant_id} / account-{session_key}/…
```

- 绑定/启动时 **不再** 强制 `user-{crosshubUserId}` 段。  
- 任务 payload 带 `session_key` / 卖家账号 → 选对应目录。  
- 迁移：若本机已有 `user-*/tenant-*/account-*`，**兼容读取旧路径**；**新写入只用** `tenant-{tid}/account-{session_key}`。不在本期做自动搬迁目录（避免误删）；用户若见「需重新登录某店」，属可接受一次性成本。

Amazon（Ziniao 等）保持现有本机会话模型，不另造 user 目录。

### 3.4 网站安装/绑定引导

优先级（状态条）：

1. **Java 机器助手在线** → 在线可用。  
2. **Java 离线 + 本机端口通**（`:18765` / `:18766`）→ 「助手已运行，但未服务当前公司」→ 生成绑定码（典型：换租户或从未绑过本租户）。  
3. **端口不通 + 本机有安装痕迹** → 「已安装，请启动 Sync Helper」；不主推下载。  
4. **都无** → 确认下载安装 + 生成绑定码。

**安装痕迹（本机，非网页扫盘）**

- 安装包或首次成功启动时写入其一（实现选稳妥者）：  
  - 固定路径标记文件，例如 `%LOCALAPPDATA%\CrossHub\SyncHelper\installed.json`（含 version、安装时间）；和/或  
  - Windows 注册表 HKCU 项。  
- Helper 面板增加只读接口，例如 `GET /api/install-info`（CORS 同现有面板），供网站在端口通时读取。  
- 端口不通时：网站无法读标记文件 → UI 提供次要操作「我已安装，去启动」+ 刷新；可选后续：开机自启托盘常驻后几乎总有端口。  
- **禁止**依赖网页遍历「下载文件夹里的安装包」。

---

## 4. 数据与兼容

### 4.1 DB / 迁移

- `integration_agent`：保证可按 `(tenant_id, machine_fingerprint)` 唯一查找（迁移增加唯一索引或应用层 upsert；处理历史多行同指纹不同 `bound_user_id`：同租户合并保留最新心跳/一条 canonical）。  
- 历史「每用户一条」同机同租户多 agent：迁移策略 = **保留最近心跳一条为机器助手**，其余同指纹同租户标记废弃或解绑（token 失效），避免双心跳抢任务。

### 4.2 Helper config

- 继续存 `agent_token`、`tenant_id`、`machine_fingerprint`；`user_id` 仅审计。  
- Profile env：按 §3.3，不再把 `CROSSHUB_BOUND_USER_ID` 作为 profile 根段（若其它逻辑依赖该 env，改为任务上下文传入）。

### 4.3 API 兼容

- `POST /api/agent/bind` 请求体不变（仍要 fingerprint）。  
- `GET /api/agent/me/status` 响应形状尽量不变（`online`、`agents`、`recommended_agent_id`）；语义改为租户机器助手列表。  
- 公开 bind 仍无 JWT；消费码时绑定到 **码所属用户的 tenant_id**。

---

## 5. 前端

- `HelperStatusBar` / `TemuHelperStatusBar`：四级状态（online / rebind-tenant / installed-start / download-bind）。  
- 探测：`fetchLocalHelperBind` + `probeLocalAgent`；有面板时可读 `/api/install-info`。  
- 同租户已在线：不展示「必须生成绑定码」主按钮。  
- 错误文案：`TEMU_*` / `AE_*` / `AMAZON_*` HELPER_OFFLINE → 「请在本机启动并绑定 Sync Helper（一台电脑绑定一次即可）」。

---

## 6. 安全与风险

| 风险 | 缓解 |
|------|------|
| 同租户任意成员向该 PC 派任务 | 拍板接受；店铺读权限仍走授权 |
| 店铺 cookie 同机共用 | 拍板 C；不同 `session_key` 仍隔离 |
| 跨租户误用 token | agent 仍单 `tenant_id`；换公司需换绑 |
| 迁移合并多 user-agent | 只留一条 canonical，旧 token 失效并提示一次重绑（每机每租户至多一次） |
| 安装痕迹伪造 | 仅 UX 提示，真正执行仍依赖 Java 在线与 token |

---

## 7. 验收标准

1. 用户 A 在本机绑定成功 → 同租户用户 B 换号登录，**不换绑**即可看到助手在线并可触发同步（Helper 保持运行）。  
2. 用户 B 打开同一 Temu 店铺登录：与 A 共用该 `account-*` 目录会话（已登录则无需重登）。  
3. 不同店铺仍独立登录态。  
4. 停止 Helper 进程后：若有安装痕迹，文案为启动引导而非强制下载；无痕迹才下载+绑定。  
5. 换另一租户账号：显示需绑定当前公司；绑定后原租户任务不再被该 token 领取。  
6. 回归：单用户单机路径（首次下载→绑码→登录→同步）不回归失败。

---

## 8. 实现边界（给计划用）

| 层 | 主要改动点 |
|----|------------|
| Java | Bind upsert 键；presence by tenant+fingerprint；enqueue 用租户机器助手；迁移合并历史行 |
| Python Helper | profile 路径；install marker + `/api/install-info`；bind 文案 |
| Vue | 状态条四级；offline 文案；弱化 per-user rebind |
| 测试 | 同租户两用户 presence；profile 路径；迁移合并 |

**明确不做进本 spec 的后续项**：跨租户机器共用、网页扫盘、多 Helper 多 token 同机并行。
