# Task 7 Report — Helper bind-code UI + machine fingerprint + profile isolation

**Status:** DONE  
**Base HEAD:** `32170bc`  
**Commit:** (see git log) — `feat(helper): bind-code enrollment and machine fingerprint`

## Summary

Sync Helper can enroll via website bind code: stable machine fingerprint (`hostname` + Windows `MachineGuid`), panel paste UI, `POST /api/agent/bind` snake_case body, persist `agent_token` / `user_id` / `tenant_id` / `java_api_url` to `config.json`, clear/rebind for multi CrossHub accounts on one PC, and nest Temu/AE profile roots under `user-{id}` (or `account-*`) when bound. Default `java_api_url` remains `https://www.yoto.work`.

## TDD evidence

### RED

```text
py -m pytest tests/test_helper_bind_code.py -v --tb=short
```

- `ModuleNotFoundError: No module named 'agent.machine_id'`
- `ModuleNotFoundError: No module named 'agent.bind'`
- Profile root assertion failed (no `user-42` segment)

### GREEN

```text
py -m pytest tests/test_helper_bind_code.py tests/test_sync_helper_config_priority.py -v --tb=short

tests/test_helper_bind_code.py::test_machine_fingerprint_non_empty PASSED
tests/test_helper_bind_code.py::test_consume_bind_code_posts_snake_case_body_and_persists PASSED
tests/test_helper_bind_code.py::test_profile_root_includes_user_isolation PASSED
tests/test_sync_helper_config_priority.py (3) PASSED
============================== 6 passed ==============================
```

## Changes

| File | Change |
|------|--------|
| `agent/machine_id.py` | `machine_fingerprint()` = sha256(hostname \| MachineGuid) |
| `agent/bind.py` | `consume_bind_code` / `clear_binding` / `binding_status` / `apply_bound_env` |
| `agent/panel/index.html` | Bind-code form +「清除绑定」rebind |
| `agent/tray_app.py` | `GET/POST/DELETE /api/bind`; status includes `bound` |
| `scripts/sync_helper_app.py` | Unbound start → panel; apply profile isolation; keep online Java default |
| `app/config.py` | Profile root nests `user-*` / `account-*` |
| `tests/test_helper_bind_code.py` | Fingerprint + httpx mock snake_case bind body + isolation |

## Concerns

1. After bind, Agent poll loop still requires **Helper restart** (panel message); hot-reload of token into a running unbound process is not fully wired.
2. Pre-existing local profile dirs without `user-{id}` are not migrated; new isolation path starts fresh under nested root.
3. Did **not** commit Java `AppErrorCode` / `AgentServiceImpl` WIP.
