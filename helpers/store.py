"""Pixeltable-backed memory store used by the Agent Zero plugin tools.

This module has no Agent Zero imports so it can be tested on its own.
Callers must set PIXELTABLE_HOME (or pass home=) before the first
Pixeltable use if they want an isolated catalog.
"""

from __future__ import annotations

import os
import random
import re
import string
from datetime import datetime, timezone
from typing import Any

import pixeltable as pxt
from pixeltable.functions.huggingface import sentence_transformer

AREAS = ("main", "fragments", "solutions")
DEFAULT_AREA = "main"
DEFAULT_DIR = "a0_pixeltable_memory"
DEFAULT_TABLE = "memories"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_THRESHOLD = 0.7
DEFAULT_LIMIT = 10
ID_LENGTH = 10

# Same character class Agent Zero uses for memory metadata filters.
_FILTER_SAFE = re.compile(r"^[a-zA-Z0-9_\-\.\ \t'\"=<>!()\[\],:\+]+$")
_INIT_DONE = False


def generate_id(length: int = ID_LENGTH) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_timestamp(value: datetime | None = None) -> str:
    dt = value or utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def index_name_for_model(model_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", model_id).strip("_").lower()
    return f"text_{slug}"[:63]


def _normalize_match_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _metadata_references_any(value: Any, ids: set[str]) -> bool:
    if isinstance(value, dict):
        return any(_metadata_references_any(item, ids) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_metadata_references_any(item, ids) for item in value)
    text = str(value or "").strip()
    if not text:
        return False
    if text in ids:
        return True
    return any(doc_id in text.split(",") for doc_id in ids)


def matches_filter(row: dict[str, Any], condition: str) -> bool:
    """Evaluate an Agent Zero-style metadata filter against a memory row."""
    condition = (condition or "").strip()
    if not condition:
        return True
    if len(condition) > 512 or not _FILTER_SAFE.match(condition):
        return False
    names: dict[str, Any] = {}
    metadata = row.get("metadata") or {}
    if isinstance(metadata, dict):
        names.update(metadata)
    names.setdefault("area", row.get("area"))
    names.setdefault("id", row.get("id"))
    names.setdefault("timestamp", row.get("timestamp"))
    names.setdefault("agent", row.get("agent"))
    names.setdefault("memory_subdir", row.get("memory_subdir"))
    try:
        return bool(eval(condition, {"__builtins__": {}}, names))  # noqa: S307
    except Exception:
        return False


def format_docs_plain(rows: list[dict[str, Any]]) -> list[str]:
    """Match Agent Zero's Memory.format_docs_plain layout."""
    result = []
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        metadata.setdefault("id", row.get("id"))
        metadata.setdefault("area", row.get("area"))
        metadata.setdefault("timestamp", row.get("timestamp"))
        text = "".join(f"{k}: {v}\n" for k, v in metadata.items())
        text += f"Content: {row.get('text', '')}"
        result.append(text)
    return result


def ensure_pixeltable(home: str | None = None) -> None:
    """Initialize Pixeltable. Safe to call more than once in one process."""
    global _INIT_DONE
    if home:
        os.environ["PIXELTABLE_HOME"] = os.path.abspath(home)
    if not _INIT_DONE:
        pxt.init()
        _INIT_DONE = True


class PixeltableMemoryStore:
    """Persistent memories in one Pixeltable table, scoped by memory_subdir."""

    def __init__(
        self,
        *,
        home: str | None = None,
        catalog_dir: str = DEFAULT_DIR,
        table_name: str = DEFAULT_TABLE,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        memory_subdir: str = "default",
        agent: str = "",
    ):
        self.home = os.path.abspath(home) if home else os.environ.get("PIXELTABLE_HOME")
        self.catalog_dir = catalog_dir
        self.table_name = table_name
        self.embedding_model = embedding_model or DEFAULT_EMBEDDING_MODEL
        self.memory_subdir = memory_subdir or "default"
        self.agent = agent or ""
        self._table_path = f"{self.catalog_dir}.{self.table_name}"
        self._idx_name = index_name_for_model(self.embedding_model)
        ensure_pixeltable(self.home)
        self._table = self._ensure_table()

    def _ensure_table(self):
        pxt.create_dir(self.catalog_dir, if_exists="ignore")
        table = pxt.create_table(
            self._table_path,
            {
                "id": pxt.String,
                "text": pxt.String,
                "area": pxt.String,
                "metadata": pxt.Json,
                "timestamp": pxt.Timestamp,
                "agent": pxt.String,
                "memory_subdir": pxt.String,
            },
            primary_key=["id"],
            if_exists="ignore",
        )
        table.add_embedding_index(
            "text",
            idx_name=self._idx_name,
            string_embed=sentence_transformer.using(model_id=self.embedding_model),
            metric="cosine",
            if_exists="ignore",
        )
        return table

    def _unique_id(self) -> str:
        while True:
            candidate = generate_id()
            if self._table.where(self._table.id == candidate).count() == 0:
                return candidate

    def _row_from_record(self, record: dict[str, Any]) -> dict[str, Any]:
        timestamp = record.get("timestamp")
        if isinstance(timestamp, datetime):
            timestamp_out = iso_timestamp(timestamp)
        else:
            timestamp_out = str(timestamp or "")
        metadata = record.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        else:
            metadata = dict(metadata)
        metadata.setdefault("id", record.get("id"))
        metadata.setdefault("area", record.get("area"))
        metadata.setdefault("timestamp", timestamp_out)
        return {
            "id": record.get("id"),
            "text": record.get("text") or "",
            "area": record.get("area") or DEFAULT_AREA,
            "metadata": metadata,
            "timestamp": timestamp_out,
            "agent": record.get("agent") or "",
            "memory_subdir": record.get("memory_subdir") or self.memory_subdir,
            "score": record.get("score"),
        }

    def _collect(self, query) -> list[dict[str, Any]]:
        rows = query.collect()
        return [self._row_from_record(dict(row)) for row in rows]

    def _scoped(self, extra=None):
        pred = self._table.memory_subdir == self.memory_subdir
        if extra is not None:
            pred = pred & extra
        return pred

    def save(
        self,
        text: str,
        *,
        area: str = DEFAULT_AREA,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        area = (area or DEFAULT_AREA).strip() or DEFAULT_AREA
        ts = timestamp or utcnow()
        memory_id = memory_id or self._unique_id()
        meta = dict(metadata or {})
        meta["id"] = memory_id
        meta["area"] = area
        meta["timestamp"] = iso_timestamp(ts)
        self._table.insert(
            [
                {
                    "id": memory_id,
                    "text": text,
                    "area": area,
                    "metadata": meta,
                    "timestamp": ts,
                    "agent": self.agent,
                    "memory_subdir": self.memory_subdir,
                }
            ]
        )
        return memory_id

    def get(self, memory_id: str) -> dict[str, Any] | None:
        rows = self._collect(
            self._table.where(
                self._scoped(self._table.id == memory_id)
            ).select(
                self._table.id,
                self._table.text,
                self._table.area,
                self._table.metadata,
                self._table.timestamp,
                self._table.agent,
                self._table.memory_subdir,
            )
        )
        return rows[0] if rows else None

    def search(
        self,
        query: str,
        *,
        threshold: float = DEFAULT_THRESHOLD,
        limit: int = DEFAULT_LIMIT,
        filter: str = "",
        area: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        if self._table.where(self._scoped()).count() == 0:
            return []

        extra = None
        if area:
            extra = self._table.area == area
        pred = self._scoped(extra)
        sim = self._table.text.similarity(string=query, idx=self._idx_name)
        fetch_limit = max(limit, 100) if filter else limit
        raw = self._table.where(pred).order_by(sim, asc=False).limit(fetch_limit).select(
            self._table.id,
            self._table.text,
            self._table.area,
            self._table.metadata,
            self._table.timestamp,
            self._table.agent,
            self._table.memory_subdir,
            score=sim,
        )
        rows = []
        for row in raw.collect():
            record = self._row_from_record(dict(row))
            score = record.get("score")
            if score is None or float(score) < float(threshold):
                continue
            if not matches_filter(record, filter):
                continue
            rows.append(record)
            if len(rows) >= limit:
                break
        return rows

    def delete(
        self,
        ids: list[str],
        *,
        cascade: bool = True,
        filter: str = "",
    ) -> list[dict[str, Any]]:
        wanted = [item.strip() for item in ids if str(item).strip()]
        if not wanted:
            return []
        existing = self._collect(
            self._table.where(
                self._scoped(self._table.id.isin(wanted))
            ).select(
                self._table.id,
                self._table.text,
                self._table.area,
                self._table.metadata,
                self._table.timestamp,
                self._table.agent,
                self._table.memory_subdir,
            )
        )
        if filter:
            existing = [row for row in existing if matches_filter(row, filter)]
        removed = list(existing)
        removed_ids = {str(row["id"]) for row in removed}
        if cascade and removed_ids:
            related = self._related_rows(removed_ids, filter=filter)
            removed.extend(related)
            removed_ids.update(str(row["id"]) for row in related)
        if removed_ids:
            self._table.delete(
                where=self._scoped(self._table.id.isin(list(removed_ids)))
            )
        return removed

    def forget(
        self,
        query: str,
        *,
        threshold: float = DEFAULT_THRESHOLD,
        filter: str = "",
        include_exact: bool = True,
        cascade: bool = True,
    ) -> list[dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []
        matches = self.search(
            query, threshold=threshold, limit=100, filter=filter
        )
        removed_ids = {str(row["id"]) for row in matches}
        if include_exact:
            for row in self._exact_matches(query, filter=filter, skip_ids=removed_ids):
                matches.append(row)
                removed_ids.add(str(row["id"]))
        if not matches:
            return []
        return self.delete(list(removed_ids), cascade=cascade, filter=filter)

    def _exact_matches(
        self, query: str, *, filter: str, skip_ids: set[str]
    ) -> list[dict[str, Any]]:
        needle = _normalize_match_text(query)
        if len(needle) < 3:
            return []
        rows = self._collect(
            self._table.where(self._scoped()).select(
                self._table.id,
                self._table.text,
                self._table.area,
                self._table.metadata,
                self._table.timestamp,
                self._table.agent,
                self._table.memory_subdir,
            )
        )
        found = []
        for row in rows:
            if str(row["id"]) in skip_ids:
                continue
            if not matches_filter(row, filter):
                continue
            haystack = _normalize_match_text(
                f"{row.get('text', '')}\n{row.get('metadata', {})}"
            )
            if needle in haystack:
                found.append(row)
        return found

    def _related_rows(
        self, ids: set[str], *, filter: str = ""
    ) -> list[dict[str, Any]]:
        ids = {str(doc_id) for doc_id in ids if str(doc_id)}
        if not ids:
            return []
        rows = self._collect(
            self._table.where(self._scoped()).select(
                self._table.id,
                self._table.text,
                self._table.area,
                self._table.metadata,
                self._table.timestamp,
                self._table.agent,
                self._table.memory_subdir,
            )
        )
        related = []
        for row in rows:
            doc_id = str(row.get("id") or "")
            if not doc_id or doc_id in ids:
                continue
            if not matches_filter(row, filter):
                continue
            if _metadata_references_any(row.get("metadata"), ids):
                related.append(row)
        return related
