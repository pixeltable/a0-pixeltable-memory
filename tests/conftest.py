from __future__ import annotations

import os
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def pxt_home(tmp_path_factory) -> Path:
    home = tmp_path_factory.mktemp("pixeltable-home")
    os.environ["PIXELTABLE_HOME"] = str(home)
    return home


@pytest.fixture(scope="session")
def initialized_store(pxt_home):
    from helpers.store import PixeltableMemoryStore

    return PixeltableMemoryStore(
        home=str(pxt_home),
        memory_subdir="__session_init__",
        agent="test",
    )


@pytest.fixture
def store(pxt_home, initialized_store, request):
    from helpers.store import PixeltableMemoryStore

    subdir = request.node.name
    return PixeltableMemoryStore(
        home=str(pxt_home),
        memory_subdir=subdir,
        agent="test-agent",
    )
