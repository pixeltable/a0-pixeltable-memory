import uuid

from helpers.strings import truncate_text
from helpers.tool import Response, Tool
from usr.plugins.pixeltable_memory.helpers.runtime import (
    extra_metadata,
    plugin_config,
    store_for_agent,
)
from usr.plugins.pixeltable_memory.helpers.store import (
    DEFAULT_AREA,
    DEFAULT_LIMIT,
    DEFAULT_THRESHOLD,
    format_docs_plain,
)


class MemoryTool(Tool):
    """Pixeltable-backed memory tool using Agent Zero's action contract."""

    async def execute(self, action="", **kwargs) -> Response:
        action = self._action(action)
        if action == "load":
            return await self._load(**kwargs)
        if action == "save":
            return await self._save(**kwargs)
        if action == "delete":
            return await self._delete(**kwargs)
        if action == "forget":
            return await self._forget(**kwargs)
        return Response(
            message=self.agent.read_prompt("fw.memory.invalid_action.md"),
            break_loop=False,
        )

    async def _load(
        self,
        query="",
        threshold=None,
        limit=None,
        filter="",
        **kwargs,
    ) -> Response:
        config = plugin_config(self.agent)
        if threshold is None or threshold == "":
            threshold = config.get("default_threshold", DEFAULT_THRESHOLD)
        if limit is None or limit == "":
            limit = config.get("default_limit", DEFAULT_LIMIT)
        threshold = float(threshold)
        limit = int(limit)

        db = store_for_agent(self.agent)
        docs = db.search(
            query=query, limit=limit, threshold=threshold, filter=filter
        )

        if not docs:
            result = self.agent.read_prompt("fw.memories_not_found.md", query=query)
        else:
            result = "\n\n".join(format_docs_plain(docs))
        return Response(message=result, break_loop=False)

    async def _save(self, text="", area="", **kwargs) -> Response:
        if not area:
            area = DEFAULT_AREA
        db = store_for_agent(self.agent)
        memory_id = db.save(text, area=area, metadata=extra_metadata(kwargs))
        result = self.agent.read_prompt("fw.memory_saved.md", memory_id=memory_id)
        return Response(message=result, break_loop=False)

    async def _delete(self, ids="", **kwargs) -> Response:
        db = store_for_agent(self.agent)
        id_list = [item.strip() for item in str(ids).split(",") if item.strip()]
        deleted = db.delete(ids=id_list, cascade=True)
        result = self.agent.read_prompt(
            "fw.memories_deleted.md", memory_count=len(deleted)
        )
        return Response(message=result, break_loop=False)

    async def _forget(
        self, query="", threshold=None, filter="", **kwargs
    ) -> Response:
        config = plugin_config(self.agent)
        if threshold is None or threshold == "":
            threshold = config.get("default_threshold", DEFAULT_THRESHOLD)
        db = store_for_agent(self.agent)
        deleted = db.forget(
            query=query,
            threshold=float(threshold),
            filter=filter,
            include_exact=True,
            cascade=True,
        )
        result = self.agent.read_prompt(
            "fw.memories_deleted.md", memory_count=len(deleted)
        )
        return Response(message=result, break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="memory",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        action = self._action(self.args.get("action"))
        if action == "save":
            detail = str(self.args.get("text") or "").strip()
            text = (
                f"Saving memory: {truncate_text(detail, 60)}"
                if detail
                else "Saving memory"
            )
            return f"icon://bookmark_add {text}"
        if action == "delete":
            detail = str(self.args.get("ids") or "").strip()
            text = (
                f"Deleting memories: {truncate_text(detail, 60)}"
                if detail
                else "Deleting memories"
            )
            return f"icon://delete {text}"
        if action == "forget":
            detail = str(self.args.get("query") or "").strip()
            text = (
                f"Forgetting memories: {truncate_text(detail, 60)}"
                if detail
                else "Forgetting memories"
            )
            return f"icon://auto_delete {text}"
        if action == "load":
            detail = str(self.args.get("query") or "").strip()
            text = (
                f"Searching memories: {truncate_text(detail, 60)}"
                if detail
                else "Searching memories"
            )
            return f"icon://saved_search {text}"
        return "icon://psychology Using memory"

    def _action(self, action) -> str:
        if self.name in {
            "memory_load",
            "memory_save",
            "memory_delete",
            "memory_forget",
        }:
            return self.name.removeprefix("memory_")
        return str(action or "").strip().lower().replace("-", "_")
