from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, Field

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
A0_ROOT = Path("/tmp/research/agent-zero")

# Copied from agent0ai/agent-zero helpers/plugins.py PluginMetadata (default branch).
class PluginMetadata(BaseModel):
    name: str = ""
    title: str = ""
    description: str = ""
    version: str = ""
    settings_sections: list[str] = Field(default_factory=list)
    per_project_config: bool = False
    per_agent_config: bool = False
    always_enabled: bool = False


def test_plugin_yaml_validates_against_agent_zero_pluginmetadata_schema():
    data = yaml.safe_load((PLUGIN_ROOT / "plugin.yaml").read_text())
    meta = PluginMetadata.model_validate(data)
    assert meta.name == "pixeltable_memory"
    assert meta.version == "0.1.0"
    assert meta.settings_sections == ["agent"]
    assert meta.per_project_config is True
    assert meta.per_agent_config is True
    assert meta.always_enabled is False


def test_agent_zero_directory_discovery_convention(tmp_path):
    dest = tmp_path / "usr" / "plugins" / "pixeltable_memory"
    dest.mkdir(parents=True)
    (dest / "plugin.yaml").write_text((PLUGIN_ROOT / "plugin.yaml").read_text())
    data = yaml.safe_load((dest / "plugin.yaml").read_text())
    assert data["name"] == dest.name
    assert (dest / "plugin.yaml").is_file()


@pytest.mark.skipif(
    not (A0_ROOT / "helpers" / "plugins.py").is_file(),
    reason="Agent Zero source is not present in this environment",
)
def test_import_plugin_store_as_usr_plugins_package(tmp_path):
    """Agent Zero loads community plugins from usr/plugins/<name>/ as usr.plugins.<name>."""
    dest = A0_ROOT / "usr" / "plugins" / "pixeltable_memory"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        PLUGIN_ROOT,
        dest,
        ignore=shutil.ignore_patterns(
            ".git", ".pytest_cache", "__pycache__", ".venv", "tests"
        ),
    )
    sys.path.insert(0, str(A0_ROOT))
    for name in list(sys.modules):
        if name == "usr" or name.startswith("usr."):
            del sys.modules[name]
    from usr.plugins.pixeltable_memory.helpers.store import (  # noqa: E402
        PixeltableMemoryStore,
    )

    assert PixeltableMemoryStore.__name__ == "PixeltableMemoryStore"
    source = (A0_ROOT / "helpers" / "plugins.py").read_text()
    assert "class PluginMetadata" in source
    assert 'META_FILE_NAME = "plugin.yaml"' in source
