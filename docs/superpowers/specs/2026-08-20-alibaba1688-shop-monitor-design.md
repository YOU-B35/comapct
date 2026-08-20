# 1688 竞店实时监控模块 设计文档

> 日期：2026-08-20  
> 状态：待用户审阅  
> 关联：通用竞店监控框架（Temu 竞店监控）、1688 登录会话与商品采集链路、`alibaba1688_peer_bestseller`

## 1. 背景与目标

### 现状

- 用户提供了三张 1688 商品分享卡片，已解析为三个店铺、三个指定商品（见第 3 节种子数据）。
- 1688 公开接口可稳定获取：商品标题/价格/SKU 区间/属性、累计销量（精确值或分桶文案）、店铺质量分（达标率/回头率/48h 揽收率/粉丝）、商品复购率、代发近 7/30 天分桶、代发热度。
- 公开接口**不提供**别家店铺的精确每日订单数据；日销量只能通过“累计销量差值”反推或分桶/评价率估算。
- 项目已有通用竞店监控框架（`monitor_target` / `monitor_schedule` / `monitor_job` / `monitor_snapshot` / `monitor_product_snapshot` / `monitor_signal` + Python worker + Java `/api/monitor/*` + Temu 适配器）。

### 目标（本迭代）

1. 以店铺为单位监控：自动发现店铺爆款榜 Top N，同时盯住用户指定的商品。
2. 每 1–2 小时自动轮询（可配置），支持页面手动立即刷新。
3. 五类业务告警（价格变动、销量异常、下架/恢复、新爆款上榜、缺货信号）+ 登录/风控系统告警。
4. 保留每次快照的原始接口响应（`raw_json`）与可导出的历史明细，为后续 AI 大模型专项分析提供数据地基（本期不实现 AI 分析）。

## 2. 范围

### 做

- 新增 1688 监控平台适配器（`MonitorPlatformAdapter` 实现）与店铺采集器。
- 新增排程入队器：消费 `monitor_schedule.next_run_at`，自动生成 `monitor_job`。
- 表结构扩展：`monitor_product_snapshot` 1688 专属字段、`monitor_target.config_json`、`monitor_signal` 类型扩展。
- Java：1688 店铺 URL 校验/规范化、`/api/monitor/targets/{id}/trend` 趋势接口、商品 DTO 1688 字段。
- 前端：1688 模块新增“竞店监控”Tab（店铺管理、爆款榜、趋势图、告警列表）。
- 报表：复用通用 worker 的 MD/XLSX 快照报表。

### 不做（本期）

- AI 大模型专项分析（仅预留数据）。
- 别家店铺的精确订单数据（公开接口不存在，只做累计销量差值估算）。
- 改动现有 `run_peer_bestsellers_sync` 同行爆款同步任务（两套功能并行，共享 1688 profile 但互不改动）。
- 多租户/权限模型重构（沿用现有 `DataScopeService` 租户与店铺范围）。

## 3. 初始种子数据（三家店铺）

| 店铺 | 店铺 URL | 指定盯梢商品（offerId） | 建议 Top N |
|------|----------|------------------------|-----------|
| 义乌市寻渔记科技有限公司 | `https://shop17682i6w5i484.1688.com` | 867473865842（FTK 欧式鲤钓绑钩） | 20 |
| 深圳市东博瑞户外用品有限公司 | `https://shop16yx1905b2433.1688.com` | 930671411701（欧鲤极尖锋 KRANK HOOK） | 20 |
| 慈溪市酷诺钓具有限公司 | `https://shop45996540o0794.1688.com` | 979632972917（跨境 Captive Backweight 压线铅） | 20 |

店铺 memberId 在采集时由店铺页接口动态解析（如东博瑞 `b2b-221111714406302508`），不硬编码。

## 4. 架构与组件

### 4.1 新增组件（Python）

| 文件 | 职责 |
|------|------|
| `backend/python/app/platforms/alibaba1688_shop_collector.py` | 1688 店铺采集器：解析店铺 URL、拉店铺商品列表、补全商品详情与店铺卡片 |
| `backend/python/app/platforms/alibaba1688_monitor_adapter.py` | `MonitorPlatformAdapter.crawl_target` 实现：调用采集器并计算日增量，输出通用监控产物 |
| `backend/python/app/monitor_schedule_enqueuer.py` | 排程入队器：扫描 `monitor_schedule` 到期项，插入 `monitor_job` 并推进 `next_run_at` |

### 4.2 复用组件

- `monitor_worker_service.py` / `monitor_db.py`：任务认领、快照/信号/报表落库、冷却记录。
- Java `MonitorService` / `MonitorController`：目标 CRUD、手动触发、历史/最新查询、报表下载。
- 1688 登录会话：`agent.alibaba1688_tasks._launch` + 租户持久化 profile（Playwright）。
- 前端 1688 模块（`Alibaba1688ModuleView.vue`）与现有 `/api/monitor/*` API。

## 5. 数据流

1. **入队**：排程入队器发现 `monitor_schedule.enabled=1 && next_run_at<=now`，或用户在页面点“立即刷新”（Java trigger），生成 `monitor_job(status=pending)`。
2. **执行**：monitor worker 认领任务，调 `Alibaba1688MonitorAdapter.crawl_target`。
3. **采集**（串行，同一 1688 profile）：
   a. 会话就绪检查（登录失效则失败 `MONITOR_AUTH_REQUIRED`）；
   b. 店铺页拉商品列表（`mtop.alisite.cbu.winport.sync.moduledata.get`，`sortType=tradenumdown`）取 Top N；
   c. 对 Top N + 指定盯梢商品逐项调详情接口（`mtop.1688.mmga.offerdetail.service`、店铺卡片、代发 adviseList），收集价格/SKU 区间/销量文案/累计成交/代发分桶/复购率/属性；
   d. 记录每个接口原始响应到 `raw_json`。
4. **计算**：`total_sales` = 本次累计销量；`daily_sales` = 本次 − 上一次快照累计（口径见第 10 节）。
5. **分析落库**：`analyze_products`（扩展）判定五类信号 → 写 `monitor_snapshot` / `monitor_product_snapshot` / `monitor_signal` → 更新 `monitor_target.latest_snapshot_*` → 生成 MD/XLSX 报表 → 记录 `monitor:{target_id}` 冷却。

## 6. 数据模型变更（V4x 迁移，向后兼容；实施时取当前最新迁移版本号 +1）

### 6.1 `monitor_product_snapshot` 新增列（可空）

| 列 | 类型 | 说明 |
|----|------|------|
| `shop_name` | TEXT | 店铺名 |
| `shop_url` | TEXT | 店铺地址 |
| `rank` | INTEGER | 本次店铺爆款榜位次（Top N 内有效） |
| `price_range` | TEXT | SKU 价格区间（如 `0.50-1.20`） |
| `sale_text` | TEXT | 平台销量文案（如 `已售10万+件`） |
| `dropship_7d` | TEXT | 代发近 7 天分桶（如 `100以内`） |
| `dropship_30d` | TEXT | 代发近 30 天分桶 |
| `dropship_heat` | INTEGER | 商家代发热度 |
| `rebuy_rate` | TEXT | 商品复购率 |
| `shop_return_rate` | TEXT | 店铺回头率 |
| `quality_rate` | TEXT | 品质达标率 |
| `shop_fans` | INTEGER | 店铺粉丝数 |
| `attrs_json` | TEXT | 品牌/材质/规格等属性 |
| `is_pinned` | INTEGER | 是否为用户指定盯梢商品（0/1） |
| `raw_json` | TEXT | 本次原始接口响应快照（AI 数据地基） |

### 6.2 `monitor_target.config_json`（新增列）

```json
{
  "top_n": 20,
  "pinned_offer_ids": ["867473865842"],
  "webhook_url": "",
  "interval_minutes": 120
}
```

排程主体继续使用 `monitor_schedule`（interval_minutes / retry_limit），`config_json` 只放 1688 专属配置。

### 6.3 `monitor_signal.signal_type` 扩展

| 类型 | 触发条件 | `signal_value` 示例 |
|------|----------|--------------------|
| `price_change` | 起价或 SKU 区间变化 | `{"old":"7.8","new":"6.5"}` |
| `sales_surge` | 日增量超过历史均值阈值（如 1.5 倍且 ≥ 20）或骤降 | `{"delta":120,"avg":40}` |
| `delist_or_relist` | 商品下架 / 恢复上架 | `{"status":"delisted"}` |
| `bestseller_new_entry` | 新商品进入 Top N（此前不在库） | `{"rank":5}` |
| `stock_warning` | 缺货/低库存信号（页面缺货标记） | `{"text":"缺货"}` |
| `auth_or_risk` | 登录失效 / 被风控（系统级） | `{"code":"A1688_NOT_LOGGED_IN"}` |

保留旧类型 `recent_launch` / `sales_outlier` 兼容。

## 7. Java API 变更

1. 新增 `Alibaba1688MonitorUrlValidator`：接受 `shop{id}.1688.com`（及商品详情链接，用于反查店铺），规范化到店铺 URL；`MonitorServiceImpl` 的 URL 校验按平台分发。
2. 新增 `GET /api/monitor/targets/{id}/trend?days=30&product_id=`：返回商品时间序列（`snapshot_at / price / total_sales / daily_sales / rank / sale_text`），供前端趋势图；`product_id` 可空，为空时返回该目标全部商品最近 `days` 天的序列。
3. 商品 DTO 增加 1688 字段（shop_name、price_range、sale_text、dropship_*、rebuy_rate、shop_return_rate、quality_rate、is_pinned、rank）。
4. 告警查询支持按 `signal_type` 过滤（沿用 `/latest` 扩展或新增 `/signals`）。

## 8. 前端

在 `Alibaba1688ModuleView.vue` 新增“竞店监控”Tab，四个区块：

1. **店铺管理**：添加/编辑监控店铺（填店铺 URL，或填商品链接由后端反查店铺）、Top N、盯梢 offerId、轮询间隔（60/120 分钟）、webhook 开关；“立即刷新”按钮。
2. **爆款榜表格**：排名、商品（缩略图+链接）、价格区间、累计销量、日增量、代发 7/30 天、复购率、回头率、在售状态、最近变化标识。
3. **趋势图**（ECharts）：单商品切换“累计销量 / 日增量 / 价格”曲线，默认 30 天。
4. **告警列表**：按店铺/类型过滤，未读红点。

新增 `dev/vue-site/src/api/alibaba1688MonitorApi.js`；CRUD/触发/历史复用 `/api/monitor/*`。

## 9. 调度与风控

- **频率**：每店 `interval_minutes` 可配置（默认 120，可设 60），排程入队器按 `next_run_at` 自主入队，不依赖手动触发。
- **抖动**：`next_run_at` 加 0–10 分钟随机偏移，避免多店整点齐发。
- **浏览器单飞**：1688 只有一个登录 profile；采集任务与现有 agent 1688 任务串行执行。monitor worker 与 agent 同驻 helper 进程时共用进程内锁；独立进程运行时沿用 profile 目录的 SingletonLock/锁清理机制避免并发占用。
- **验证码/风控**：检测 punish/captcha 页面 → `MONITOR_RISK_BLOCKED`，按 `retry_limit` 退避重试，延后 `next_run_at`；连续失败转 `auth_or_risk` 系统告警。
- **登录失效**：`MONITOR_AUTH_REQUIRED`，提示通过现有登录窗口重新登录。
- **失败隔离**：单店失败不影响其他店；单商品失败只跳过该商品，成功部分落库（任务 warning）。
- **冷却**：手动触发沿用现有 monitor scope 冷却；排程按 `next_run_at` 控制频率。

## 10. 数据质量与日增量口径

1. **累计销量取值优先级**：详情页精确“成交 X 件” > `saleAmount` 精确值 > 分桶文案下限（`10万+件` 记为 100000）。
2. **日增量**：`daily_sales = 本次累计 − 上次快照累计`；首次快照为 baseline（daily_sales=0，`is_pinned` 等字段照常）。
3. **异常检测**：增量为负、跳变超阈值（如 >5 倍且 >1000）或商品改链接/重上架时，标记可疑，不计入趋势，保留 `raw_json` 供人工/AI 复核。
4. **代发分桶**：仅作量级参考（存 `dropship_7d/30d`），不并入 `daily_sales`。
5. **时区**：统一 Asia/Shanghai，快照时间 `YYYY-MM-DD HH:mm:ss`。

## 11. AI 分析预留

- 每次快照完整保存 `raw_json`（按商品），历史可回溯。
- `monitor_snapshot` / `monitor_product_snapshot` 提供 JSON + XLSX 导出（报表目录已含 MD/XLSX）。
- 后续 AI 专项分析直接消费“按 target/product 对齐的时间序列 + 原始字段”即可，无需重新抓取。
- 本期不实现模型调用、prompt 编排与结论落库。

## 12. 测试策略

| 层级 | 覆盖 |
|------|------|
| 单元（Python） | 店铺 URL 解析、接口响应解析（用已抓取的真实响应做 fixtures）、日增量与异常检测、五类信号判定、排程入队器（假时钟）、webhook 负载 |
| 单元（Java） | `Alibaba1688MonitorUrlValidator`、`MonitorServiceImpl` trend/信号查询 |
| 集成冒烟 | 对三家真实店铺跑一次适配器，验证快照/信号/报表/趋势 API 落库 |
| 异常用例 | captcha 响应、登录失效、空商品列表、单商品失败、部分成功 |
| 前端 | 手动 smoke：建店、立即刷新、趋势图、告警已读 |

## 13. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 1688 反爬（captcha/限频） | 串行采集、随机抖动、退避重试、失败隔离 |
| 接口字段变动 | 响应解析集中在一个模块，fixtures 回归；`raw_json` 留存便于排查 |
| 累计销量分桶显示（如 10 万+） | 优先精确字段；分桶按下限兜底并标注口径 |
| 商品下架/改链接 | `delist_or_relist` 信号 + 异常增量标记 |
| 浏览器 profile 并发冲突 | 进程内锁串行；与 agent 1688 任务共用锁 |
| 高轮询频率触发风控 | 频率可配置、抖动、冷却；默认 120 分钟 |

## 14. 验收标准

1. 三个店铺可创建监控目标并“立即刷新”成功，爆款榜 Top N + 三个盯梢商品全部落库。
2. 自动排程按配置（60/120 分钟）入队并执行，快照历史连续。
3. 五类业务信号 + 登录/风控系统信号可产生、可查询、可 webhook。
4. 趋势接口返回时间序列，前端图表与表格数据一致。
5. 单店/单商品失败不影响其他目标；报表 MD/XLSX 正常生成。
6. 每商品 `raw_json` 落库，可导出供后续 AI 分析。

## 15. 实施阶段（概要，供 writing-plans 细化）

1. Python：采集器 + 适配器 + 排程入队器。
2. 表迁移 + Java（validator / trend API / DTO）。
3. 前端“竞店监控”Tab。
4. 测试与三家真实店铺冒烟。
