# Task 5 Report — End-to-end verification checklist

**Status:** PARTIAL PASS (automated green; live protocol matrix blocked without registered exe + missing `openHelperDownload` export)  
**Worktree:** `.worktrees/helper-connect-launch`  
**Branch:** `impl/helper-connect-launch`  
**Date:** 2026-08-12  
**Commit:** none (verification only; no code changes)

## Step 1: Frontend unit tests

```text
cd .worktrees/helper-connect-launch/dev/vue-site
node --test tests/agentConnect.test.mjs
```

**Result: PASS** — 4/4

| Test | Result |
|------|--------|
| HELPER_PROTOCOL_START is fixed scheme | PASS (`crosshub-sync-helper://start`) |
| already_running when probe true before trigger | PASS → message `本机助手已在运行` |
| started when probe becomes true after trigger | PASS → message `助手已启动` |
| not_found when probe never true | PASS → message matches `/请先下载安装/` (`未检测到本机助手，请先下载安装 Sync Helper`) |

## Step 2: Python unit tests

```text
cd .worktrees/helper-connect-launch/backend/python
py -m pytest tests/test_protocol_launch.py -v
```

**Result: PASS** — 2/2

| Test | Result |
|------|--------|
| `test_is_protocol_start_flag` | PASS |
| `test_ports_already_serving_false_when_closed` | PASS |

## Step 3: Checks without full exe rebuild

### 3a. 「连接助手」 on both bars + three modules

| Surface | Evidence | Result |
|---------|----------|--------|
| `HelperStatusBar.vue` | Label `连接助手` ×5 (rebind / offline / need-login / else + error string); `connectLocalHelper` | PASS |
| `TemuHelperStatusBar.vue` | Same pattern (`连接助手` ×5) + `connectLocalHelper` | PASS |
| Temu module | `TemuModuleView.vue` mounts `TemuHelperStatusBar` | PASS (static) |
| AliExpress module | `AliExpressModuleView.vue` mounts `HelperStatusBar` | PASS (static) |
| Amazon module | `AmazonModuleView.vue` mounts `HelperStatusBar` | PASS (static) |

### 3b. Protocol helpers import + `ports_already_serving`

```text
from agent.protocol_launch import is_protocol_start_argv, ports_already_serving
```

| Check | Result |
|-------|--------|
| Import | PASS |
| `is_protocol_start_argv(['x','--protocol-start'])` | True |
| `is_protocol_start_argv(['x','crosshub-sync-helper://start'])` | True |
| Live `ports_already_serving(18765, 18766)` | False (helper not listening; expected) |

### 3c. Vue on :5174 (this worktree)

| Item | Result |
|------|--------|
| `vite.config.js` default | `port: 5173`, `strictPort: false` |
| Already running | PID 28260: worktree `dev/vue-site` → `vite.js --port 5174 --strictPort` |
| `http://localhost:5174/` | HTTP 200 |
| Protocol HKCU `crosshub-sync-helper` | **not registered** (`HKCU:\Software\Classes\crosshub-sync-helper` missing) |

### 3d. Manual matrix (no new exe)

| Case | Expect | Verified? | Notes |
|------|--------|-----------|-------|
| Helper stopped, protocol not registered | 连接助手 → 中文「请先下载安装」 | **Partial** | Unit path returns `未检测到本机助手，请先下载安装 Sync Helper`. Live click blocked by missing export (below). No protocol registration. |
| Helper stopped, protocol registered | 连接助手 → process up →「助手已启动」 | **SKIPPED** | Needs HKCU registration + packaged/local helper exe; not rebuilt this task. |
| Helper already running | 「本机助手已在运行」+ panel | **Partial** | Covered by unit test; live helper ports down so runtime path not exercised. |
| Temu + AE + Amazon bars | Button present on all three | **PASS (static)** | Wiring confirmed in SFCs; browser click-through blocked by load error. |

## Step 4: Commit

Skipped — report only; no design/plan checklist updates.

## Concerns

1. **Runtime import break on Vue:** Both bars import `openHelperDownload` from `@/api/agentHelper`, but that export is **missing** (only `resolveHelperDownloadUrl` / `DEFAULT_HELPER_DOWNLOAD_URL` exist). Served module on :5174 confirms no `openHelperDownload`. This blocks helper-bar routes until fixed (out of Task 5 scope; no code change per brief).

2. **Live protocol E2E incomplete:** no HKCU protocol registration and no helper on 18765/18766; cannot prove start-via-`crosshub-sync-helper://start` without Task 4 packaging/register path.

3. **Vite port:** config still defaults to 5173; worktree already serves explicit `--port 5174` (matches brief).

## Spec coverage self-check (verification posture)

| Spec item | Verification |
|-----------|--------------|
| Button on HelperStatusBar + TemuHelperStatusBar | Static PASS |
| Probe then protocol then poll | Unit PASS (`agentConnect.test.mjs`) |
| Chinese messages | Unit PASS (already_running / started / not_found) |
| `crosshub-sync-helper://start` | Unit + `is_protocol_start_argv` PASS; live launch SKIPPED |
| HKCU registration + packaging | Not present on this machine; Task 4 artifact needed |
| Single-instance / already running | Unit PASS; live `ports_already_serving` False with helper down |
| Bind flow unchanged | Not re-tested (no bind API tasks) |
| Rollout: frontend before new exe OK | Unit `not_found` timeout path PASS |

## Verdict

Automated checklist **green**. Manual browser/protocol matrix **not fully closable** without adding `openHelperDownload` and registering/running Sync Helper.

---

## Follow-up fix — `openHelperDownload` export (2026-08-12)

**Problem:** Bars import `openHelperDownload` from `@/api/agentHelper`, but worktree file only had a relative `resolveHelperDownloadUrl` / `DEFAULT_HELPER_DOWNLOAD_URL`.

**Fix:** Ported from parent `dev/vue-site/src/api/agentHelper.js`:
- `HELPER_DOWNLOAD_ORIGIN`, `DEFAULT_HELPER_DOWNLOAD_PATH`, `DEFAULT_HELPER_DOWNLOAD_URL`
- `resolveHelperDownloadUrl` (absolutizes non-empty env values)
- `absolutizeHelperDownloadUrl`
- `openHelperDownload`

**Verify:**
```text
# Grep: openHelperDownload exported
export function openHelperDownload(...)  # agentHelper.js:210

cd .worktrees/helper-connect-launch/dev/vue-site
node --test tests/agentConnect.test.mjs
# PASS 4/4 (fail 0)
```

**Commit:** `fix(helper): export openHelperDownload for status bars` (author CrossHub Agent)

**Remaining concerns:** Live protocol E2E still needs HKCU registration + helper on 18765/18766; Vite default port still 5173 (worktree uses 5174 explicitly).

---

## Final review Important fixes (2026-08-12)

**Status:** DONE  
**Branch:** `impl/helper-connect-launch`

### Fix 1 — Packaging README contradiction

`scripts/build-sync-helper-exe.ps1` generated `README.txt` rewritten for **user-local Sync Helper**:
- Double-click exe / keep running
- Panel `http://127.0.0.1:18766`
- Website bind code
- `java_api_url` default `https://www.yoto.work`
- Chrome required
- Steps 6–7 kept (`register-protocol.ps1` / `crosshub-sync-helper://start`)
- Removed ops-only / “don't expose download on ops web” language

### Fix 2 — Browser intercept tip

`dev/vue-site/src/utils/agentConnect.js` `not_found` message now includes allow-open tip:

`未检测到本机助手，请先下载安装 Sync Helper。若浏览器拦截了打开提示，请允许打开 CrossHub Sync Helper`

`tests/agentConnect.test.mjs` asserts `/请先下载安装/` and `/允许打开/`.

### Verify

```text
cd dev/vue-site
node --test tests/agentConnect.test.mjs
# PASS 4/4 (fail 0)
```

**Commit:** `fix(helper): align README and connect timeout copy` (author CrossHub Agent)
