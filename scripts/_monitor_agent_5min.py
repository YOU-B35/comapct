"""Monitor CrossHub agent for up to 5 minutes; kill if stuck."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "backend" / "data" / "crosshub.db"
DOWNLOADS = ROOT / "backend" / "data" / "amazon-downloads"
MAX_SECONDS = 300
POLL_SECONDS = 15
STUCK_RUNNING_SECONDS = 180


def agent_pids() -> list[int]:
    out = subprocess.check_output(
        ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine"],
        text=True,
        errors="ignore",
    )
    pids: list[int] = []
    for line in out.splitlines():
        if "run_agent.py" not in line:
            continue
        parts = line.strip().split()
        if parts and parts[-1].isdigit():
            pids.append(int(parts[-1]))
    return pids


def kill_agents() -> None:
    for pid in agent_pids():
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False, capture_output=True)
            print(f"[kill] agent pid={pid}")
        except Exception as exc:
            print(f"[kill-fail] pid={pid} {exc}")


def snapshot() -> dict:
    conn = sqlite3.connect(DB)
    hb = conn.execute(
        """
        SELECT tenant_id, last_heartbeat_at, ziniao_online
        FROM integration_agent
        WHERE agent_token=?
        """,
        (os.environ.get("AGENT_TOKEN", ""),),
    ).fetchone()
    task = conn.execute(
        """
        SELECT id, status, task_type, created_at, started_at, finished_at, error_message
        FROM agent_task
        WHERE task_type='amazon_sync'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    job = conn.execute(
        """
        SELECT id, scope, status, created_at, finished_at, error_message
        FROM amazon_sync_job
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    csv_files = sorted(DOWNLOADS.glob("**/*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "heartbeat": hb,
        "task": task,
        "job": job,
        "csv_count": len(csv_files),
        "csv_latest": str(csv_files[0]) if csv_files else "",
        "agent_pids": agent_pids(),
    }


def parse_ts(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return None


def main() -> int:
    started = time.time()
    last_running_since: float | None = None
    last_csv_count = 0
    print(f"==> monitor agent up to {MAX_SECONDS}s, poll every {POLL_SECONDS}s")

    while True:
        elapsed = time.time() - started
        snap = snapshot()
        hb = snap["heartbeat"]
        task = snap["task"]
        job = snap["job"]
        pids = snap["agent_pids"]

        print(
            f"[{int(elapsed):03d}s] agents={pids} hb={hb[1] if hb else None} "
            f"ziniao={hb[2] if hb else None} task={task[1] if task else None} "
            f"job={job[2] if job else None} csv={snap['csv_count']}"
        )

        if not pids:
            print("[stop] no agent process")
            return 2

        if hb and hb[1]:
            hb_age = time.time() - (parse_ts(hb[1]) or time.time())
            if hb_age > 90:
                print(f"[stuck] heartbeat stale {int(hb_age)}s -> kill")
                kill_agents()
                return 3

        if task and task[1] == "running":
            run_since = parse_ts(task[4]) or parse_ts(task[3]) or time.time()
            if last_running_since is None:
                last_running_since = run_since
            running_for = time.time() - last_running_since
            if running_for >= STUCK_RUNNING_SECONDS and snap["csv_count"] <= last_csv_count:
                print(f"[stuck] amazon_sync running {int(running_for)}s, no new csv -> kill")
                kill_agents()
                return 4
        else:
            last_running_since = None

        if task and task[1] in ("success", "failed"):
            print(f"[done] latest task {task[0]} status={task[1]} err={task[6] or ''}")
            if snap["csv_latest"]:
                print(f"[done] csv: {snap['csv_latest']}")
            return 0 if task[1] == "success" else 1

        if snap["csv_count"] > last_csv_count:
            last_csv_count = snap["csv_count"]
            print(f"[progress] new csv -> {snap['csv_latest']}")

        if elapsed >= MAX_SECONDS:
            print("[timeout] 5 minutes reached -> kill")
            kill_agents()
            return 5

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
