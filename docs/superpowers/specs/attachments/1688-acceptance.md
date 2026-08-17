# 1688 Ops Acceptance — 2026-08-17

Spec: `docs/superpowers/specs/2026-08-17-alibaba1688-ops-design.md`  
Plan: `docs/superpowers/plans/2026-08-17-alibaba1688-ops.md`  
Branch: `feat/alibaba1688-ops`  
Defaults: Day0 skeleton + fixture path (2A); commits deferred until user asks (1B)

| ID | Expectation | Result | Notes |
|----|-------------|--------|-------|
| A01 | login_probe → manual login → session usable | PARTIAL | Playwright login_probe implemented; needs human login on local Windows |
| A02 | sync stores purchase orders (not Demo RNG) | PARTIAL | Fixture path via `A1688_USE_FIXTURE=1`; live XHR blocked until Day0 fills `PURCHASE_LIST_URL` + keywords |
| A03 | delayed/stockout highlighted + supplier_alert | PASS (code) | Rules + rebuildAlerts; UI tags in PurchasePanel |
| A04 | 90-day supplier ranking visible | PASS (code) | SupplierPanel ranking block + `alibaba1688_supplier_stat` |
| A05 | overview four metrics match lists | PASS (code) | BossOverview + OperationalAggregator |
| A06 | conflict toast when sync already running | PASS (code) | 409 + `CRAWL_IN_PROGRESS` |
| A07 | Java down → Demo + hint | PASS (code) | `alibaba1688.js` facade fallback |
| A08 | employee scoped stores only | PASS (code) | existing `scopeStores` |
| A09 | no reconciliation; no server crawl | PASS | Global constraints honored |

## Remaining human steps

1. Fill `docs/superpowers/specs/attachments/1688-purchase-xhr.md` with real buyer DevTools notes.
2. Populate `STOCKOUT_KEYWORDS` + `PURCHASE_LIST_URL` in `alibaba1688_constants.py`.
3. Local smoke: login_probe → sync → `/boss/1688` panels show DB rows.
4. User commit when ready (working tree currently holds Tasks 3–10).
