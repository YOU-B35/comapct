"""Tests for the fine-grained browser lock pool used by agent dispatch."""
from __future__ import annotations

import threading
import time

from agent.browser_lock_pool import (
    BrowserLockPool,
    browser_lock_key,
    task_browser_keys,
)


def _run_tasks(pool, platform, keys, limit):
    state = {"active": 0, "peak": 0, "entered": 0}
    state_lock = threading.Lock()

    def work(key: str) -> None:
        with pool.guard(platform, key):
            with state_lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.04)
            with state_lock:
                state["active"] -= 1

    threads = [threading.Thread(target=work, args=(key,)) for key in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive(), "worker thread did not finish in time"
    return state["peak"]


def test_different_keys_run_in_parallel_within_platform_limit():
    pool = BrowserLockPool({"temu": 2})
    peak = _run_tasks(pool, "temu", ["tenant1:sess_a", "tenant1:sess_b"], limit=2)
    assert peak >= 2


def test_same_key_is_serialized():
    pool = BrowserLockPool({"temu": 2})
    peak = _run_tasks(pool, "temu", ["tenant1:sess_a", "tenant1:sess_a"], limit=2)
    assert peak <= 1


def test_platform_limit_caps_concurrent_distinct_keys():
    pool = BrowserLockPool({"douyin": 1})
    keys = ["tenant1:store1", "tenant1:store2", "tenant1:store3"]
    peak = _run_tasks(pool, "douyin", keys, limit=1)
    assert peak >= 3


def test_pool_guard_is_reentrant_on_same_thread():
    pool = BrowserLockPool({"temu": 1})
    with pool.guard("temu", "tenant1:sess_a"):
        with pool.guard("temu", "tenant1:sess_a"):
            assert True


def test_browser_lock_key_normalizes_identity():
    assert browser_lock_key("temu", 1, None) == "temu:1:default"
    assert browser_lock_key("douyin", 5, "store-7") == "douyin:5:store-7"


def test_task_browser_keys_single_session_and_multi_session():
    task = {
        "task_type": "temu_crawl",
        "payload": {
            "tenant_id": 5,
            "session_key": "acct_a",
        },
    }
    assert browser_lock_key("temu", 5, "acct_a") in task_browser_keys("temu", task)

    multi = {
        "task_type": "temu_crawl",
        "payload": {
            "tenant_id": 6,
            "seller_sessions": [
                {"session_key": "s1"},
                {"session_key": "s2"},
            ],
        },
    }
    keys = task_browser_keys("temu", multi)
    assert browser_lock_key("temu", 6, "s1") in keys
    assert browser_lock_key("temu", 6, "s2") in keys


def test_amazon_cli_store_id_is_used_as_browser_lock_identity():
    task = {
        "task_type": "amazon_sync",
        "payload": {"tenant_id": 7, "browser_id": "webdriver-1", "ziniao_store_id": "cli-store-1"},
    }
    assert task_browser_keys("amazon", task) == [browser_lock_key("amazon", 7, "cli-store-1")]


def test_douyin_and_1688_task_key_uses_store_id():
    douyin = {
        "task_type": "douyin_sync",
        "payload": {"tenant_id": 8, "store_id": "store_x"},
    }
    assert browser_lock_key("douyin", 8, "store_x") in task_browser_keys("douyin", douyin)

    a1688 = {
        "task_type": "1688_products_sync",
        "payload": {"tenant_id": 9, "store_id": "store_y"},
    }
    assert browser_lock_key("1688", 9, "store_y") in task_browser_keys("1688", a1688)


def test_same_account_different_stores_get_distinct_keys():
    store_a = {
        "task_type": "douyin_login_open",
        "payload": {
            "tenant_id": 10,
            "platform_account_id": "acct_1",
            "store_id": "store_a",
        },
    }
    store_b = {
        "task_type": "douyin_login_open",
        "payload": {
            "tenant_id": 10,
            "platform_account_id": "acct_1",
            "store_id": "store_b",
        },
    }
    keys_a = task_browser_keys("douyin", store_a)
    keys_b = task_browser_keys("douyin", store_b)
    assert browser_lock_key("douyin", 10, "acct_1", "store_a") in keys_a
    assert browser_lock_key("douyin", 10, "acct_1", "store_b") in keys_b
    assert keys_a != keys_b


def test_same_account_same_store_keeps_single_key():
    task = {
        "task_type": "douyin_login_open",
        "payload": {
            "tenant_id": 11,
            "platform_account_id": "acct_1",
            "store_id": "store_a",
        },
    }
    assert task_browser_keys("douyin", task) == [
        browser_lock_key("douyin", 11, "acct_1", "store_a")
    ]
