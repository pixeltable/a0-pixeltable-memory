# Pixeltable Memory for Agent Zero

A community plugin that stores Agent Zero memories in [Pixeltable](https://pixeltable.com) instead of the bundled FAISS index.

Memories are rows in a Pixeltable table: text, area, JSON metadata, timestamp, agent, and memory subdirectory. An embedding index on the text column is maintained as rows are inserted. Save, semantic load, delete-by-id, and forget-by-query follow Agent Zero's existing `memory` tool contract.

## Why Pixeltable

- **Persistent.** The catalog lives under `PIXELTABLE_HOME` (default `~/.pixeltable`), not a process-local FAISS file.
- **Incremental embedding index.** `add_embedding_index` keeps vectors up to date on insert; new memories are indexed without a rebuild script.
- **Queryable.** Semantic search composes with SQL-like `where` / `order_by` / `limit` filters (area, subdirectory, metadata).
- **Versioned.** Pixeltable records table history for inserts, updates, deletes, and schema changes.

## Install into Agent Zero

This repository **is** the plugin. Contents sit at the repo root (`plugin.yaml` next to `helpers/`, `tools/`, `hooks.py`).

1. In Agent Zero, open **Plugins** and install from Git using this repository URL:
   `https://github.com/pixeltable/a0-pixeltable-memory`
2. Or copy / clone the repo into `usr/plugins/pixeltable_memory` so that path contains `plugin.yaml`.
3. Agent Zero runs `hooks.py:install()` after install and after updates. That installs `pixeltable>=0.7.23` and `sentence-transformers` into the **framework** Python (`sys.executable` in Docker is `/opt/venv-a0`).
4. Restart Agent Zero if the plugin list or tools do not refresh on their own.

The plugin name is `pixeltable_memory`. Community plugins live under `usr/plugins/`; they must not use a leading underscore (that prefix is reserved for bundled plugins).

### Stand in for bundled FAISS memory

Agent Zero discovers tools by filename. `agent.get_tool("memory")` walks `subagents.get_paths(..., "tools", "memory.py")` and loads the **first** match. User plugins are searched before bundled plugins, so this plugin's `tools/memory.py` is used instead of `plugins/_memory/tools/memory.py` while this plugin is enabled.

The same first-file-wins rule applies to `prompts/agent.system.tool.memory.md` and the legacy `memory_save` / `memory_load` / `memory_delete` / `memory_forget` aliases.

Disable the bundled **Memory** (`_memory`) plugin if you want Pixeltable as the only memory store. If `_memory` stays enabled, its auto-recall / auto-memorize extensions still write to FAISS, while the `memory` **tool** uses Pixeltable.

### Sit beside bundled memory

Leave `_memory` enabled if you still want FAISS auto-recall. Understand that the `memory` tool itself is then this plugin, not FAISS. There is no separate tool name in v0.1.0.

## Configuration

Settings appear under the Agent tab (`settings_sections: [agent]`). Defaults are in `default_config.yaml`.

| Key | Default | Meaning |
| --- | --- | --- |
| `embedding_model` | `all-MiniLM-L6-v2` | Local sentence-transformers model for the embedding index |
| `default_threshold` | `0.7` | Cosine similarity used when load/forget omit `threshold` |
| `default_limit` | `10` | Load result cap when `limit` is omitted |
| `project_memory_isolation` | `true` | Project chats use `memory_subdir=projects/<name>` |
| `agent_memory_subdir` | `default` | Subdirectory when project isolation does not apply |
| `pixeltable_dir` | `a0_pixeltable_memory` | Pixeltable catalog directory (`pxt.create_dir`) |
| `pixeltable_home` | empty | Optional `PIXELTABLE_HOME`. Empty uses Pixeltable's default |

Changing `embedding_model` after data exists adds a new index name derived from the model id; existing rows are indexed with the new function. Leave `pixeltable_home` stable once you have memories.

## Memory areas

These match Agent Zero's bundled `Memory.Area` values:

| Area | Typical content |
| --- | --- |
| `main` | Durable facts, preferences, project constraints |
| `fragments` | Conversation fragments the bundled plugin would memorize |
| `solutions` | Successful approaches / solutions |

`save` stores `area` (default `main`) as a column and inside metadata JSON, together with `id`, ISO timestamp, optional extra kwargs, `agent`, and `memory_subdir`.

`load` / `forget` accept the same arguments as Agent Zero:

- `query` — semantic search text
- `threshold` — similarity in `[0, 1]`
- `limit` — max rows (`load` only)
- `filter` — metadata expression such as `area=='main'`
- `ids` — comma-separated ids (`delete`)
- `text`, `area`, extra kwargs (`save`)

`forget` removes semantic matches, exact normalized-text matches, and related rows whose metadata references a removed id (the bundled cascade behavior).

## Tool interface

```json
{
  "tool_name": "memory",
  "tool_args": {
    "action": "load",
    "query": "preferred editor theme",
    "threshold": 0.7,
    "limit": 3
  }
}
```

Actions: `load`, `save`, `delete`, `forget`. Legacy tool names (`memory_load`, `memory_save`, `memory_delete`, `memory_forget`) still force that action.

## Development

```bash
python -m pip install -r requirements.txt pytest pyyaml
pytest
```

Tests create an isolated `PIXELTABLE_HOME`, write real Pixeltable rows, and exercise save, semantic search, delete, forget, subdirectory isolation, and persistence across a new store handle and a subprocess reopen. The first run downloads `all-MiniLM-L6-v2`.

## Uninstall

Disable or remove the plugin in Agent Zero. `hooks.py:uninstall()` does not delete Pixeltable or `PIXELTABLE_HOME`; that catalog may hold other data. Remove the `a0_pixeltable_memory` directory inside Pixeltable yourself if you want the memories gone.

## License

Apache-2.0. See [LICENSE](LICENSE).
