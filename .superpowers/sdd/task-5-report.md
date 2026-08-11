# Task 5 Report — Daily sync per online user

**Status:** DONE (Important review fixes applied)  
**Base HEAD:** `6f20557`  
**Commit:** `2b3503c` — `feat(temu): daily sync enqueues per online user-bound helper`  
**Fix commit:** _(pending)_ — `fix(temu): daily sync scope — drop unused repo methods and honor shop_ids`

## Summary

09:30 scheduler entry (`runDailySyncForAllRegisteredTenants` / `PlatformDailySyncService`) unchanged. Per tenant, `enqueueDailyCrawl` lists active non-warehouse users; for each user with an online bound helper it enqueues one crawl (`triggeredBy` = user id → Task 3 `agent_id` routing) with `shop_ids` from `DataScopeService.resolveScopeForLogin`. Users without an online helper are **skipped** (logged `skipped_offline`); **no** failed/parked jobs are created for them.

## Rate limits

Daily path calls `TemuAgentService.enqueueCrawlJob(job, shopIds)` directly — **does not** go through `TemuSyncLimitService` / per-user 3/min UI quota (system scheduler job). Documented on `enqueueCrawlJob` javadoc and `TemuDailySyncService` class comment.

## TDD evidence

### RED

```text
mvn -f backend/java/pom.xml "-Dtest=TemuDailySyncEnqueueTest" test
```

- testCompile failed: constructor / repo / `enqueueCrawlJob(job, shopIds)` missing.

### GREEN

```text
mvn -f backend/java/pom.xml "-Dtest=TemuDailySyncEnqueueTest" test

Tests run: 2, Failures: 0, Errors: 0
- enqueuesOnlyForUsersWithOnlineHelper
- skipsAllOfflineUsersWithoutCreatingJobs
BUILD SUCCESS
```

## Changes

| File | Change |
|------|--------|
| `TemuDailySyncService.java` | Per-user loop; skip offline; shop scope; no failed-job spam |
| `TemuAgentService.java` | `enqueueCrawlJob(job, shopIds)` payload `shop_ids` |
| `TemuCrawlJobRepository.java` | Per-user latest / active lookups |
| `AppUserRepository.java` | `findByTenantIdOrderByIdAsc` |
| `TemuDailySyncEnqueueTest.java` | Two-user online/offline coverage |

## Concerns

1. ~~**Python Helper** may not yet filter crawl by payload `shop_ids`~~ — **fixed** (see below).
2. **Employee with empty shop scope** is skipped (`skipped_no_scope`); Boss (`admin`) gets empty `shop_ids` (= unrestricted in payload).
3. **Warehouse users** excluded from daily candidates.
4. Did **not** commit dirty WIP `AppErrorCode.java` / `AgentServiceImpl.java`.

---

## Review fix evidence (Important)

### 1. Strip out-of-scope repository methods

Removed from `TemuCrawlJobRepository` (were unused by Task 5 / daily sync):

- `findTop60ByTenantIdOrderByCreatedAtDesc`
- `findByStatusAndNextRetryAtLessThanEqualOrderByNextRetryAtAsc`

Kept Task 5 methods: `findFirstByTenantIdAndTriggeredByOrderByCreatedAtDesc`, `findFirstByTenantIdAndTriggeredByAndStatusInOrderByCreatedAtDesc`. Callers for the stripped methods (`AgentOpsLogService`, `TemuCrawlRetryService`) remain uncommitted WIP and will re-add those methods in their owning tasks.

### 2. Honor `shop_ids` in Helper crawl path

- `app/temu/shop_scope.py` — allowlist normalize + mall/payload filter helpers
- `handlers.handle_temu_crawl` reads `payload.shop_ids` → `crawl_and_ingest(..., shop_ids=...)`
- `temu_crawler.crawl_temu_sales*` filters malls before switch/fetch when allowlist non-empty

### Fix verification

```text
# Java (WIP callers temporarily held out of compile path)
mvn -f backend/java/pom.xml -Dtest=TemuDailySyncEnqueueTest test
Tests run: 2, Failures: 0, Errors: 0
BUILD SUCCESS

# Python
python -m pytest tests/test_temu_shop_scope.py -q
4 passed
```

(Additional local check against WIP HTTP crawler: `test_temu_http_sync_crawl.py` shop_ids case — not included in this commit.)
