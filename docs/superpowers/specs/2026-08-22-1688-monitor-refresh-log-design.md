# 竞店监控刷新日志 设计

- 日期：2026-08-22
- 状态：已确认（方案 A：服务端任务日志；刷新记录面板放在「爆款榜」卡片内部、商品表格下方）
- 范围：后端 `backend/java`（新增 1 个查询接口）+ 前端 `dev/vue-site`（竞店监控面板）

## 1. 背景与目标

竞店监控目前只有手动点击「立即刷新」后的一次性成功/失败提示，没有历史记录；定时抓取（默认 120 分钟）的更新也无处查看。目标：在竞店监控面板内清晰展示每次刷新（手动+定时）的时间节点、状态、耗时和失败原因。

## 2. 后端

### 2.1 新增列表接口

`GET /api/monitor/jobs`

参数：
- `target_id`：监控店铺目标 ID（必填）；
- `limit`：返回条数，默认 20，上限 100。

返回：`ApiResult.ok({ jobs: [...] })`，按 `queued_at` 倒序。

Job 字段（复用现有 `monitor_job` 表与 `toJobDto` 结构）：

| 字段 | 说明 |
| --- | --- |
| `job_id` | 任务 ID |
| `target_id` | 目标 ID |
| `status` | `queued / pending / running / success / failed / retry_wait` |
| `trigger_type` | `manual`（手动）/ `schedule`（定时）等 |
| `queued_at` | 发起时间 |
| `started_at` | 开始时间 |
| `finished_at` | 结束时间 |
| `error_code` / `error_message` | 失败时的错误信息 |
| `reason` | 触发原因 |

### 2.2 实现位置

- `MonitorServiceImpl` 新增 `listRecentJobs(String targetId, int limit)`：`JdbcTemplate` 查询 `monitor_job`（`WHERE target_id = ? ORDER BY queued_at DESC LIMIT ?`）；
- `MonitorController` 新增 `GET /jobs` 路由。

手动「立即刷新」（现有 trigger 已带 `reason=manual refresh`）与定时抓取都会写入 `monitor_job`，无需新增表。

## 3. 前端

### 3.1 API

`dev/vue-site/src/api/alibaba1688MonitorApi.js` 新增：

```js
export async function fetch1688MonitorJobs(targetId, limit = 20) {
  const res = await service.get('/api/monitor/jobs', {
    params: { target_id: targetId, limit },
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res
}
```

### 3.2 面板（Alibaba1688MonitorPanel.vue）

- 新增状态：`jobs = ref([])`、`loadingJobs = ref(false)`；
- `loadLatest()` 中同步加载 `jobs`（切换店铺后刷新记录随之更新）；
- `trigger()` 轮询结束（成功/失败/超时）后重新加载 `jobs`，用户能立刻看到最新一次结果；
- 在「爆款榜」卡片内、商品 `el-table` 之后新增「刷新记录」区块：

| 列 | 字段 | 展示 |
| --- | --- | --- |
| 发起时间 | `queued_at` | `formatUtc8(...)` |
| 状态 | `status` | success→成功(success tag)；failed→失败(danger tag)；其余（queued/pending/running/retry_wait）→进行中(warning tag) |
| 开始时间 | `started_at` | `formatUtc8(...)`；空则 `—` |
| 结束时间 | `finished_at` | `formatUtc8(...)`；空则 `—` |
| 耗时 | 计算值 | `finished_at - queued_at`，秒/分钟展示；未完成显示 `—` |
| 触发方式 | `trigger_type` | `manual`→手动；`schedule`→定时；其他原样 |
| 失败原因 | `error_message` | 失败时显示，`show-overflow-tooltip` |

- 表格 `size="small"`、`max-height` 约 260px、空数据提示「暂无刷新记录」；
- 展示最近 20 条，不做分页/筛选/导出。

## 4. 明确不做的事

- 不新增独立日志表（复用 `monitor_job`）；
- 不做分页、筛选、导出；
- 不动「告警信号」卡片；
- 不改变现有刷新/轮询逻辑（仅结束后刷新日志列表）。

## 5. 上线与验证

- 后端：`mvn test` 通过；前端：`npm run build` 通过；
- 部署新 jar + 新前端（`docker compose up -d --force-recreate`，已知约 1–4 分钟 502 空窗）；
- 数据库：先备份 → dry-run → 执行 `migrate_db_utc_to_shanghai.py` UTC+8 迁移 → 抽查 `last_heartbeat_at` 与任务时间；
- 接口验证：`curl 'https://www.yoto.work/api/monitor/jobs?target_id=xx&limit=5'` 返回任务列表；
- 页面验证：点「立即刷新」，刷新记录区出现新记录且状态正确；
- 回滚：保留旧 jar 与 DB 备份。
