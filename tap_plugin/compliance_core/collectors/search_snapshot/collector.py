"""The abstract Search snapshot collector (`req-compliance-core-search-snapshot-collector`).

A plugin that wants a Search recorded on a schedule writes a subclass of a few lines, registers it, and seeds a
`Schedule` for it. The subclass names the Searches by entity id, because a collector's configuration is two ids and
nothing else, each registry key has one `Collector` node and the registry takes classes, never factories::

    class CoverageSnapshotCollector(SearchSnapshotCollector):
        SOURCE = "fedramp_20x_vdr"
        SEARCH_ENTITY_IDS = ("01a15b2f-df3b-7569-bf22-9ead3f816b84",)

The base class does the work: resolve every Search before running any, run each through the search service so the
Search's input defaults apply, build one `compliance_search_snapshot` per Search and submit one GRIFT batch. It reads
the grid and calls no outside service, so it needs no credential and no call ceiling. It registers nothing, reads no
earlier snapshot and keeps no state between runs: an unchanged figure is written again at a new time, because the flat
stretch is the point of a series.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from tap_cares.collectors import CollectorBase
from tap_grid.models import Search
from tap_grid.search import execute_search
from tap_grid.services import get_node

SNAPSHOT_TYPE = "compliance_core__compliance_search_snapshot"
CAPTURES_EDGE = "CAPTURES_SEARCH__compliance_core"
BATCH_SOURCE = "plugins.compliance_core.collectors.search_snapshot"
MAX_ROWS = 1000
MAX_PROPERTIES = 50
MAX_NAME = 128
MAX_STRING = 4096
MAX_DISPLAY = 255

_SITE_RUN_STARTED = "4992"
_SITE_BAD_SEARCH = "8e68"
_SITE_NOT_ROWS = "8ee6"
_SITE_ROW_SHAPE = "db9d"
_SITE_CONVERTED = "2652"
_SITE_SUBMITTED = "0609"


class SearchSnapshotError(RuntimeError):
    """A Search could not be snapshotted; the run stops and nothing is submitted."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _utc_text(moment: datetime) -> str:
    """UTC ISO 8601 to the microsecond: the form a snapshot key and `observed_at` both use."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _display_name(search_name: str, when: str) -> str:
    """`<search name> @ <time>` within the model's 255 characters: the Search's name gives way, the time never does."""
    suffix = f" @ {when}"
    return f"{search_name[: MAX_DISPLAY - len(suffix)]}{suffix}"


def _scalar(value: Any) -> tuple[Any, bool]:
    """``(value, changed)``: a list or object becomes its canonical JSON text, a long string is cut."""
    if value is None or isinstance(value, bool | int | float):
        return value, False
    if isinstance(value, str):
        return (value, False) if len(value) <= MAX_STRING else (value[:MAX_STRING], True)
    text = _canonical(value)
    return (text[:MAX_STRING], True)


class SearchSnapshotCollector(CollectorBase):
    """Records one `compliance_search_snapshot` per Search each run. Abstract: a subclass sets two attributes."""

    #: The plugin slug of the subclass, 1 to 64 characters; written to every snapshot's `source`.
    SOURCE: ClassVar[str] = ""
    #: The Searches to run, by entity id (UUID strings). A Search is keyless, so a name could match two.
    SEARCH_ENTITY_IDS: ClassVar[tuple[str, ...]] = ()
    #: The most rows kept per snapshot. A subclass may lower it; it never exceeds the model's limit.
    MAX_ROWS: ClassVar[int] = MAX_ROWS

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not isinstance(cls.SOURCE, str) or not 1 <= len(cls.SOURCE) <= 64:
            raise TypeError(f"{cls.__name__}.SOURCE must be a plugin slug of 1 to 64 characters")
        ids = cls.SEARCH_ENTITY_IDS
        if not isinstance(ids, tuple) or not ids:
            raise TypeError(f"{cls.__name__}.SEARCH_ENTITY_IDS must be a non-empty tuple of UUID strings")
        if len(set(ids)) != len(ids):
            raise TypeError(f"{cls.__name__}.SEARCH_ENTITY_IDS names a Search twice, which would write one key twice")
        for item in ids:
            try:
                uuid.UUID(item)
            except (ValueError, AttributeError, TypeError):
                raise TypeError(f"{cls.__name__}.SEARCH_ENTITY_IDS holds {item!r}, which is not a UUID string") from None
        if not isinstance(cls.MAX_ROWS, int) or isinstance(cls.MAX_ROWS, bool) or not 1 <= cls.MAX_ROWS <= MAX_ROWS:
            raise TypeError(f"{cls.__name__}.MAX_ROWS must be an integer from 1 to {MAX_ROWS}")

    def run(self) -> None:
        self.record_info(
            _SITE_RUN_STARTED,
            "RUN_STARTED",
            f"Snapshotting {len(self.SEARCH_ENTITY_IDS)} Search(es) for {self.SOURCE}.",
        )
        # The run reads the grid, not a listing surface in a source system, so it claims no completeness.
        self.declare_no_surfaces()
        observed_at = datetime.now(UTC)  # taken once: every snapshot of this run shares it

        searches = [self._resolve(search_id) for search_id in self.SEARCH_ENTITY_IDS]  # all, before any runs
        converted = 0
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for index, (search_id, search) in enumerate(searches):
            rows = self._rows(search_id, search)
            kept: list[dict[str, Any]] = []
            for row in rows[: self.MAX_ROWS]:
                clean, count = self._clean_row(search_id, row)
                converted += count
                kept.append(clean)
            when = _utc_text(observed_at)
            ref = f"snapshot-{index}"
            nodes.append(
                {
                    "entity": {
                        "ref": ref,
                        "entity_type": SNAPSHOT_TYPE,
                        "name": _display_name(search.name, when),
                        "dimensions": {"compliance": "search-snapshot"},
                    },
                    "node": {
                        "name": _display_name(search.name, when),
                        "source": self.SOURCE,
                        "snapshot_key": f"{search_id}@{when}",
                        "search_name": search.name,
                        "observed_at": when,
                        "row_count": len(rows),
                        "rows": kept,
                        "truncated": len(kept) < len(rows),
                        "inputs_text": _canonical(self._defaults(search)),
                    },
                }
            )
            edges.append(
                {
                    "entity": {
                        "ref": f"captures-{index}",
                        "entity_type": "edge",
                        "name": CAPTURES_EDGE,
                        "dimensions": {"compliance": "search-snapshot"},
                    },
                    "edge": {
                        "from_ref": ref,
                        "to_entity_id": search_id,
                        "edge_type": CAPTURES_EDGE,
                        "properties": {},
                    },
                }
            )
        if converted:
            self.record_warn(
                _SITE_CONVERTED,
                "VALUES_CONVERTED",
                f"{converted} value(s) were converted to text or cut to {MAX_STRING} characters so the rows stay scalar.",
                message_data={"count": converted},
            )
        self.submit_grift(self._document(nodes, edges))
        parts = [f"{len(n['node']['rows'])} of {n['node']['row_count']} rows" for n in nodes]
        self.summary = f"Snapshot {len(nodes)} search(es): {'; '.join(parts)}."
        self.record_info(
            _SITE_SUBMITTED,
            "SNAPSHOT_SUBMITTED",
            self.summary,
            message_data={"searches": len(nodes), "rows": sum(len(n["node"]["rows"]) for n in nodes)},
        )

    def _resolve(self, search_id: str) -> tuple[str, Search]:
        """The Search node for an id, or an error naming the id: nothing runs and nothing is submitted."""
        try:
            node = get_node(search_id)
        except Exception as exc:  # the service layer's not-found, constraint and validation errors alike
            self.record_error(
                _SITE_BAD_SEARCH,
                "SEARCH_NOT_FOUND",
                f"Search {search_id} was not found on the grid; nothing was snapshotted.",
                message_data={"search_entity_id": search_id, "error": type(exc).__name__},
            )
            raise SearchSnapshotError(f"Search {search_id} was not found.") from exc
        if not isinstance(node, Search):
            self.record_error(
                _SITE_BAD_SEARCH,
                "NOT_A_SEARCH",
                f"{search_id} is a {type(node).ENTITY_TYPE}, not a search; nothing was snapshotted.",
                message_data={"search_entity_id": search_id, "entity_type": type(node).ENTITY_TYPE},
            )
            raise SearchSnapshotError(f"{search_id} is not a search.")
        return search_id, node

    def _rows(self, search_id: str, search: Search) -> list[dict[str, Any]]:
        """Run the Search through the search service (its input defaults apply) and take its rows."""
        envelope = execute_search(search)  # a Search that raises fails the run: the exception propagates
        rows = envelope.get("rows")
        if rows is None:
            if envelope.get("nodes") or envelope.get("edges"):
                self.record_error(
                    _SITE_NOT_ROWS,
                    "NOT_ROW_SHAPED",
                    f"Search {search_id} returns a graph, not rows, which v0 cannot snapshot.",
                    message_data={"search_entity_id": search_id},
                )
                raise SearchSnapshotError(f"Search {search_id} returns a graph, not rows.")
            return []  # the bare empty envelope is an answer: zero rows
        if not isinstance(rows, list):
            self.record_error(
                _SITE_NOT_ROWS,
                "NOT_ROW_SHAPED",
                f"Search {search_id} returned rows that are not a list.",
                message_data={"search_entity_id": search_id},
            )
            raise SearchSnapshotError(f"Search {search_id} returned rows that are not a list.")
        return rows

    def _clean_row(self, search_id: str, row: Any) -> tuple[dict[str, Any], int]:
        """One row made scalar-valued; the count of values converted or cut."""
        if not isinstance(row, dict) or len(row) > MAX_PROPERTIES or any(
            not isinstance(key, str) or len(key) > MAX_NAME for key in row
        ):
            self.record_error(
                _SITE_ROW_SHAPE,
                "ROW_SHAPE",
                f"Search {search_id} returned a row that is not an object of at most {MAX_PROPERTIES} properties "
                f"with names of at most {MAX_NAME} characters; flatten the Search's columns.",
                message_data={"search_entity_id": search_id},
            )
            raise SearchSnapshotError(f"Search {search_id} returned a row the snapshot cannot hold.")
        clean: dict[str, Any] = {}
        changed = 0
        for key, value in row.items():
            clean[key], did = _scalar(value)
            changed += int(did)
        return clean, changed

    @staticmethod
    def _defaults(search: Search) -> dict[str, Any]:
        """The default of each property in the Search's input schema that declares one: what the run used."""
        schema = search.input_schema if isinstance(search.input_schema, dict) else {}
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return {}
        return {name: spec["default"] for name, spec in properties.items() if isinstance(spec, dict) and "default" in spec}

    def _document(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
        title = f"Search snapshots for {self.SOURCE} ({len(nodes)})"
        return {
            "metadata": {"grift_version": "0"},
            "_reserved": {},
            "batches": [
                {
                    "batch_entity": {
                        "entity_id": str(uuid.uuid4()),
                        "entity_type": "batch",
                        "name": title,
                        "dimensions": {},
                    },
                    "batch_node": {
                        "source": BATCH_SOURCE,
                        "name": title,
                        "description": "One compliance_search_snapshot per Search run, each with the edge naming the Search.",
                        "description_json": {
                            "format": "tap.compliance_core.search-snapshot-v0",
                            "data": {"source": self.SOURCE, "searches": [n["node"]["snapshot_key"] for n in nodes]},
                        },
                    },
                    "nodes": nodes,
                    "edges": edges,
                }
            ],
        }
