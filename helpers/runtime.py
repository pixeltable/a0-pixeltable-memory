"""Agent Zero glue: plugin config, memory subdir, and store construction."""

from __future__ import annotations

from typing import Any

PLUGIN_NAME = "pixeltable_memory"

RESERVED_SAVE_KEYS = {
    "action",
    "text",
    "area",
    "query",
    "ids",
    "threshold",
    "limit",
    "filter",
}


def plugin_config(agent=None) -> dict[str, Any]:
    from helpers.plugins import get_plugin_config

    return get_plugin_config(PLUGIN_NAME, agent=agent) or {}


def memory_subdir_for_agent(agent) -> str:
    from helpers import projects

    config = plugin_config(agent)
    if config.get("project_memory_isolation", True) and agent is not None:
        project_name = projects.get_context_project_name(agent.context)
        if project_name:
            return "projects/" + project_name
    return config.get("agent_memory_subdir", "") or "default"


def agent_name(agent) -> str:
    if agent is None:
        return ""
    return str(getattr(agent, "agent_name", "") or getattr(agent, "name", "") or "")


def store_for_agent(agent):
    from .store import PixeltableMemoryStore

    config = plugin_config(agent)
    home = (config.get("pixeltable_home") or "").strip() or None
    return PixeltableMemoryStore(
        home=home,
        catalog_dir=config.get("pixeltable_dir") or "a0_pixeltable_memory",
        embedding_model=config.get("embedding_model") or "all-MiniLM-L6-v2",
        memory_subdir=memory_subdir_for_agent(agent),
        agent=agent_name(agent),
    )


def extra_metadata(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if key not in RESERVED_SAVE_KEYS}
