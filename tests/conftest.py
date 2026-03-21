"""Test-wide hooks: ensure SQLite engines from GraphStore are disposed to avoid ResourceWarning."""

from __future__ import annotations

import gc

import pytest

from converge.graph.store import GraphStore


@pytest.fixture(autouse=True)
def _dispose_graph_stores_after_test() -> None:
    yield
    GraphStore.close_all_open()
    gc.collect()
