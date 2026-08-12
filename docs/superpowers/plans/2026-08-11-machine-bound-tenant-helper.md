# Machine-Bound Tenant Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Sync Helper bind once per PC per company (`tenant_id` + `machine_fingerprint`) so same-tenant account switches stay online without rebinding, with shop-scoped browser profiles and install-aware status UX.

**Architecture:** Change Java agent upsert/presence from user-bound to tenant+fingerprint. Route Temu/AE/Amazon manual jobs to the tenant’s online machine agent. Stop nesting Playwright profiles under `user-{id}`; keep `tenant-{tid}/account-{session_key}` (legacy `user-*/…` readable). Website status bar: Java online → local process needs company bind → installed-but-stopped → download+bind.

**Tech Stack:** Spring Boot + SQLite migrations, Vue3 + Element Plus, Python Sync Helper (tray `:18766`, health `:18765`).

**Spec:** `docs/superpowers/specs/2026-08-11-machine-bound-tenant-helper-design.md`

## Global Constraints

- Same tenant only: one bind per `(tenant_id, machine_fingerprint)`; cross-tenant still requires rebind.
- Shop/session isolation: Temu/AE profiles under `tenant-{tid}/account-{session_key}` — no CrossHub `user-{id}` segment on new writes.
- Same-tenant users who can open the platform module can trigger sync/login (do not block on “my user agent”).
- Browser must not scan Downloads/Desktop; install detection = ports + install marker file/API.
- Helper `java_api_url` defaults to `https://www.yoto.work` (no silent localhost).
- Chinese user-facing copy; offline messages emphasize PC bind once, not “current account unbound”.
- After Java changes: `powershell -File scripts\restart-java-api.ps1` before claiming done.
- No production deploy unless the user explicitly asks.

## File map

| Area | Files |
|------|--------|
| DB | Create `V26MachineBoundAgentMigration.java`; wire `@Order(26)` |
| Repo | `IntegrationAgentRepository.java` |
| Bind / status | `AgentBindCodeService.java`, `AgentMeController.java` |
| Presence / routing | `AgentPresenceService.java`, `TemuAgentService.java`, `TemuDailySyncService.java`, `TemuCrawlRetryService.java`, `AliExpressAgentService.java`, `AmazonSyncServiceImpl.java`, `AmazonWriteServiceImpl.java` |
| Errors | `AppErrorCode.java`, `dev/vue-site/src/utils/appErrorCode.js` |
| Helper profile | `backend/python/app/config.py`, `backend/python/app/session_scope.py`, `backend/python/agent/bind.py` |
| Install marker | new `backend/python/agent/install_marker.py`, `tray_app.py`, optionally `sync_helper_app.py` |
| Vue | `agentProbe.js`, `HelperStatusBar.vue`, `TemuHelperStatusBar.vue` |
| Tests | `AgentBindCodeServiceTest.java`, new presence/bind tests, Python profile/install tests |

---

### Task 1: DB + repository for `(tenant_id, machine_fingerprint)`

**Files:**
- Create: `backend/java/src/main/java/com/crosshub/config/migration/V26MachineBoundAgentMigration.java`
- Modify: `backend/java/src/main/java/com/crosshub/agent/repository/IntegrationAgentRepository.java`
- Modify: `backend/java/src/main/java/com/crosshub/config/migration/TenantSchemaMigration.java` only if other migrations are registered there — prefer standalone `@Order(26)` like V24/V25
- Test: `backend/java/src/test/java/com/crosshub/agent/repository/IntegrationAgentMachineBindRepoTest.java` (or extend `IntegrationAgentBindingFieldsTest.java`)

**Interfaces:**
- Produces: `Optional<IntegrationAgent> findByTenantIdAndMachineFingerprint(Long tenantId, String fingerprint)`
- Produces: `List<IntegrationAgent> findByTenantIdAndMachineFingerprintAndStatusNot(Long tenantId, String fingerprint, String status)` (optional; migration may use JDBC only)
- Produces: migration retires duplicate active agents sharing same `(tenant_id, fingerprint)` keeping newest heartbeat

- [ ] **Step 1: Write failing repo method test**

```java
@Test
void repositoryDeclaresTenantFingerprintLookup() throws Exception {
    assertNotNull(IntegrationAgentRepository.class.getMethod(
            "findByTenantIdAndMachineFingerprint", Long.class, String.class));
}
```

- [ ] **Step 2: Run test — expect FAIL (method missing)**

Run: `mvn -f backend/java/pom.xml -Dtest=IntegrationAgentBindingFieldsTest,IntegrationAgentMachineBindRepoTest test`

- [ ] **Step 3: Add repository method**

```java
Optional<IntegrationAgent> findByTenantIdAndMachineFingerprint(Long tenantId, String fingerprint);

List<IntegrationAgent> findByTenantIdOrderByLastHeartbeatAtDesc(Long tenantId);
```

(Keep existing `findByBoundUserId*` for audit/compat; stop using them for routing in later tasks.)

- [ ] **Step 4: Add V26 migration**

```java
@Component
@Order(26)
public class V26MachineBoundAgentMigration {
    // On ApplicationReadyEvent:
    // 1) For rows with non-empty machine_fingerprint grouped by (tenant_id, machine_fingerprint):
    //    keep one canonical (prefer max last_heartbeat_at, then created_at), set others:
    //      status='retired', agent_token='' (or random invalid), so they cannot heartbeat/claim
    // 2) CREATE INDEX IF NOT EXISTS idx_agent_tenant_fp
    //      ON integration_agent(tenant_id, machine_fingerprint);
    // SQLite: do not rely on partial UNIQUE if duplicates still exist before retire step —
    // retire first, then create index. Application upsert remains source of truth.
}
```

Register like V24 (`@Component` + `@EventListener(ApplicationReadyEvent.class)`).

- [ ] **Step 5: Re-run tests — PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/java/src/main/java/com/crosshub/config/migration/V26MachineBoundAgentMigration.java \
  backend/java/src/main/java/com/crosshub/agent/repository/IntegrationAgentRepository.java \
  backend/java/src/test/java/com/crosshub/agent/
git commit -m "feat(agent): Add tenant+fingerprint agent lookup and V26 dedupe"
```

---

### Task 2: Bind consume + me/status by tenant

**Files:**
- Modify: `backend/java/src/main/java/com/crosshub/agent/service/AgentBindCodeService.java`
- Modify: `backend/java/src/main/java/com/crosshub/agent/controller/AgentMeController.java`
- Modify: `backend/java/src/test/java/com/crosshub/agent/service/AgentBindCodeServiceTest.java`

**Interfaces:**
- Consumes: `findByTenantIdAndMachineFingerprint`
- Produces: `consume` upserts by `(entry.tenantId(), fingerprint)`; still sets `boundUserId` for audit
- Produces: `statusForTenant(Long tenantId)` (or `statusForUser` rewritten to take tenantId) listing tenant agents with heartbeat online flags

- [ ] **Step 1: Update failing tests in `AgentBindCodeServiceTest`**

Change mocks from `findByBoundUserIdAndMachineFingerprint` → `findByTenantIdAndMachineFingerprint`.

Add:

```java
@Test
void consume_sameTenantSameFingerprint_reusesAgent_evenIfDifferentUser() {
    // user 1 then user 2, same tenant + fp → same agent id, new token
    // boundUserId becomes user 2 (last binder)
}

@Test
void statusForTenant_includesAgentsBoundByOtherUsers() {
    // agent bound_user_id=1, query status for tenant → online true when heartbeat fresh
}
```

- [ ] **Step 2: Run tests — FAIL on old upsert key / missing status method**

Run: `mvn -f backend/java/pom.xml -Dtest=AgentBindCodeServiceTest test`

- [ ] **Step 3: Implement consume upsert**

In `consume`:

```java
IntegrationAgent agent = agentRepository
        .findByTenantIdAndMachineFingerprint(entry.tenantId(), fingerprint)
        .orElseGet(IntegrationAgent::new);
// ... same field sets ...
agent.setTenantId(entry.tenantId());
agent.setBoundUserId(entry.userId()); // audit only
agent.setMachineFingerprint(fingerprint);
agent.setStatus("active");
```

- [ ] **Step 4: Implement status by tenant**

```java
public Map<String, Object> statusForTenant(Long tenantId) {
    if (tenantId == null) {
        throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
    }
    List<IntegrationAgent> agents =
            agentRepository.findByTenantIdOrderByLastHeartbeatAtDesc(tenantId);
    // same online/recommended packing as statusForUser today
}
```

Deprecate/remove `statusForUser(Long userId)` callers; keep thin wrapper only if tests need it.

- [ ] **Step 5: Wire `AgentMeController.meStatus`**

```java
@GetMapping("/me/status")
public Map<String, Object> meStatus() {
    Long tenantId = requireTenantId();
    return Map.of("success", true, "data", bindCodeService.statusForTenant(tenantId));
}
```

- [ ] **Step 6: Run `AgentBindCodeServiceTest` — PASS**

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(agent): Bind and me/status by tenant machine fingerprint"
```

---

### Task 3: Route Temu / AE / Amazon / daily / retry to tenant machine agent

**Files:**
- Modify: `AgentPresenceService.java` — add clear helpers used by callers
- Modify: `TemuAgentService.java`, `TemuDailySyncService.java`, `TemuCrawlRetryService.java`
- Modify: `AliExpressAgentService.java`
- Modify: `AmazonSyncServiceImpl.java`, `AmazonWriteServiceImpl.java`
- Modify: `AppErrorCode.java` message strings (codes can stay)
- Modify tests: `TemuAgentServiceUserRoutingTest.java`, AE/Amazon tests that mock `findLatestOnlineAgentForUser`

**Interfaces:**
- Produces: `findLatestOnlineAgentForTenant(Long tenantId)` — may alias existing `findLatestOnlineAgent`
- Produces: callers pass `AuthContext` tenantId (already available where userId is used)
- Consumes: Task 2 status semantics (any online agent for tenant)

- [ ] **Step 1: Write/adjust failing routing tests**

Example (`TemuAgentServiceUserRoutingTest` rename or extend):

```java
@Test
void enqueueFailsWhenTenantHelperOffline() {
    when(agentPresenceService.findLatestOnlineAgent(tenantId)).thenReturn(null);
    // expect TEMU_USER_HELPER_OFFLINE
}

@Test
void enqueueTargetsTenantOnlineAgent() {
    when(agentPresenceService.findLatestOnlineAgent(tenantId)).thenReturn(agent);
    // task.agentId == agent.getId()
}
```

Replace every `findLatestOnlineAgentForUser(userId)` expectation with `findLatestOnlineAgent(tenantId)` (or new alias).

- [ ] **Step 2: Run affected tests — FAIL**

- [ ] **Step 3: Presence helpers**

```java
public IntegrationAgent findLatestOnlineAgentForTenant(Long tenantId) {
    return findLatestOnlineAgent(tenantId);
}

public boolean isAgentOnlineForTenant(Long tenantId) {
    return findLatestOnlineAgent(tenantId) != null;
}
```

Keep `findLatestOnlineAgentForUser` for one release but unused by product paths (or make it delegate to tenant via user→tenant lookup only if needed — prefer direct tenantId at call sites).

- [ ] **Step 4: Replace call sites**

| File | Change |
|------|--------|
| `TemuAgentService` | `findLatestOnlineAgent(tenantId)` / `ForTenant` |
| `TemuDailySyncService` | Skip users whose **tenant** has no online agent; enqueue with that agent id (do not require `isAgentOnlineForUser`) |
| `TemuCrawlRetryService` | Online check by tenant of the job |
| `AliExpressAgentService` | same |
| `AmazonSyncServiceImpl` / `AmazonWriteServiceImpl` | same |

Daily sync: still iterate users/shops for scope, but **presence gate is per tenant** (once online, all active users in tenant can be enqueued per existing shop scope rules).

- [ ] **Step 5: Update offline messages**

`AppErrorCode` + `appErrorCode.js`:

```text
本机同步助手未在线，请启动并绑定 Sync Helper（同一公司一台电脑绑定一次即可）
```

- [ ] **Step 6: Run Java unit tests for agent/temu/aliexpress/amazon routing — PASS**

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(agent): Route platform sync to tenant machine helper"
```

---

### Task 4: Python profile roots without `user-{id}`

**Files:**
- Modify: `backend/python/app/config.py` (`_profile_isolation_segment`, `resolve_profile_root`, `resolve_ae_profile_root`)
- Modify: `backend/python/app/session_scope.py` (legacy read under `user-*`)
- Modify: `backend/python/agent/bind.py` (`apply_profile_isolation_env` — do not force user segment)
- Test: `backend/python/tests/test_helper_bind_code.py`, new `backend/python/tests/test_profile_root_no_user_segment.py`

**Interfaces:**
- Produces: `_profile_isolation_segment()` returns `""` for CrossHub user env (ignore `CROSSHUB_BOUND_USER_ID` for path nesting)
- Produces: `resolve_platform_profile_dir` prefers `root/tenant-{id}/account-{key}`; if missing, falls back to first existing `root/user-*/tenant-{id}/account-{key}` for **read** only (return that path when it exists and new path does not)

- [ ] **Step 1: Failing tests**

```python
def test_profile_root_ignores_bound_user_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TEMU_PROFILE_ROOT", str(tmp_path))
    monkeypatch.setenv("CROSSHUB_BOUND_USER_ID", "55")
    from app.config import resolve_profile_root
    assert resolve_profile_root() == tmp_path

def test_resolve_dir_falls_back_to_legacy_user_segment(tmp_path):
    legacy = tmp_path / "user-55" / "tenant-5" / "account-default"
    legacy.mkdir(parents=True)
    from app.session_scope import resolve_platform_profile_dir
    got = resolve_platform_profile_dir("temu", 5, "default", root=tmp_path)
    assert got == legacy

def test_resolve_dir_prefers_new_path_when_present(tmp_path):
    legacy = tmp_path / "user-55" / "tenant-5" / "account-default"
    legacy.mkdir(parents=True)
    modern = tmp_path / "tenant-5" / "account-default"
    modern.mkdir(parents=True)
    from app.session_scope import resolve_platform_profile_dir
    assert resolve_platform_profile_dir("temu", 5, "default", root=tmp_path) == modern
```

- [ ] **Step 2: Run — FAIL**

Run: `pytest backend/python/tests/test_profile_root_no_user_segment.py -v`

- [ ] **Step 3: Implement**

`_profile_isolation_segment`: remove user-id branch (or gate behind unused flag). Keep optional `account-*` only if product still needs unbound account leaf — prefer `""` always so `session_scope` owns account segment.

`resolve_platform_profile_dir` after computing `nested`:

```python
if nested.is_dir():
    return nested
# legacy user-* scan (read compatibility)
for child in sorted(root.iterdir()) if root.is_dir() else []:
    if child.is_dir() and child.name.startswith("user-"):
        candidate = child / f"tenant-{tenant_id}" / f"account-{key}"
        if candidate.is_dir():
            return candidate
# existing default-key flat legacy tenant-{id} ...
return nested  # for create
```

`bind.apply_profile_isolation_env`: still may set env for audit, but must not nest roots under `user-*`.

- [ ] **Step 4: Fix any tests that assert `user-42` paths**

- [ ] **Step 5: pytest relevant bind/profile tests — PASS**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(helper): Use shop-scoped profiles without CrossHub user segment"
```

---

### Task 5: Install marker + panel `/api/install-info`

**Files:**
- Create: `backend/python/agent/install_marker.py`
- Modify: `backend/python/agent/tray_app.py` (route + write marker on start)
- Modify: `backend/python/scripts/sync_helper_app.py` (write marker on start if tray not used)
- Test: `backend/python/tests/test_install_marker.py`

**Interfaces:**
- Produces: `marker_path() -> Path` = `%LOCALAPPDATA%/CrossHub/SyncHelper/installed.json`
- Produces: `write_install_marker(version: str = "") -> dict`
- Produces: `read_install_marker() -> dict | None`
- Produces: `GET /api/install-info` → `{ ok, installed, path, version, installed_at }`

- [ ] **Step 1: Failing tests**

```python
def test_write_and_read_install_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from agent.install_marker import write_install_marker, read_install_marker
    write_install_marker(version="test")
    data = read_install_marker()
    assert data["installed"] is True
    assert data["version"] == "test"
```

- [ ] **Step 2: Implement `install_marker.py`**

```python
def marker_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return base / "CrossHub" / "SyncHelper" / "installed.json"
```

Write JSON: `installed`, `version`, `installed_at` (ISO), `fingerprint_preview` optional.

- [ ] **Step 3: Call `write_install_marker` on Helper startup** (tray + sync_helper_app)

- [ ] **Step 4: Add Flask route**

```python
@app.route("/api/install-info", methods=["GET", "OPTIONS"])
def api_install_info():
    if request.method == "OPTIONS":
        return ("", 204)
    from agent.install_marker import read_install_marker, marker_path
    data = read_install_marker() or {}
    return jsonify({
        "ok": True,
        "installed": bool(data.get("installed")),
        "path": str(marker_path()),
        "version": data.get("version") or "",
        "installed_at": data.get("installed_at") or "",
    })
```

(CORS already on tray `after_request`.)

- [ ] **Step 5: pytest — PASS**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(helper): Persist install marker and expose install-info API"
```

---

### Task 6: Vue status bar four-level offline UX

**Files:**
- Modify: `dev/vue-site/src/utils/agentProbe.js`
- Modify: `dev/vue-site/src/components/helper/HelperStatusBar.vue`
- Modify: `dev/vue-site/src/components/temu/TemuHelperStatusBar.vue`
- Modify: `dev/vue-site/src/utils/appErrorCode.js` (if not done in Task 3)

**Interfaces:**
- Consumes: `fetchLocalHelperBind`, `probeLocalAgent`, `GET /api/install-info`
- Produces: `probeHelperInstallState()` → `{ processUp, panelUp, installed, localTenantId, localBound }`
- Produces bar modes: `ready` | `need-login` | `rebind` | `start` | `offline`
  - `rebind`: Java offline + process/panel up (wrong/missing company bind)
  - `start`: Java offline + process down + `installed` true (from install-info **or** user acknowledged — when panel down, `installed` may be unknown: show secondary “我已安装，去启动”)
  - `offline`: download+bind

- [ ] **Step 1: Extend `agentProbe.js`**

```js
export async function fetchLocalInstallInfo(timeoutMs = 2000) {
  // GET http://127.0.0.1:18766/api/install-info CORS
  // on failure return { reachable: false, installed: false }
}

export async function probeHelperInstallState() {
  const [bind, install, health] = await Promise.all([
    fetchLocalHelperBind(),
    fetchLocalInstallInfo(),
    probeLocalAgent(),
  ])
  return {
    processUp: Boolean(health || bind.reachable),
    installed: Boolean(install.installed || bind.reachable),
    localTenantId: bind.tenant_id,
    localBound: bind.bound,
  }
}
```

Note: when Helper is stopped, `installed` cannot be read from panel — UI must still offer 「我已安装，请启动」 without requiring marker (marker helps when a future always-on stub exists; for now `installed` true only if panel answered or we keep a `localStorage` flag `crosshub_helper_installed=1` set after successful bind/download click).

Add:

```js
export function markHelperInstalledLocally() {
  localStorage.setItem('crosshub_helper_installed', '1')
}
export function hasLocalHelperInstallHint() {
  return localStorage.getItem('crosshub_helper_installed') === '1'
}
```

Set hint on successful bind-code dialog copy path and on download click.

- [ ] **Step 2: Status bar mode logic**

```js
const barMode = computed(() => {
  if (online.value) {
    if (supportsSessionLogin.value && !sessionReady.value) return 'need-login'
    return 'ready'
  }
  if (localState.value.processUp) return 'rebind'
  if (localState.value.installed || hasLocalHelperInstallHint()) return 'start'
  return 'offline'
})
```

Titles/meta per spec §3.4 / §5. Actions: `rebind` → 生成绑定码 + 打开面板; `start` → 打开面板指引 + 刷新 (download secondary); `offline` → 下载 primary + 绑定码.

- [ ] **Step 3: Compare local tenant vs `auth.tenantId` when processUp**

If `localBound && localTenantId === auth.tenantId` but Java offline → meta「助手进程在跑，等待心跳…」+ 刷新 (not aggressive rebind). If tenant mismatch → rebind copy.

- [ ] **Step 4: Manual UI check in browser (local Vite)** — same PC two users same tenant: after Task 3 Java restart, B sees online without rebind.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(web): Four-level Sync Helper status for machine-bound tenants"
```

---

### Task 7: Restart Java + acceptance smoke

**Files:** none (ops)

- [ ] **Step 1: Restart local Java**

Run: `powershell -File scripts\restart-java-api.ps1`  
Confirm `:18080` listening.

- [ ] **Step 2: Smoke checklist (manual)**

1. User A bind Helper → `/api/agent/me/status` online.  
2. Logout, User B same tenant same PC → status online without clear-bind.  
3. B triggers Temu session status / sync enqueue → task `agent_id` = machine agent.  
4. Stop Helper → status offline; with install hint →「请启动」not forced download.  
5. Different tenant account → rebind required.  
6. Profile path on disk: new login writes `…/tenant-{tid}/account-{key}/` not under `user-*`.

- [ ] **Step 3: Commit any smoke fixes; mark spec status「实施中」if desired**

```bash
git commit -m "chore(helper): Smoke fixes for machine-bound tenant helper"
```

---

## Spec coverage self-check

| Spec requirement | Task |
|------------------|------|
| Upsert `(tenant_id, machine_fingerprint)` | 1–2 |
| `bound_user_id` audit only | 2 |
| me/status tenant-wide online | 2 |
| Temu/AE/Amazon route to machine agent | 3 |
| Daily/retry presence by tenant | 3 |
| Offline copy machine-oriented | 3, 6 |
| Profile without user segment + legacy read | 4 |
| Install marker + `/api/install-info` | 5 |
| Status bar 4 levels | 6 |
| Acceptance same-PC two users | 7 |
| No web disk scan | 5–6 |
| No cross-tenant share | 2 (tenant on bind code) |

## Out of scope (do not implement in this plan)

- Cross-tenant one token  
- Web scraping Downloads folder  
- Auto-moving old `user-*` profile trees  
- Production deploy
