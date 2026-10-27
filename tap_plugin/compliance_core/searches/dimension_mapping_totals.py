"""Live totals of a grouped mapping summary, as a `module` Search runner (`req-compliance-core-dimension-mapping-totals`).

A coverage card shows a few figures about a whole summary: how covered the groups are on average, and how many entries are
mapped, unmapped and mapped incorrectly. This runs the summary Search it is pointed at, live, and returns one row of totals.
The mapping is stated once, in the summary Search: this reads that Search's own ``input_schema`` defaults (``mappings``,
``group_by``, ``exclude_groups``) and holds none of its own, so the totals can never differ from the summary. The arithmetic
is ``coverage.totals_from_rows``, the one place a coverage average is computed. Reads use the read rules Gryphon applies
(``tap_grid.gryphon.read_scope``, the caller's ``db_alias``); it writes nothing and reads no snapshot.

Input: ``summary_search_id``, required, the entity id of a ``search`` node whose runner is ``dimension-mapping-summary``.
"""

from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ValidationError

from tap_grid.gryphon import read_scope
from tap_grid.models import Search

from ..coverage import totals_from_rows
from .dimension_mapping import dimension_mapping_summary

SUMMARY_RUNNER = "tap_plugin.compliance_core.searches.dimension_mapping:dimension-mapping-summary"
_SUMMARY_INPUTS = ("mappings", "group_by", "exclude_groups")
_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def _summary_search(summary_search_id: Any, *, db_alias: str) -> Any:
    if not isinstance(summary_search_id, str) or not summary_search_id:
        raise ValueError("summary_search_id must be a non-empty string")
    try:
        found = (
            read_scope.node_relation(read_scope.DEFAULT_SCOPE, Search, db_alias=db_alias)
            .filter(entity_id=summary_search_id)
            .first()
        )
    except (ValueError, TypeError, ValidationError):  # not a UUID  # fmt: skip
        found = None
    if found is None:
        raise ValueError(f"summary_search_id {summary_search_id} is not a search on this grid")
    runner = (found.definition or {}).get("runner_key") if isinstance(found.definition, dict) else None
    if found.search_type != "module" or runner != SUMMARY_RUNNER:
        raise ValueError(f"summary_search_id {summary_search_id} is not a dimension-mapping-summary search")
    return found


def _defaults(search: Any) -> dict[str, Any]:
    schema = search.input_schema if isinstance(search.input_schema, dict) else {}
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    return {
        name: props[name]["default"]
        for name in _SUMMARY_INPUTS
        if isinstance(props.get(name), dict) and "default" in props[name]
    }


def dimension_mapping_totals(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """Exactly one row: `groups`, `percent_overall`, `denominator`, `mapped`, `unmapped`, `mapped_incorrectly`, `no_rule`,
    `percent_pooled`. `warnings` are the summary's own.

    req-compliance-core-dimension-mapping-totals
    """
    summary = _summary_search(inputs.get("summary_search_id"), db_alias=db_alias)
    out = dimension_mapping_summary(summary, _defaults(summary), db_alias=db_alias, layer=layer)
    row = totals_from_rows(out["rows"])
    return {"nodes": [], "edges": [], "rows": [row], "info": {"row_count": 1}, "warnings": out["warnings"]}


def _summaries(raw: Any) -> list[tuple[str, str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("summaries must be a non-empty array")
    seen: set[str] = set()
    out: list[tuple[str, str, Any]] = []
    for item in raw:
        key = item.get("key") if isinstance(item, dict) else None
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise ValueError(f"summaries key {key!r} must match ^[a-z][a-z0-9_]*$")
        if key in seen:
            raise ValueError(f"summaries key {key} is repeated")
        seen.add(key)
        label = item.get("label", key)
        if not isinstance(label, str) or not label:
            raise ValueError(f"summaries label for {key} must be a non-empty string")
        out.append((key, label, item.get("summary_search_id")))
    return out


def dimension_mapping_totals_set(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per summary, in array order: `key`, `label`, then the same fields `dimension-mapping-totals` returns, then
    `percent_text`, `percent_overall` to one decimal with a `%` (`None` when there is none), for a card that shows it as it is.
    `warnings` are the summaries' own, concatenated. Input `summaries`: a non-empty array of `{key, label?, summary_search_id}`
    (`label` defaults to `key`).

    req-compliance-core-dimension-mapping-totals-set
    """
    triples = _summaries(inputs.get("summaries"))
    searches = [(key, label, _summary_search(sid, db_alias=db_alias)) for key, label, sid in triples]  # validate all first
    rows: list[dict[str, Any]] = []
    warnings: list[Any] = []
    for key, label, summary in searches:
        out = dimension_mapping_summary(summary, _defaults(summary), db_alias=db_alias, layer=layer)
        totals = totals_from_rows(out["rows"])
        percent = totals["percent_overall"]
        rows.append({"key": key, "label": label, **totals, "percent_text": None if percent is None else f"{round(percent, 1)}%"})
        warnings.extend(out["warnings"])
    return {"nodes": [], "edges": [], "rows": rows, "info": {"row_count": len(rows)}, "warnings": warnings}
