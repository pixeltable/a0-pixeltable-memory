from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def test_save_search_delete_and_forget(store):
    dark_id = store.save(
        "The user prefers a dark editor theme and compact sidebars.",
        area="main",
        metadata={"topic": "ui"},
    )
    store.save(
        "Deploy the API behind Cloudflare and keep logs in Pixeltable.",
        area="main",
        metadata={"topic": "infra"},
    )
    fragment_id = store.save(
        "Earlier the user asked to try a light theme, then changed their mind.",
        area="fragments",
        metadata={"related_id": dark_id},
    )

    hits = store.search("dark mode UI preference", threshold=0.2, limit=5)
    assert hits, "semantic search should return the dark-theme memory"
    assert any(row["id"] == dark_id for row in hits)
    assert hits[0]["score"] >= 0.2
    assert hits[0]["memory_subdir"] == store.memory_subdir
    assert hits[0]["agent"] == "test-agent"

    main_only = store.search(
        "theme preference",
        threshold=0.1,
        limit=10,
        filter="area=='main'",
    )
    assert main_only
    assert all(row["area"] == "main" for row in main_only)

    deleted = store.delete([dark_id], cascade=True)
    deleted_ids = {row["id"] for row in deleted}
    assert dark_id in deleted_ids
    assert fragment_id in deleted_ids
    assert store.get(dark_id) is None
    assert store.get(fragment_id) is None

    leftover = store.search("Cloudflare logs Pixeltable", threshold=0.2, limit=5)
    assert leftover
    forgotten = store.forget("Cloudflare Pixeltable logs", threshold=0.2)
    assert forgotten
    assert store.search("Cloudflare logs Pixeltable", threshold=0.2, limit=5) == []


def test_forget_includes_exact_text_match(store):
    memory_id = store.save(
        "UNIQUE_TOKEN_PIXELTABLE_MEMORY_XYZ remembers the wifi password is stored in the vault.",
        area="main",
    )
    forgotten = store.forget("UNIQUE_TOKEN_PIXELTABLE_MEMORY_XYZ", threshold=0.99)
    assert any(row["id"] == memory_id for row in forgotten)
    assert store.get(memory_id) is None


def test_memory_subdir_isolation(pxt_home, initialized_store):
    from helpers.store import PixeltableMemoryStore

    left = PixeltableMemoryStore(
        home=str(pxt_home), memory_subdir="alpha", agent="a"
    )
    right = PixeltableMemoryStore(
        home=str(pxt_home), memory_subdir="beta", agent="b"
    )
    left_id = left.save("The office espresso machine is broken until Friday.")
    right.save("The office espresso machine was repaired this morning.")

    hits = left.search("espresso machine status", threshold=0.1, limit=10)
    assert hits
    assert all(row["memory_subdir"] == "alpha" for row in hits)
    assert any(row["id"] == left_id for row in hits)
    assert right.get(left_id) is None


def test_persistence_across_reopen(pxt_home, initialized_store):
    from helpers.store import PixeltableMemoryStore

    subdir = "persist_reopen"
    first = PixeltableMemoryStore(
        home=str(pxt_home), memory_subdir=subdir, agent="persist"
    )
    memory_id = first.save(
        "The staging database host is db.internal.example and the port is 5432."
    )
    del first

    second = PixeltableMemoryStore(
        home=str(pxt_home), memory_subdir=subdir, agent="persist"
    )
    row = second.get(memory_id)
    assert row is not None
    assert "db.internal.example" in row["text"]
    hits = second.search("staging database host port", threshold=0.2, limit=5)
    assert any(item["id"] == memory_id for item in hits)

    env = os.environ.copy()
    env["PIXELTABLE_HOME"] = str(pxt_home)
    script = f"""
import os, sys
sys.path.insert(0, {str(PLUGIN_ROOT)!r})
os.environ['PIXELTABLE_HOME'] = {str(pxt_home)!r}
from helpers.store import PixeltableMemoryStore
store = PixeltableMemoryStore(home={str(pxt_home)!r}, memory_subdir={subdir!r})
row = store.get({memory_id!r})
assert row is not None, 'row missing after subprocess reopen'
hits = store.search('staging database host', threshold=0.2, limit=5)
assert any(item['id'] == {memory_id!r} for item in hits), 'search missed persisted row'
print('reopen-ok', row['id'])
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        cwd=str(PLUGIN_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "reopen-ok" in result.stdout
