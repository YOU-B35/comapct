"""Consume pending monitor jobs and persist snapshots, signals, and reports."""
from __future__ import annotations

import json
import sqlite3
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


def process_next_pending_job(
    conn: sqlite3.Connection,
    *,
    adapters: dict[str, object],
    report_root: Path,
    worker_id: str = "monitor-worker",
) -> dict | None:
    job = conn.execute(
        """
        SELECT * FROM monitor_job
        WHERE status = 'pending'
        ORDER BY queued_at ASC
        LIMIT 1
        """
    ).fetchone()
    if job is None:
        return None

    claimed = conn.execute(
        """
        UPDATE monitor_job
        SET status = 'running', started_at = ?, worker_id = ?
        WHERE id = ? AND status = 'pending'
        """,
        (now_text(), worker_id, job["id"]),
    )
    conn.commit()
    if claimed.rowcount == 0:
        return None

    job = conn.execute("SELECT * FROM monitor_job WHERE id = ?", (job["id"],)).fetchone()
    target = conn.execute(
        "SELECT * FROM monitor_target WHERE tenant_id = ? AND id = ? LIMIT 1",
        (job["tenant_id"], job["target_id"]),
    ).fetchone()
    if target is None:
        fail_job(conn, job["id"], "MONITOR_TARGET_NOT_FOUND", "Monitor target not found")
        raise RuntimeError("Monitor target not found")

    schedule = conn.execute(
        "SELECT * FROM monitor_schedule WHERE tenant_id = ? AND target_id = ? LIMIT 1",
        (job["tenant_id"], job["target_id"]),
    ).fetchone()
    max_products = int(schedule["max_products"]) if schedule is not None else 100
    adapter = adapters.get(target["platform"])
    if adapter is None:
        fail_job(conn, job["id"], "MONITOR_PLATFORM_UNSUPPORTED", f"Unsupported platform: {target['platform']}")
        raise RuntimeError(f"Unsupported platform: {target['platform']}")

    adapter_target = dict(target)
    adapter_target["job_id"] = job["id"]
    adapter_target["trigger_type"] = job["trigger_type"]
    adapter_target["force_refresh"] = bool_value(job["force"]) if "force" in job.keys() else False

    try:
        payload = adapter.crawl_target(
            tenant_id=int(job["tenant_id"]),
            target=adapter_target,
            max_products=max_products,
        )
        snapshot_at = payload.get("snapshot_at") or now_text()
        products = payload.get("products") or []
        analysis = analyze_products(conn, int(job["tenant_id"]), str(job["target_id"]), snapshot_at, products)
        snapshot_id = f"ms_{uuid.uuid4().hex}"
        report_paths = write_reports(
            report_root=report_root,
            platform=str(target["platform"]),
            target_id=str(target["id"]),
            snapshot_at=snapshot_at,
            snapshot_id=snapshot_id,
            target_label=str(target["label"]),
            products=products,
            analysis=analysis,
        )
        ingest_id = start_ingest_batch(
            conn,
            tenant_id=int(job["tenant_id"]),
            platform=str(target["platform"]),
            report_day=snapshot_at[:10],
            scope="monitor_snapshot",
            detail={
                "job_id": str(job["id"]),
                "target_id": str(target["id"]),
                "target_url": str(target["target_url"]),
                "trigger_type": str(job["trigger_type"]),
                "force_refresh": bool(adapter_target.get("force_refresh")),
                "max_products": int(max_products),
                "report_md_path": str(report_paths["report_md_rel"]),
                "report_xlsx_path": str(report_paths["report_xlsx_rel"]),
                "crawl_meta": payload.get("meta") if isinstance(payload, dict) else None,
            },
        )
        snapshot_id = persist_snapshot(
            conn,
            snapshot_id=snapshot_id,
            tenant_id=int(job["tenant_id"]),
            target_id=str(target["id"]),
            platform=str(target["platform"]),
            snapshot_at=snapshot_at,
            products=products,
            analysis=analysis,
            report_paths=report_paths,
        )
        finish_ingest_batch(
            conn,
            ingest_id=ingest_id,
            status="success",
            detail={
                "snapshot_id": snapshot_id,
                "product_count": len(products),
                "recent_launch_count": len(analysis["recent_launches"]),
                "sales_outlier_count": len(analysis["sales_outliers"]),
            },
        )
        conn.execute(
            """
            UPDATE monitor_target
            SET latest_snapshot_id = ?, latest_snapshot_at = ?, updated_at = ?
            WHERE tenant_id = ? AND id = ?
            """,
            (snapshot_id, snapshot_at, now_text(), job["tenant_id"], job["target_id"]),
        )
        conn.execute(
            """
            UPDATE monitor_job
            SET status = 'success', finished_at = ?, snapshot_id = ?, error_code = NULL, error_message = NULL, error_detail = NULL
            WHERE id = ?
            """,
            (now_text(), snapshot_id, job["id"]),
        )
        conn.commit()
        record_monitor_crawl_success(conn, int(job["tenant_id"]), str(job["target_id"]))
        return {
            "job_id": job["id"],
            "status": "success",
            "snapshot_id": snapshot_id,
            "product_count": len(products),
            "recent_launch_count": len(analysis["recent_launches"]),
            "sales_outlier_count": len(analysis["sales_outliers"]),
            "report_md_path": str(report_paths["report_md_abs"]),
            "report_xlsx_path": str(report_paths["report_xlsx_abs"]),
        }
    except Exception as exc:
        # best-effort：如果 ingest_batch 已创建，记录失败原因，避免“覆盖写不可追溯”
        try:
            ingest_id = locals().get("ingest_id")
            if ingest_id:
                finish_ingest_batch(
                    conn,
                    ingest_id=str(ingest_id),
                    status="failed",
                    detail={"error": str(exc)[:1800]},
                )
        except Exception:
            pass
        error_code, message = monitor_error_from_exception(exc)
        fail_job(conn, job["id"], error_code, message)
        raise


def monitor_error_from_exception(exc: Exception) -> tuple[str, str]:
    message = str(exc)
    if message.startswith("MONITOR_"):
        code, sep, rest = message.partition(":")
        if sep and code.replace("_", "").isalnum():
            return code, rest.strip() or message
    return "MONITOR_JOB_FAILED", message


def record_monitor_crawl_success(
    conn: sqlite3.Connection, tenant_id: int, target_id: str
) -> None:
    """Persist monitor-target cooldown scope only (never tenant platform)."""
    now = now_text()
    scope = f"monitor:{target_id}"
    conn.execute(
        """
        INSERT INTO tenant_crawl_cooldown (tenant_id, scope, last_success_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tenant_id, scope) DO UPDATE SET
          last_success_at = excluded.last_success_at,
          updated_at = excluded.updated_at
        """,
        (tenant_id, scope, now, now),
    )
    conn.commit()



def fail_job(conn: sqlite3.Connection, job_id: str, error_code: str, message: str) -> None:
    conn.execute(
        """
        UPDATE monitor_job
        SET status = 'failed', finished_at = ?, error_code = ?, error_message = ?, error_detail = ?
        WHERE id = ?
        """,
        (now_text(), error_code, message[:500], message[:2000], job_id),
    )
    conn.commit()


def start_ingest_batch(
    conn: sqlite3.Connection,
    *,
    tenant_id: int,
    platform: str,
    report_day: str | None,
    scope: str,
    detail: dict,
) -> str:
    ingest_id = f"ib_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO ingest_batch (
          id, tenant_id, platform, report_day, scope, status, started_at, finished_at, detail_json
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, ?)
        """,
        (
            ingest_id,
            tenant_id,
            platform,
            report_day,
            scope,
            now_text(),
            json.dumps(detail or {}, ensure_ascii=False),
        ),
    )
    conn.commit()
    return ingest_id


def finish_ingest_batch(
    conn: sqlite3.Connection,
    *,
    ingest_id: str,
    status: str,
    detail: dict | None = None,
) -> None:
    row = conn.execute("SELECT detail_json FROM ingest_batch WHERE id = ? LIMIT 1", (ingest_id,)).fetchone()
    merged: dict = {}
    if row is not None:
        raw = row["detail_json"] if isinstance(row, dict) else row[0]
        if raw:
            try:
                merged = json.loads(raw)
            except Exception:
                merged = {}
    if detail:
        merged.update(detail)
    conn.execute(
        """
        UPDATE ingest_batch
        SET status = ?, finished_at = ?, detail_json = ?
        WHERE id = ?
        """,
        (status, now_text(), json.dumps(merged, ensure_ascii=False), ingest_id),
    )
    conn.commit()


SUSPICIOUS_DELTA_CAP = 200000


def analyze_products(
    conn: sqlite3.Connection,
    tenant_id: int,
    target_id: str,
    snapshot_at: str,
    products: list[dict],
) -> dict:
    snapshot_day = snapshot_at[:10]
    prior_products = {
        row["product_id"]
        for row in conn.execute(
            """
            SELECT DISTINCT product_id
            FROM monitor_product_snapshot
            WHERE tenant_id = ? AND target_id = ?
            """,
            (tenant_id, target_id),
        ).fetchall()
    }
    history = {}
    for row in conn.execute(
        """
        SELECT product_id, AVG(daily_sales) AS avg_daily_sales
        FROM monitor_product_snapshot
        WHERE tenant_id = ? AND target_id = ?
        GROUP BY product_id
        """,
        (tenant_id, target_id),
    ).fetchall():
        history[row["product_id"]] = float(row["avg_daily_sales"] or 0)

    prior_totals: dict[str, dict] = {}
    for row in conn.execute(
        """
        SELECT p.product_id, p.total_sales, p.price, p.status, p.expired, s.snapshot_at
        FROM monitor_product_snapshot p
        JOIN monitor_snapshot s ON s.id = p.snapshot_id
        WHERE p.tenant_id = ? AND p.target_id = ?
        ORDER BY s.snapshot_at DESC
        """,
        (tenant_id, target_id),
    ).fetchall():
        pid = row["product_id"]
        if pid not in prior_totals:
            prior_totals[pid] = {
                "total_sales": int(row["total_sales"] or 0),
                "price": float(row["price"] or 0),
                "status": str(row["status"] or ""),
                "expired": int(row["expired"] or 0),
                "snapshot_at": row["snapshot_at"],
            }

    recent_launches = []
    sales_outliers = []
    signals = []
    for product in products:
        listed_at = str(product.get("listed_at") or "")
        product_id = str(product.get("product_id") or "")
        total_sales = int(product.get("total_sales") or 0)
        daily_sales = int(product.get("daily_sales") or 0)
        price = float(product.get("price") or 0)
        prior = prior_totals.get(product_id)
        if prior is None:
            if product.get("rank"):
                signals.append(("bestseller_new_entry", 1.0, json.dumps({"rank": product.get("rank")}), product_id))
        else:
            if daily_sales == 0:
                delta = total_sales - prior["total_sales"]
                if 0 <= delta <= SUSPICIOUS_DELTA_CAP:
                    daily_sales = delta
                else:
                    product["suspicious"] = 1
            old_price = prior["price"]
            if old_price and price and abs(old_price - price) > 0.001:
                signals.append(("price_change", 1.0, json.dumps({"old": old_price, "new": price}), product_id))
            if prior["expired"] and not int(product.get("expired") or 0):
                signals.append(("delist_or_relist", 1.0, json.dumps({"status": "relisted"}), product_id))
        product["daily_sales"] = daily_sales
        if is_recent_launch(snapshot_day, listed_at) and product_id not in prior_products:
            recent_launches.append(product)
        avg_daily = history.get(product_id, 0.0)
        if daily_sales >= 20 and (avg_daily <= 0 or daily_sales >= max(20, avg_daily * 1.5)):
            sales_outliers.append(product)

    current_ids = {str(p.get("product_id") or "") for p in products}
    for pid, prior in prior_totals.items():
        if pid not in current_ids and prior["status"] != "":
            signals.append(("delist_or_relist", 1.0, json.dumps({"status": "delisted"}), pid))

    return {
        "recent_launches": recent_launches,
        "sales_outliers": sales_outliers,
        "signals": signals,
    }


def is_recent_launch(snapshot_day: str, listed_at: str) -> bool:
    if not listed_at:
        return False
    try:
        listed = datetime.strptime(listed_at[:10], "%Y-%m-%d").date()
        snapshot = datetime.strptime(snapshot_day[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    return 0 <= (snapshot - listed).days <= 7


def persist_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_id: str | None = None,
    tenant_id: int,
    target_id: str,
    platform: str,
    snapshot_at: str,
    products: list[dict],
    analysis: dict,
    report_paths: dict,
) -> str:
    snapshot_id = snapshot_id or f"ms_{uuid.uuid4().hex}"
    created_at = now_text()
    conn.execute(
        """
        INSERT INTO monitor_snapshot (
          id, tenant_id, target_id, platform, snapshot_at, product_count,
          recent_launch_count, sales_outlier_count, report_md_path, report_xlsx_path, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            tenant_id,
            target_id,
            platform,
            snapshot_at,
            len(products),
            len(analysis["recent_launches"]),
            len(analysis["sales_outliers"]),
            report_paths["report_md_rel"],
            report_paths["report_xlsx_rel"],
            created_at,
        ),
    )
    for product in products:
        conn.execute(
            """
            INSERT INTO monitor_product_snapshot (
              id, tenant_id, snapshot_id, target_id, product_id, product_name,
              category, price, daily_sales, total_sales, listed_at, url,
              shop_name, shop_url, rank, price_range, sale_text, dropship_7d,
              dropship_30d, dropship_heat, rebuy_rate, shop_return_rate,
              quality_rate, shop_fans, attrs_json, is_pinned, status, expired,
              suspicious, raw_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"mps_{snapshot_id}_{product['product_id']}",
                tenant_id,
                snapshot_id,
                target_id,
                product["product_id"],
                product["product_name"],
                product.get("category", ""),
                float(product.get("price") or 0),
                int(product.get("daily_sales") or 0),
                int(product.get("total_sales") or 0),
                product.get("listed_at", ""),
                product.get("url", ""),
                product.get("shop_name", ""),
                product.get("shop_url", ""),
                int(product.get("rank") or 0),
                product.get("price_range", ""),
                product.get("sale_text", ""),
                product.get("dropship_7d", ""),
                product.get("dropship_30d", ""),
                int(product.get("dropship_heat") or 0),
                product.get("rebuy_rate", ""),
                product.get("shop_return_rate", ""),
                product.get("quality_rate", ""),
                int(product.get("shop_fans") or 0),
                product.get("attrs_json", ""),
                int(product.get("is_pinned") or 0),
                product.get("status", ""),
                int(product.get("expired") or 0),
                int(product.get("suspicious") or 0),
                product.get("raw_json", ""),
                created_at,
            ),
        )
    for signal_type, rows in (
        ("recent_launch", analysis["recent_launches"]),
        ("sales_outlier", analysis["sales_outliers"]),
    ):
        for product in rows:
            conn.execute(
                """
                INSERT INTO monitor_signal (
                  id, tenant_id, snapshot_id, target_id, product_id, signal_type, signal_score, signal_value, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"sig_{uuid.uuid4().hex}",
                    tenant_id,
                    snapshot_id,
                    target_id,
                    product["product_id"],
                    signal_type,
                    1.0,
                    str(product.get("daily_sales") or 0),
                    created_at,
                ),
            )
    for signal_type, score, value, product_id in analysis.get("signals", []):
        conn.execute(
            """
            INSERT INTO monitor_signal (
              id, tenant_id, snapshot_id, target_id, product_id, signal_type, signal_score, signal_value, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"sig_{uuid.uuid4().hex}",
                tenant_id,
                snapshot_id,
                target_id,
                product_id,
                signal_type,
                float(score or 1.0),
                str(value or ""),
                created_at,
            ),
        )
    conn.commit()
    return snapshot_id


def write_reports(
    *,
    report_root: Path,
    platform: str,
    target_id: str,
    snapshot_at: str,
    snapshot_id: str,
    target_label: str,
    products: list[dict],
    analysis: dict,
) -> dict:
    snapshot_day = snapshot_at[:10]
    report_dir = report_root / "monitor" / platform / target_id / snapshot_day / snapshot_id
    report_dir.mkdir(parents=True, exist_ok=True)
    report_md_abs = report_dir / "final.md"
    report_xlsx_abs = report_dir / "report.xlsx"
    report_md_rel = report_md_abs.as_posix()
    report_xlsx_rel = report_xlsx_abs.as_posix()

    report_md_abs.write_text(
        build_markdown_report(target_label, snapshot_at, products, analysis),
        encoding="utf-8",
    )
    build_simple_xlsx(
        report_xlsx_abs,
        {
            "Summary": [
                ["Metric", "Value"],
                ["Product Count", len(products)],
                ["Recent Launch Count", len(analysis["recent_launches"])],
                ["Sales Outlier Count", len(analysis["sales_outliers"])],
            ],
            "All Products": product_rows(products),
            "Recent Launch": product_rows(analysis["recent_launches"]),
            "Sales Outliers": product_rows(analysis["sales_outliers"]),
        },
    )
    return {
        "report_md_abs": report_md_abs,
        "report_xlsx_abs": report_xlsx_abs,
        "report_md_rel": report_md_rel,
        "report_xlsx_rel": report_xlsx_rel,
    }


def build_markdown_report(target_label: str, snapshot_at: str, products: list[dict], analysis: dict) -> str:
    lines = [
        f"# Monitor Report: {target_label}",
        "",
        f"- Snapshot At: {snapshot_at}",
        f"- Product Count: {len(products)}",
        f"- Recent Launch Count: {len(analysis['recent_launches'])}",
        f"- Sales Outlier Count: {len(analysis['sales_outliers'])}",
        "",
        "## Recent Launch",
        "",
    ]
    for product in analysis["recent_launches"]:
        lines.append(f"- {product['product_name']} | {product['product_id']} | {product.get('daily_sales', 0)}")
    lines.extend(["", "## Sales Outliers", ""])
    for product in analysis["sales_outliers"]:
        lines.append(f"- {product['product_name']} | {product['product_id']} | {product.get('daily_sales', 0)}")
    return "\n".join(lines) + "\n"


def product_rows(products: list[dict]) -> list[list]:
    rows = [["Product ID", "Product Name", "Category", "Price", "Daily Sales", "Total Sales", "Listed At", "URL"]]
    for product in products:
        rows.append(
            [
                product.get("product_id", ""),
                product.get("product_name", ""),
                product.get("category", ""),
                product.get("price", 0),
                product.get("daily_sales", 0),
                product.get("total_sales", 0),
                product.get("listed_at", ""),
                product.get("url", ""),
            ]
        )
    return rows


def build_simple_xlsx(path: Path, sheets: dict[str, list[list]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(len(sheets)))
        zf.writestr("_rels/.rels", rels_xml())
        zf.writestr("xl/workbook.xml", workbook_xml(list(sheets.keys())))
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml(len(sheets)))
        zf.writestr("xl/styles.xml", styles_xml())
        for index, (_, rows) in enumerate(sheets.items(), start=1):
            zf.writestr(f"xl/worksheets/sheet{index}.xml", worksheet_xml(rows))


def content_types_xml(sheet_count: int) -> str:
    overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for index in range(1, sheet_count + 1):
        overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(overrides)
        + "</Types>"
    )


def rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def workbook_xml(sheet_names: list[str]) -> str:
    sheets_xml = []
    for index, name in enumerate(sheet_names, start=1):
        sheets_xml.append(
            f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheets>{''.join(sheets_xml)}</sheets>"
        "</workbook>"
    )


def workbook_rels_xml(sheet_count: int) -> str:
    rels = []
    for index in range(1, sheet_count + 1):
        rels.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
    rels.append(
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )


def styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '</styleSheet>'
    )


def worksheet_xml(rows: list[list]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            cell_ref = f"{column_name(col_index)}{row_index}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )


def column_name(index: int) -> str:
    value = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        value = chr(65 + remainder) + value
    return value


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) != 0
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
