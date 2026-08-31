"""Tests for the file-backed TTL cache component."""
from __future__ import annotations

from pathlib import Path

from app.cache_store import CacheStore


def test_get_missing_returns_none(tmp_path: Path):
    store = CacheStore(tmp_path / "cache.json")
    assert store.get("ns", "missing") is None


def test_set_get_roundtrip_preserves_value(tmp_path: Path):
    store = CacheStore(tmp_path / "cache.json")
    store.set("ns", "k", {"title": "demo", "n": 42})
    assert store.get("ns", "k") == {"title": "demo", "n": 42}


def test_expired_entry_returns_none(tmp_path: Path):
    clock = {"t": 1000.0}
    store = CacheStore(tmp_path / "cache.json", default_ttl=100, now=lambda: clock["t"])
    store.set("ns", "k", "v")
    assert store.get("ns", "k") == "v"
    clock["t"] = 1000.0 + 101
    assert store.get("ns", "k") is None


def test_namespaces_are_isolated(tmp_path: Path):
    store = CacheStore(tmp_path / "cache.json")
    store.set("tenant_a", "k", "a")
    store.set("tenant_b", "k", "b")
    assert store.get("tenant_a", "k") == "a"
    assert store.get("tenant_b", "k") == "b"


def test_custom_ttl_overrides_default(tmp_path: Path):
    clock = {"t": 0.0}
    store = CacheStore(tmp_path / "cache.json", default_ttl=1000, now=lambda: clock["t"])
    store.set("ns", "k", "v", ttl_seconds=10)
    clock["t"] = 20.0
    assert store.get("ns", "k") is None


def test_invalidate_removes_entry(tmp_path: Path):
    store = CacheStore(tmp_path / "cache.json")
    store.set("ns", "k", "v")
    store.invalidate("ns", "k")
    assert store.get("ns", "k") is None


def test_persists_across_instances(tmp_path: Path):
    path = tmp_path / "cache.json"
    CacheStore(path).set("ns", "k", {"kept": True})
    assert CacheStore(path).get("ns", "k") == {"kept": True}
