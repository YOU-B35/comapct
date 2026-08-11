# Task 3 Report — Task routing (user agent enqueue + poll filter)

**Status:** DONE_WITH_CONCERNS  
**Base HEAD:** `792bc6b`  
**Commit:** `01380fc` — `feat(temu): route agent tasks to the calling user's online helper`

## Summary

Temu web/session/crawl enqueue paths resolve the acting user's online bound Sync Helper and persist `agent_task.agent_id`. Agent poll claims only blank (legacy) or matching `agent_id` tasks. Missing user helper → **503** with exact Chinese: `本机同步助手未在线，请先安装并绑定`.

## TDD evidence

### RED

```text
mvn -f backend/java/pom.xml "-Dtest=TemuAgentServiceUserRoutingTest,AgentServiceImplPollFilterTest" test
```

- **TemuAgentServiceUserRoutingTest**: testCompile failed — missing `isAgentOnlineForUser` / `enqueueLoginOpenForUser`.
- Poll filter would have claimed foreign-targeted tasks before `isClaimableByAgent`.

### GREEN

```text
Tests run: 2, Failures: 0, Errors: 0
- AgentServiceImplPollFilterTest (pollSkipsTaskAimedAtOtherAgent)
- TemuAgentServiceUserRoutingTest (enqueueLoginOpenRequiresUserOnlineHelper)
BUILD SUCCESS
```

## Changes

| File | Change |
|------|--------|
| `AgentPresenceService.java` | `findLatestOnlineAgentForUser` / `isAgentOnlineForUser` (bound-user + 90s heartbeat) |
| `TemuAgentService.java` | `assertAgentOnlineForUser` (503); `enqueueLoginOpenForUser` / frontend ForUser; `insertAgentTask(..., agentId)`; crawl uses `triggeredBy`; session probe(userId) |
| `AgentServiceImpl.java` | poll skips non-matching non-blank `agent_id` |
| `TemuSessionServiceImpl.java` | AuthContext `userId` for login/frontend/probe |
| `TemuCrawlServiceImpl.java` | `assertAgentOnlineForUser(userId)` |
| `AppErrorCode.java` | `TEMU_USER_HELPER_OFFLINE` (+ see Concerns) |
| Tests | `TemuAgentServiceUserRoutingTest`, `AgentServiceImplPollFilterTest` |

## Concerns

1. **`AppErrorCode.java`** also includes pre-existing dirty WIP enums (team/AE/human-challenge) that were already in the working tree — additive only; not required for Task 3 beyond `TEMU_USER_HELPER_OFFLINE`.
2. **`AgentServiceImpl`** includes optional `AliExpressBridge` wiring (no hard dependency on untracked AE sources). Poll filter is the Task 3 behavior.
3. **Daily sync / retry / competitor** still tenant-wide or blank `agent_id` when `triggeredBy` ≤ 0 — Task 5 / later.
4. Legacy blank `agent_id` remains claimable by any tenant agent (intentional).

## Review fix (Important findings)

**Commit:** _(pending)_ — `fix(temu): strip Task 3 out-of-scope AppErrorCode and AE bridge`

### What changed

1. **`AppErrorCode.java`** — Restored from parent `792bc6b`, then re-added only `TEMU_USER_HELPER_OFFLINE` (`本机同步助手未在线，请先安装并绑定`). Removed out-of-scope team / AE / human-challenge enums and their `BY_REASON` / `classifyCrawlRaw` mappings that had been dumped in `01380fc`.
2. **`AgentServiceImpl.java`** — Removed `AliExpressBridge` interface, constructor/field, start/complete/stale callbacks, and AE task-type TTL branches. Kept poll filter (`isClaimableByAgent`) only. Matches pre–Task 3 TemuBridge-only pattern for AE.
3. **Tests** — Dropped `AliExpressBridge` ctor args from `AgentServiceImplTest` and `AgentServiceImplPollFilterTest`.

### Covering tests (re-run)

```text
mvn -f backend/java/pom.xml "-Dtest=TemuAgentServiceUserRoutingTest,AgentServiceImplPollFilterTest,AgentServiceImplTest" test

Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
- AgentServiceImplPollFilterTest
- AgentServiceImplTest
- TemuAgentServiceUserRoutingTest
BUILD SUCCESS
```

### WIP note

Other working-tree files still reference stripped symbols (`AE_AGENT_OFFLINE`, `CRAWL_HUMAN_CHALLENGE`, `TEAM_LEADER_ACTIVE`, `AgentServiceImpl.AliExpressBridge`) — e.g. `AliExpressAgentService`, `AliExpressAgentBridge`, `TemuCrawlRetryService`, `TenantMemberLeaderGuardTest`. Those are outside Task 3; they will not compile until their own tasks restore enums / AE bridge wiring.
