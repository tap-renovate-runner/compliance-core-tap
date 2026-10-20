"""Mapped, unmapped and mapped incorrectly, as `module` Search runners (`req-compliance-core-dimension-mapping`).

A mapping says, for an entity type, which dimension keys it should carry and which values are acceptable. The two runners
compare the grid against it and put every live entity of a mapped type into one of three states. The mapping is the
``mappings`` input of the Search (its ``input_schema`` default), so it is versioned with the Search node; nothing here names an
entity type, a dimension key or a value. Reads use the read rules Gryphon applies (``tap_grid.gryphon.read_scope``: a
tombstoned entity contributes nothing; the caller's ``db_alias`` for every query). Neither runner writes.

Inputs (both runners):

    mappings       a non-empty array of at most 50 mapping rows ``{entity_type, keys, match}``; ``keys`` is a non-empty
                   array of at most 20 ``{key, allowed}`` with ``allowed`` a non-empty array of at most 100 strings;
                   ``match`` is ``all`` (default) or ``any``

``dimension-mapping-entities`` also takes ``status`` (one of the three states) and ``max_entities`` (1 to 5000, default 1000).

A key is *present* on an entity when its ``dimensions`` map has it with a value that is not ``null`` (``null`` is unobserved
and counts as absent), and *correct* when the value is a string equal to one of the key's ``allowed`` strings, exactly. The
dimensions are compared as the JSON the entity stores, so a number or an array is never mistaken for a string.

    mapped              ``match: any``: at least one listed key is correct; ``match: all``: every listed key is correct
    mapped_incorrectly  not mapped, and at least one listed key is present with a value that is not allowed
    unmapped            neither
"""

from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from typing import Any

from tap_grid.gryphon import read_scope
from tap_grid.models import Search

from .dimension_coverage import _label
from .dimension_dictionary import read_dictionary

MAX_MAPPING_ROWS = 50
MAX_KEYS = 20
MAX_ALLOWED = 100
DEFAULT_MAX_ENTITIES = 1000
MAX_ENTITIES = 5000
STATES = ("mapped", "unmapped", "mapped_incorrectly")
_STATE_ORDER = {"mapped_incorrectly": 0, "unmapped": 1, "mapped": 2}
_CHUNK = 2000


@dataclass(frozen=True)
class MappingRow:
    entity_type: str
    keys: tuple[tuple[str, tuple[str, ...]], ...]
    match: str

    @property
    def keys_text(self) -> str:
        return "\n".join(f"{key}: {', '.join(allowed)}" for key, allowed in self.keys)


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _row(index: int, raw: Any) -> MappingRow:
    where = f"mappings[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be an object")
    if not _non_empty_str(raw.get("entity_type")):
        raise ValueError(f"{where}.entity_type must be a non-empty string")
    keys = raw.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ValueError(f"{where}.keys must be a non-empty array")
    if len(keys) > MAX_KEYS:
        raise ValueError(f"{where}.keys has {len(keys)} keys; at most {MAX_KEYS} are allowed")
    parsed: list[tuple[str, tuple[str, ...]]] = []
    for position, item in enumerate(keys):
        at = f"{where}.keys[{position}]"
        if not isinstance(item, dict) or not _non_empty_str(item.get("key")):
            raise ValueError(f"{at}.key must be a non-empty string")
        allowed = item.get("allowed")
        if not isinstance(allowed, list) or not allowed or not all(isinstance(v, str) for v in allowed):
            raise ValueError(f"{at}.allowed must be a non-empty array of strings")
        if len(allowed) > MAX_ALLOWED:
            raise ValueError(f"{at}.allowed has {len(allowed)} values; at most {MAX_ALLOWED} are allowed")
        parsed.append((item["key"], tuple(allowed)))
    match = raw.get("match", "all")
    if match not in ("any", "all"):
        raise ValueError(f"{where}.match must be 'any' or 'all'")
    return MappingRow(raw["entity_type"], tuple(parsed), match)


def _mappings(inputs: dict[str, Any]) -> list[MappingRow]:
    raw = inputs.get("mappings")
    if not isinstance(raw, list) or not raw:
        raise ValueError("mappings must be a non-empty array of mapping rows")
    if len(raw) > MAX_MAPPING_ROWS:
        raise ValueError(f"mappings has {len(raw)} rows; at most {MAX_MAPPING_ROWS} are allowed")
    return [_row(index, item) for index, item in enumerate(raw)]


def _entity_inputs(inputs: dict[str, Any]) -> tuple[list[MappingRow], str | None, int]:
    rows = _mappings(inputs)
    status = inputs.get("status")
    if status is not None and status not in STATES:
        raise ValueError(f"status must be one of {', '.join(STATES)}")
    max_entities = inputs.get("max_entities", DEFAULT_MAX_ENTITIES)
    if isinstance(max_entities, bool) or not isinstance(max_entities, int) or not 1 <= max_entities <= MAX_ENTITIES:
        raise ValueError(f"max_entities must be an integer from 1 to {MAX_ENTITIES}")
    return rows, status, max_entities


def classify(dimensions: Any, row: MappingRow) -> tuple[str, dict[str, Any]]:
    """``(state, found)`` for one entity's dimensions against one mapping row; ``found`` is the listed keys it carries."""
    dims = dimensions if isinstance(dimensions, dict) else {}
    found = {key: dims[key] for key, _ in row.keys if dims.get(key) is not None}
    correct = [key in found and isinstance(found[key], str) and found[key] in allowed for key, allowed in row.keys]
    mapped = any(correct) if row.match == "any" else all(correct)
    if mapped:
        return "mapped", found
    if any(key in found and not ok for (key, _), ok in zip(row.keys, correct, strict=True)):
        return "mapped_incorrectly", found
    return "unmapped", found


def _entities(entity_type: str, *, db_alias: str) -> Any:
    """The live entities of a type, streamed: ``(pk, name, dimensions)``."""
    return (
        read_scope.node_relation(read_scope.DEFAULT_SCOPE, None, db_alias=db_alias)
        .filter(entity_type=entity_type)
        .values_list("pk", "name", "dimensions")
        .iterator(chunk_size=_CHUNK)
    )


def _value_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


def _warnings(rows: list[MappingRow], *, db_alias: str) -> dict[str, list[str]]:
    """Keys and allowed values with no dimension node: reported, never failed on, and they change no state.

    The dictionary is read once per distinct key, whatever the number of mapping rows that name it.
    """
    allowed_by_key: dict[str, set[str]] = {}
    for row in rows:
        for key, allowed in row.keys:
            allowed_by_key.setdefault(key, set()).update(allowed)
    keys: set[str] = set()
    values: set[str] = set()
    for key, allowed in allowed_by_key.items():
        description, declared = read_dictionary(key, db_alias=db_alias)
        if description is None:
            keys.add(key)
        values.update(f"{key} = {value}" for value in allowed if value not in declared)
    out: dict[str, list[str]] = {}
    if keys:
        out["undeclared_keys"] = sorted(keys)
    if values:
        out["undeclared_values"] = sorted(values)
    return out


def _envelope(rows: list[dict[str, Any]], warnings: dict[str, Any]) -> dict[str, Any]:
    return {"nodes": [], "edges": [], "rows": rows, "info": {"row_count": len(rows)}, "warnings": warnings}


def dimension_mapping_summary(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per mapping row, in input order: ``entity_type``, ``label``, ``keys_text``, ``match``, ``denominator``,
    ``mapped``, ``unmapped``, ``mapped_incorrectly``, ``percent_mapped`` (one decimal, ``None`` at a zero denominator).

    req-compliance-core-dimension-mapping
    """
    mapping = _mappings(inputs)
    rows: list[dict[str, Any]] = []
    for row in mapping:
        counts = dict.fromkeys(STATES, 0)
        for _pk, _name, dimensions in _entities(row.entity_type, db_alias=db_alias):
            counts[classify(dimensions, row)[0]] += 1
        denominator = sum(counts.values())
        rows.append(
            {
                "entity_type": row.entity_type,
                "label": _label(row.entity_type),
                "keys_text": row.keys_text,
                "match": row.match,
                "denominator": denominator,
                **counts,
                "percent_mapped": round(100 * counts["mapped"] / denominator, 1) if denominator else None,
            }
        )
    return _envelope(rows, _warnings(mapping, db_alias=db_alias))


def dimension_mapping_entities(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per entity per mapping row: ``mapping`` (the row's index), ``entity_id``, ``entity_type``, ``label``,
    ``name``, ``status``, ``found``, ``found_text``, ``allowed_text``. Ordered ``mapped_incorrectly``, ``unmapped``,
    ``mapped``, then type, name, ``entity_id`` and ``mapping``; at most ``max_entities`` rows.

    req-compliance-core-dimension-mapping
    """
    mapping, wanted, max_entities = _entity_inputs(inputs)
    seen = 0

    def stream() -> Any:
        nonlocal seen
        for index, row in enumerate(mapping):
            for pk, name, dimensions in _entities(row.entity_type, db_alias=db_alias):
                state, found = classify(dimensions, row)
                if wanted is not None and state != wanted:
                    continue
                seen += 1
                yield (_STATE_ORDER[state], row.entity_type, name, str(pk), index), {
                    "mapping": index,
                    "entity_id": str(pk),
                    "entity_type": row.entity_type,
                    "label": _label(row.entity_type),
                    "name": name,
                    "status": state,
                    "found": found,
                    "found_text": "\n".join(f"{k} = {_value_text(v)}" for k, v in found.items()) or "not set",
                    "allowed_text": row.keys_text,
                }

    # Only the first max_entities rows are kept while the entities stream past, so memory is bounded by the cap, not by
    # the grid or by the number of mapping rows; the count of the rest is exact.
    kept = heapq.nsmallest(max_entities, stream(), key=lambda item: item[0])
    rows = [row for _key, row in kept]
    warnings = _warnings(mapping, db_alias=db_alias)
    if seen > max_entities:
        warnings["entities_omitted"] = [f"{seen - max_entities} entity rows were left out; max_entities is {max_entities}"]
    return _envelope(rows, warnings)
