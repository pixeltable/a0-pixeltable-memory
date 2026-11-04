from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9_]+$")
ALLOWED_SECTIONS = {"agent", "external", "mcp", "developer", "backup"}
KNOWN_FIELDS = {
    "name",
    "title",
    "description",
    "version",
    "settings_sections",
    "per_project_config",
    "per_agent_config",
    "always_enabled",
}


def test_plugin_yaml_matches_agent_zero_runtime_schema():
    data = yaml.safe_load((ROOT / "plugin.yaml").read_text())
    assert isinstance(data, dict)
    assert data["name"] == "pixeltable_memory"
    assert NAME_RE.fullmatch(data["name"])
    assert data["title"]
    assert data["description"]
    assert data["version"] == "0.1.0"
    assert isinstance(data["settings_sections"], list)
    assert set(data["settings_sections"]) <= ALLOWED_SECTIONS
    assert data["per_project_config"] is True
    assert data["per_agent_config"] is True
    assert data["always_enabled"] is False
    assert set(data) <= KNOWN_FIELDS


def test_community_layout_has_required_root_files():
    for name in (
        "plugin.yaml",
        "README.md",
        "LICENSE",
        "hooks.py",
        "default_config.yaml",
        "requirements.txt",
        "tools/memory.py",
        "helpers/store.py",
    ):
        assert (ROOT / name).is_file(), name


def test_requirements_pin_pixeltable():
    text = (ROOT / "requirements.txt").read_text()
    assert "pixeltable>=0.7.23" in text
