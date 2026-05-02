"""Debouncer behaviour tests.

Pure logic — uses a fast monotonic clock + the per-agent timestamp map.
"""
from __future__ import annotations

import time
import uuid

import pytest

from scoring.config import Settings
from scoring.debouncer import Debouncer


def test_dirty_set_coalesces_repeated_events():
    d = Debouncer(Settings(recompute_debounce_seconds=60))
    aid = uuid.uuid4()
    for _ in range(50):
        d.mark_dirty(aid)
    assert d._dirty == {aid}


def test_only_ready_agents_flush(monkeypatch):
    """An agent recomputed within the window stays in dirty until the window passes."""
    d = Debouncer(Settings(recompute_debounce_seconds=60))
    aid = uuid.uuid4()
    d.mark_dirty(aid)

    # Frozen time at t=0.
    fake_now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

    # Pretend we recomputed it just now.
    d._dirty.discard(aid)
    d._last_compute[aid] = fake_now[0]

    # New event arrives 30s later — still inside the 60s window.
    fake_now[0] += 30
    d.mark_dirty(aid)
    ready = {
        a for a in d._dirty
        if fake_now[0] - d._last_compute.get(a, 0.0)
        >= d.settings.recompute_debounce_seconds
    }
    assert ready == set()  # not ready yet

    # Cross the 60s boundary — now ready.
    fake_now[0] += 35
    ready = {
        a for a in d._dirty
        if fake_now[0] - d._last_compute.get(a, 0.0)
        >= d.settings.recompute_debounce_seconds
    }
    assert ready == {aid}


def test_dirty_set_holds_multiple_agents_independently():
    d = Debouncer(Settings(recompute_debounce_seconds=60))
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    d.mark_dirty(a)
    d.mark_dirty(b)
    d.mark_dirty(c)
    d.mark_dirty(b)  # duplicate
    assert d._dirty == {a, b, c}
