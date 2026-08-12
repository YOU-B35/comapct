# Platform Sync History 鈥?Design Spec

**Date:** 2026-08-12  
**Status:** Implemented
**Scope:** Temu + AliExpress + Amazon module headers 鈥?last sync summary + sync history drawer (recent 20)

## Goal

Users can clearly see when data was last synced, how many records were obtained, when the run happened, and how long it took 鈥?plus a short history of recent syncs per platform.

## Decisions (locked)

| Decision | Choice |
|----------|--------|
| Platforms | Temu, AliExpress, Amazon |
| Placement | Each platform module page header |
| History depth | Recent **20** jobs |
| Approach | Reuse `last_job` / existing job entities; add missing list APIs; shared drawer UI |
| Duration | Computed client-side from `started_at` / `finished_at` (not persisted) |
| Out of scope | Global sidebar aggregate table, unified cross-platform history API, dedicated history page, Walmart / 1688 / Domestic |

## UX

### Header summary

On Temu / AliExpress / Amazon panel headers, replace or extend the existing 鈥滄渶杩戝悓姝?{{ syncedAt }}鈥?line:

- **Success:** `鏈€杩戝悓姝?YYYY-MM-DD HH:mm 路 N 鏉?路 鑰楁椂 XmYs`  
  (optional platform-specific secondary count, e.g. Temu shops, when available)
- **Failed:** `鏈€杩戝悓姝ュけ璐?HH:mm 路 {short error}`
- **Running / pending:** `鍚屾涓€ (no fake wall-clock)
- **Never synced:** hide summary or show `灏氭湭鍚屾`

Add a text button **銆屽悓姝ヨ褰曘€?* that opens the history drawer.

**Timestamp source:** wall-clock `finished_at` (fallback `started_at` / `created_at`). Do **not** use Temu `report_time` (sales report day) as the sync clock.

**Count source (per platform):**

| Platform | Primary count | Secondary (optional) |
|----------|---------------|----------------------|
| Temu | `rows_count` (sales SKU rows) | `shops_count` |
| AliExpress | Prefer `orders_count` / `products_count` / `violations_count` / `rows_count` (show fields that are present) | 鈥?|
| Amazon | Counts from job `result_summary` or sync-version (`product_count` / `item_count` / `metric_count`) | 鈥?|

### History drawer

- Title: `鍚屾璁板綍`
- Table columns: 鐘舵€?| 寮€濮嬫椂闂?| 缁撴潫鏃堕棿 | 鑰楁椂 | 鑾峰彇鏉℃暟 | 瑙﹀彂鏂瑰紡 | 澶辫触鍘熷洜
- Load on open: platform-specific history API with `limit=20`
- Empty: `鏆傛棤鍚屾璁板綍`
- Trigger labels: map `triggered_by` / mode / known flags to `鎵嬪姩` / `瀹氭椂` / `绯荤粺` (best-effort)

## Backend

### Shared job row shape (API response items)

Each list endpoint returns `{ success, data: { jobs: [...] } }` (or Amazon鈥檚 existing envelope adapted by the frontend). Each job includes at least:

- `job_id` (or `id`)
- `status`
- `started_at`, `finished_at`, `created_at`
- Platform count fields as above
- `error_code`, `error_message` (when failed)
- `triggered_by` and/or `trigger` when available

Duration is **not** required from the API.

### Endpoints

| Platform | Endpoint | Notes |
|----------|----------|-------|
| Temu | `GET /api/temu/jobs?limit=20` | Use existing `TemuCrawlJobRepository.findTop60ByTenantIdOrderByCreatedAtDesc`; clamp `limit` to 1鈥?0, default 20. Reuse crawl-job DTO mapper. |
| AliExpress | `GET /api/aliexpress/jobs?limit=20` (or `crawl-jobs`) | Add repo `findTopN鈥rderByCreatedAtDesc` if missing; same clamp rules. |
| Amazon | Existing `GET /api/agent/amazon/sync-jobs` | Frontend takes first 20, **or** add optional `limit` query (prefer optional `limit` for consistency). |

### Header data source

- Prefer `/api/platform/sync-status` 鈫?platform `last_job` for initial paint.
- After manual refresh / poll success, update header from the completed job payload immediately (same fields).

## Frontend

### Shared pieces

- Small util: format duration (`finished_at - started_at` 鈫?Chinese short form).
- Shared drawer component (e.g. `SyncHistoryDrawer.vue`) parameterized by platform + fetch function.
- Extend panel headers:
  - `Temu` header (or module toolbar where refresh lives)
  - `AliExpressPanelHeader.vue`
  - `AmazonPanelHeader.vue`

Wire open-drawer + pass last-job summary props from each module view.

### Temu-specific fix

Stop treating `report_time` as `syncedAt` for the header clock; keep `report_time` only if still needed as 鈥滄暟鎹棩鏈熲€?elsewhere.

## Testing

- Backend: list endpoints return newest-first, respect `limit`, tenant-scoped.
- Frontend util: duration formatting edge cases (missing end, negative, &lt;1s).
- Optional smoke: header shows finished_at after mock last_job; drawer loads 20 rows.

## Non-goals (this round)

- Mounting unused `PlatformSyncLogPanel` as global sidebar
- Persisting `duration_ms`
- Cross-platform aggregate API
- Changing Sync Helper / agent crawl logic beyond exposing existing job fields
