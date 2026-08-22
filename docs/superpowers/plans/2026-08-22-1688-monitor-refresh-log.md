# 竞店监控刷新日志 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增后端任务列表接口并在竞店监控面板「爆款榜」卡片内展示刷新记录（时间节点、状态、耗时、失败原因）。

**Architecture:** 后端 `MonitorService` 新增 `listRecentJobs` 查询 `monitor_job` 表并按发起时间倒序返回；`MonitorController` 暴露 `GET /api/monitor/jobs`；前端面板加载并展示最近 20 条。上线时连同 Java 时区改动一起部署并执行 UTC+8 数据库迁移。

**Tech Stack:** Spring Boot（JdbcTemplate）、Vue 3 + Element Plus、SQLite、SSH/SFTP 部署脚本。

## Global Constraints

- 只新增 1 个后端接口，复用 `monitor_job` 表，不新增表；
- `target_id` 必填；`limit` 默认 20、上限 100；
- 返回字段沿用 `toJobDto`：`job_id / target_id / status / trigger_type / queued_at / started_at / finished_at / error_code / error_message / reason`；
- 前端日志表格只展示最近 20 条，不做分页/筛选/导出；
- 前端放置位置：竞店监控「爆款榜」卡片内部、商品表格下方；
- 部署：`deploy-server.ps1`（`CROSSHUB_SSH_HOST=124.223.27.98` + `CROSSHUB_SSH_KEY`），随后执行 `migrate_db_utc_to_shanghai.py`（先备份→dry-run→apply）。

---

### Task 1: 后端任务列表（接口 + 实现 + 路由）

**Files:**
- Modify: `backend/java/src/main/java/com/crosshub/monitor/service/MonitorService.java`
- Modify: `backend/java/src/main/java/com/crosshub/monitor/service/impl/MonitorServiceImpl.java`
- Modify: `backend/java/src/main/java/com/crosshub/monitor/controller/MonitorController.java`

**Interfaces:**
- Produces: `List<Map<String, Object>> listRecentJobs(String targetId, int limit)`；`GET /api/monitor/jobs?target_id=xx&limit=20`。

- [ ] **Step 1: 接口新增方法**

`MonitorService.java` 在 `getJob` 声明后新增：

```java
List<Map<String, Object>> listRecentJobs(String targetId, int limit);
```

- [ ] **Step 2: 实现 `listRecentJobs`**

`MonitorServiceImpl.java` 在 `getJob(...)` 方法后新增：

```java
@Override
public List<Map<String, Object>> listRecentJobs(String targetId, int limit) {
    Long tenantId = dataScopeService.requireTenantId();
    requireTargetRow(targetId, tenantId);
    reconcileStaleJobs(tenantId, targetId);
    return jdbc.query(
            """
            SELECT * FROM monitor_job
            WHERE tenant_id = ? AND target_id = ?
            ORDER BY queued_at DESC
            LIMIT ?
            """,
            (rs, rn) -> toJobDto(rsToMap(rs)),
            tenantId, targetId, Math.min(Math.max(limit, 1), 100)
    );
}
```

- [ ] **Step 3: Controller 新增路由**

`MonitorController.java` 在 `@GetMapping("/jobs/{jobId}")` 前新增：

```java
@GetMapping("/jobs")
public Map<String, Object> jobs(
        @RequestParam("target_id") String targetId,
        @RequestParam(defaultValue = "20") int limit
) {
    return ApiResult.ok(Map.of("jobs", monitorService.listRecentJobs(targetId, limit)));
}
```

- [ ] **Step 4: 验证**

运行：`. .\scripts\env-java.ps1 | Out-Null; Set-Location backend\java; mvn test -DskipITs`
预期：`BUILD SUCCESS`，`Tests run: 126, Failures: 0, Errors: 0`。

- [ ] **Step 5: Commit**

```bash
git add backend/java/src/main/java/com/crosshub/monitor/service/MonitorService.java backend/java/src/main/java/com/crosshub/monitor/service/impl/MonitorServiceImpl.java backend/java/src/main/java/com/crosshub/monitor/controller/MonitorController.java
git commit -m "feat(monitor): add recent monitor job list API"
```

---

### Task 2: 前端 API 与面板刷新记录

**Files:**
- Modify: `dev/vue-site/src/api/alibaba1688MonitorApi.js`
- Modify: `dev/vue-site/src/components/alibaba1688/Alibaba1688MonitorPanel.vue`

**Interfaces:**
- Consumes: `GET /api/monitor/jobs`（Task 1）
- Produces: `fetch1688MonitorJobs(targetId, limit)`；面板「刷新记录」表格。

- [ ] **Step 1: 新增 API 函数**

`alibaba1688MonitorApi.js` 末尾新增：

```js
export async function fetch1688MonitorJobs(targetId, limit = 20) {
  const res = await service.get('/api/monitor/jobs', {
    params: { target_id: targetId, limit },
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res
}
```

- [ ] **Step 2: 面板脚本新增状态与加载逻辑**

`Alibaba1688MonitorPanel.vue`：

1. import 增加 `fetch1688MonitorJobs` 与 `toUtc8Date`：

```js
import { formatUtc8, toUtc8Date } from '@/utils/time'
```

```js
  fetch1688MonitorJobs,
```

2. 在 `const loading = ref(false)` 后新增：

```js
const jobs = ref([])
const loadingJobs = ref(false)
```

3. 新增函数（放在 `loadLatest` 之后）：

```js
async function loadJobs() {
  if (!selectedTargetId.value) return
  loadingJobs.value = true
  try {
    const data = await fetch1688MonitorJobs(selectedTargetId.value, 20)
    jobs.value = Array.isArray(data?.jobs) ? data.jobs : []
  } catch (e) {
    jobs.value = []
  } finally {
    loadingJobs.value = false
  }
}

function formatJobDuration(row) {
  const start = toUtc8Date(row?.queued_at)
  const end = toUtc8Date(row?.finished_at)
  if (!start || !end) return '—'
  const sec = Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000))
  if (sec < 60) return `${sec} 秒`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return s ? `${m} 分 ${s} 秒` : `${m} 分钟`
}
```

4. `loadLatest()` 中 `signals.value = await fetch1688MonitorSignals(...)` 之后新增 `await loadJobs()`。

5. `trigger()` 中：`failed` 分支与超时 `warning` 分支末尾、`catch` 块内各新增 `await loadJobs()`（成功分支已由 `loadLatest()` 覆盖）。

- [ ] **Step 3: 面板模板新增「刷新记录」表格**

在「爆款榜」`el-card` 内、商品表格 `</el-table>` 之后、`</el-card>` 之前新增：

```html
<div style="margin-top: 12px">
  <div style="font-weight: 600; margin-bottom: 8px">刷新记录</div>
  <el-table :data="jobs" v-loading="loadingJobs" size="small" max-height="260" empty-text="暂无刷新记录">
    <el-table-column label="发起时间" width="150">
      <template #default="{ row }">{{ formatUtc8(row.queued_at) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="80">
      <template #default="{ row }">
        <el-tag v-if="row.status === 'success'" type="success" size="small">成功</el-tag>
        <el-tag v-else-if="row.status === 'failed'" type="danger" size="small">失败</el-tag>
        <el-tag v-else type="warning" size="small">进行中</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="开始时间" width="150">
      <template #default="{ row }">{{ row.started_at ? formatUtc8(row.started_at) : '—' }}</template>
    </el-table-column>
    <el-table-column label="结束时间" width="150">
      <template #default="{ row }">{{ row.finished_at ? formatUtc8(row.finished_at) : '—' }}</template>
    </el-table-column>
    <el-table-column label="耗时" width="90">
      <template #default="{ row }">{{ formatJobDuration(row) }}</template>
    </el-table-column>
    <el-table-column label="触发方式" width="90">
      <template #default="{ row }">{{ row.trigger_type === 'manual' ? '手动' : row.trigger_type === 'scheduled' ? '定时' : (row.trigger_type || '—') }}</template>
    </el-table-column>
    <el-table-column label="失败原因" min-width="160" show-overflow-tooltip>
      <template #default="{ row }">{{ row.error_message || '—' }}</template>
    </el-table-column>
  </el-table>
</div>
```

- [ ] **Step 4: 验证构建**

运行：`Set-Location dev\vue-site; npm run build`
预期：`✓ built`，退出码 0。

- [ ] **Step 5: Commit**

```bash
git add dev/vue-site/src/api/alibaba1688MonitorApi.js dev/vue-site/src/components/alibaba1688/Alibaba1688MonitorPanel.vue
git commit -m "feat(1688): show monitor refresh log in competitor monitor panel"
```

---

### Task 3: 构建并上线（含 UTC+8 迁移）

**Files:** 无代码改动。

- [ ] **Step 1: 构建并部署后端 + 前端**

```powershell
$env:CROSSHUB_SSH_HOST = '124.223.27.98'
$env:CROSSHUB_SSH_KEY = 'C:\Users\Administrator\.ssh\lhkp-o3wazsuv'
powershell -File scripts\deploy-server.ps1
```

预期：本地 `mvn package` + `npm run build` 成功，远端 `docker compose up -d --force-recreate` 完成（期间有已知 502 空窗），nginx 重载。

- [ ] **Step 2: 上传迁移脚本并执行（先备份 → dry-run → apply）**

将 `scripts/migrate_db_utc_to_shanghai.py` 上传到 `/data/crosshub/scripts/`，然后：

```bash
python3 /data/crosshub/scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db --dry-run
python3 /data/crosshub/scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db --backup-dir /data/crosshub/backups
```

预期：dry-run 输出各表影响行数；apply 前生成 `.bak-*` 备份。

- [ ] **Step 3: 线上验证**

```bash
curl 'https://www.yoto.work/api/monitor/jobs?target_id=mt_fb2a75ab45164bff8a8d03f537641d87&limit=5'
```
预期：返回 `jobs` 数组，含 queued_at/status/trigger_type/error_message 等字段。

`SELECT last_heartbeat_at FROM integration_agent ORDER BY last_heartbeat_at DESC LIMIT 1` 应与当前北京时间接近（±1 分钟）。

- [ ] **Step 4: 回滚预案（如需）**

- 还原 `/data/crosshub/app.jar` 后 `docker compose up -d --force-recreate crosshub-java`；
- 用 `/data/crosshub/backups` 的 `.bak-*` 覆盖 `crosshub.db` 并重启容器；
- 前端回滚：还原 `/opt/1panel/www/sites/www.yoto.work/index/crosshub` 上一版。
