"""Mapped, unmapped and mapped incorrectly, as `module` Search runners (`req-compliance-core-dimension-mapping`).

A mapping says, for an entity type or a group of entity types, which dimension keys it should carry and which values are
acceptable. The two runners compare the grid against it and put every live entity of a mapped type into one of three states.
The mapping is the ``mappings`` input of the Search (its ``input_schema`` default), so it is versioned with the Search node;
nothing here names an entity type, a dimension key or a value. Reads use the read rules Gryphon applies
(``tap_grid.gryphon.read_scope``: a tombstoned entity contributes nothing; the caller's ``db_alias`` for every query).
Neither runner writes.

Inputs (both runners):

    mappings       a non-empty array of at most 50 mapping rows ``{entity_type | entity_types, label?, keys, match}``; exactly
                   one of ``entity_type`` and ``entity_types`` (a non-empty array of at most 50 types, ``*`` meaning every type
                   no other row names, in grouped mode); ``keys`` is a non-empty array of at most 20 ``{key, allowed?}`` with
                   ``allowed`` a non-empty array of at most 100 strings, or omitted to accept any present value; ``match`` is
                   ``all`` (default) or ``any``
    group_by       optional dimension key; set, both runners work in grouped mode
    exclude_groups optional (grouped mode only) array of at most 50 group values left out of the result entirely

``dimension-mapping-entities`` also takes ``status`` (one of the three states) and ``max_entities`` (1 to 5000, default 1000).

A key is *present* on an entity when its ``dimensions`` map has it with a value that is not ``null`` (``null`` is unobserved
and counts as absent), and *correct* when the value is a string equal to one of the key's ``allowed`` strings, exactly, or,
for a key with no ``allowed``, when it is present. The dimensions are compared as the JSON the entity stores, so a number or
an array is never mistaken for a string.

    mapped              ``match: any``: at least one listed key is correct; ``match: all``: every listed key is correct
    mapped_incorrectly  not mapped, and at least one listed key is present with a value that is not allowed
    unmapped            neither

Grouped mode: the population is every live entity carrying the ``group_by`` key with a non-null value, of any type, grouped by
that value. An entity is judged by the first row, in input order, naming its type exactly, else the first row naming ``*``. An
entity of a type no row names is ``unmapped`` and counted in ``no_rule``: a gap to show, never an entity to leave out.
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
MAX_TYPES = 50
MAX_EXCLUDED = 50
MAX_NAME = 128  # an entity type, a dimension key, a label or a group value
MAX_VALUE = 256  # one allowed value
DEFAULT_MAX_ENTITIES = 1000
MAX_ENTITIES = 5000
STATES = ("mapped", "unmapped", "mapped_incorrectly")
_STATE_ORDER = {"mapped_incorrectly": 0, "unmapped": 1, "mapped": 2}
CATCH_ALL = "*"
NO_RULE = "no rule"
_CHUNK = 2000


@dataclass(frozen=True)
class MappingRow:
    entity_types: tuple[str, ...]
    keys: tuple[tuple[str, tuple[str, ...] | None], ...]  # allowed is None for "any present value"
    match: str
    label: str | None = None

    @property
    def keys_text(self) -> str:
        return "\n".join(
            f"{key}: {'any value' if allowed is None else ', '.join(allowed)}" for key, allowed in self.keys
        )

    @property
    def display(self) -> str:
        """The group's name in the summary: the explicit label, else the single type's registered name, else the types."""
        if self.label:
            return self.label
        if len(self.entity_types) == 1:
            return _label(self.entity_types[0])
        return ", ".join(self.entity_types)


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _types(where: str, raw: dict[str, Any]) -> tuple[str, ...]:
    if ("entity_type" in raw) == ("entity_types" in raw):
        raise ValueError(f"{where} needs exactly one of entity_type and entity_types")
    single, group = raw.get("entity_type"), raw.get("entity_types")
    if "entity_type" in raw:
        if not _non_empty_str(single) or len(single) > MAX_NAME:
            raise ValueError(f"{where}.entity_type must be a non-empty string of at most {MAX_NAME} characters")
        return (single,)
    if not isinstance(group, list) or not group:
        raise ValueError(f"{where}.entity_types must be a non-empty array")
    if len(group) > MAX_TYPES:
        raise ValueError(f"{where}.entity_types has {len(group)} types; at most {MAX_TYPES} are allowed")
    if not all(_non_empty_str(t) and len(t) <= MAX_NAME for t in group):
        raise ValueError(f"{where}.entity_types must hold non-empty strings of at most {MAX_NAME} characters")
    return tuple(group)


def _row(index: int, raw: Any) -> MappingRow:
    where = f"mappings[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be an object")
    types = _types(where, raw)
    label = raw.get("label")
    if label is not None and (not isinstance(label, str) or len(label) > MAX_NAME):
        raise ValueError(f"{where}.label must be a string of at most {MAX_NAME} characters")
    keys = raw.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ValueError(f"{where}.keys must be a non-empty array")
    if len(keys) > MAX_KEYS:
        raise ValueError(f"{where}.keys has {len(keys)} keys; at most {MAX_KEYS} are allowed")
    parsed: list[tuple[str, tuple[str, ...] | None]] = []
    for position, item in enumerate(keys):
        at = f"{where}.keys[{position}]"
        if not isinstance(item, dict) or not _non_empty_str(item.get("key")) or len(item["key"]) > MAX_NAME:
            raise ValueError(f"{at}.key must be a non-empty string of at most {MAX_NAME} characters")
        if "allowed" not in item:
            parsed.append((item["key"], None))
            continue
        allowed = item["allowed"]
        if not isinstance(allowed, list) or not allowed or not all(isinstance(v, str) for v in allowed):
            raise ValueError(f"{at}.allowed must be a non-empty array of strings")
        if len(allowed) > MAX_ALLOWED:
            raise ValueError(f"{at}.allowed has {len(allowed)} values; at most {MAX_ALLOWED} are allowed")
        if any(len(v) > MAX_VALUE for v in allowed):
            raise ValueError(f"{at}.allowed has a value longer than {MAX_VALUE} characters")
        parsed.append((item["key"], tuple(allowed)))
    match = raw.get("match", "all")
    if match not in ("any", "all"):
        raise ValueError(f"{where}.match must be 'any' or 'all'")
    return MappingRow(types, tuple(parsed), match, label)


def _mappings(inputs: dict[str, Any]) -> list[MappingRow]:
    raw = inputs.get("mappings")
    if not isinstance(raw, list) or not raw:
        raise ValueError("mappings must be a non-empty array of mapping rows")
    if len(raw) > MAX_MAPPING_ROWS:
        raise ValueError(f"mappings has {len(raw)} rows; at most {MAX_MAPPING_ROWS} are allowed")
    return [_row(index, item) for index, item in enumerate(raw)]


def _grouping(inputs: dict[str, Any]) -> tuple[str | None, frozenset[str]]:
    group_by = inputs.get("group_by")
    if group_by is not None and (not _non_empty_str(group_by) or len(group_by) > MAX_NAME):
        raise ValueError(f"group_by must be a non-empty string of at most {MAX_NAME} characters")
    excluded = inputs.get("exclude_groups")
    if excluded is None:
        return group_by, frozenset()
    if group_by is None:
        raise ValueError("exclude_groups needs group_by")
    if (
        not isinstance(excluded, list)
        or len(excluded) > MAX_EXCLUDED
        or not all(isinstance(g, str) and len(g) <= MAX_NAME for g in excluded)
    ):
        raise ValueError(
            f"exclude_groups must be an array of at most {MAX_EXCLUDED} strings of at most {MAX_NAME} characters"
        )
    return group_by, frozenset(excluded)


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
    correct = [
        key in found and (allowed is None or (isinstance(found[key], str) and found[key] in allowed))
        for key, allowed in row.keys
    ]
    mapped = any(correct) if row.match == "any" else all(correct)
    if mapped:
        return "mapped", found
    if any(key in found and not ok for (key, _), ok in zip(row.keys, correct, strict=True)):
        return "mapped_incorrectly", found
    return "unmapped", found


def _entities(entity_types: tuple[str, ...], *, db_alias: str) -> Any:
    """The live entities of a row's types, streamed in one query: ``(pk, name, entity_type, dimensions)``."""
    return (
        read_scope.node_relation(read_scope.DEFAULT_SCOPE, None, db_alias=db_alias)
        .filter(entity_type__in=entity_types)
        .values_list("pk", "name", "entity_type", "dimensions")
        .iterator(chunk_size=_CHUNK)
    )


def _grouped_population(group_by: str, *, db_alias: str) -> Any:
    """Every live entity carrying the key, of any type, streamed: ``(pk, name, entity_type, dimensions)``.

    The database filter keeps entities that have the key at all; a JSON ``null`` value is dropped by the caller.
    """
    return (
        read_scope.node_relation(read_scope.DEFAULT_SCOPE, None, db_alias=db_alias)
        .filter(**{f"dimensions__{group_by}__isnull": False})
        .values_list("pk", "name", "entity_type", "dimensions")
        .iterator(chunk_size=_CHUNK)
    )


def _value_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


def _warnings(rows: list[MappingRow], *, db_alias: str, extra_keys: tuple[str, ...] = ()) -> dict[str, list[str]]:
    """Keys and allowed values with no dimension node: reported, never failed on, and they change no state.

    The dictionary is read once per distinct key, whatever the number of mapping rows that name it. A key that accepts any
    value has no allowed value to check; ``extra_keys`` are keys to check for a description only (the grouping key).
    """
    allowed_by_key: dict[str, set[str]] = {key: set() for key in extra_keys}
    for row in rows:
        for key, allowed in row.keys:
            allowed_by_key.setdefault(key, set()).update(allowed or ())
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


def _judging(rows: list[MappingRow]) -> tuple[dict[str, int], int | None]:
    """Grouped mode: the index of the first row naming each type exactly, and of the first row naming ``*``."""
    exact: dict[str, int] = {}
    catch_all: int | None = None
    for index, row in enumerate(rows):
        for entity_type in row.entity_types:
            if entity_type == CATCH_ALL:
                catch_all = index if catch_all is None else catch_all
            else:
                exact.setdefault(entity_type, index)
    return exact, catch_all


def _group_label(value: str, declared: dict[str, str]) -> str:
    """The dictionary description of the value up to its first colon, without a trailing full stop; else the value."""
    text = declared.get(value, "")
    head = text.split(":", 1)[0].strip().removesuffix(".").strip()
    return head or value


def _grouped_stream(rows: list[MappingRow], group_by: str, excluded: frozenset[str], *, db_alias: str) -> Any:
    """``(group, pk, name, entity_type, state, found, judging index or None)`` for each entity in the grouped population."""
    exact, catch_all = _judging(rows)
    for pk, name, entity_type, dimensions in _grouped_population(group_by, db_alias=db_alias):
        value = dimensions.get(group_by) if isinstance(dimensions, dict) else None
        if value is None:
            continue
        group = _value_text(value)
        if group in excluded:
            continue
        index = exact.get(entity_type, catch_all)
        if index is None:
            yield group, pk, name, entity_type, "unmapped", {}, None
            continue
        state, found = classify(dimensions, rows[index])
        yield group, pk, name, entity_type, state, found, index


def _grouped_summary(
    rows: list[MappingRow], group_by: str, excluded: frozenset[str], *, db_alias: str
) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    no_rule_types: dict[str, int] = {}
    for group, _pk, _name, entity_type, state, _found, index in _grouped_stream(
        rows, group_by, excluded, db_alias=db_alias
    ):
        bucket = counts.setdefault(group, {**dict.fromkeys(STATES, 0), "no_rule": 0})
        bucket[state] += 1
        if index is None:
            bucket["no_rule"] += 1
            no_rule_types[entity_type] = no_rule_types.get(entity_type, 0) + 1
    _description, declared = read_dictionary(group_by, db_alias=db_alias)
    declared_values = sorted(v for v in declared if v not in excluded)
    others = sorted(g for g in counts if g not in declared)
    out: list[dict[str, Any]] = []
    for group in [*declared_values, *others]:
        bucket = counts.get(group) or {**dict.fromkeys(STATES, 0), "no_rule": 0}
        denominator = bucket["mapped"] + bucket["unmapped"] + bucket["mapped_incorrectly"]
        out.append(
            {
                "group": group,
                "label": _group_label(group, declared),
                "denominator": denominator,
                **bucket,
                "percent_mapped": round(100 * bucket["mapped"] / denominator, 1) if denominator else None,
            }
        )
    warnings = _warnings(rows, db_alias=db_alias, extra_keys=(group_by,))
    if no_rule_types:
        warnings["no_rule_types"] = [f"{t}: {n}" for t, n in sorted(no_rule_types.items())]
    return _envelope(out, warnings)


def dimension_mapping_summary(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per mapping row, in input order: ``entity_type``, ``entity_types``, ``label``, ``keys_text``, ``match``,
    ``denominator``, ``mapped``, ``unmapped``, ``mapped_incorrectly``, ``percent_mapped`` (one decimal, ``None`` at a zero
    denominator). With ``group_by``, one row per value of that key instead: ``group``, ``label``, ``denominator``, the three
    states, ``no_rule`` and ``percent_mapped``.

    req-compliance-core-dimension-mapping
    """
    mapping = _mappings(inputs)
    group_by, excluded = _grouping(inputs)
    if group_by is not None:
        return _grouped_summary(mapping, group_by, excluded, db_alias=db_alias)
    rows: list[dict[str, Any]] = []
    for row in mapping:
        counts = dict.fromkeys(STATES, 0)
        for _pk, _name, _type, dimensions in _entities(row.entity_types, db_alias=db_alias):
            counts[classify(dimensions, row)[0]] += 1
        denominator = sum(counts.values())
        rows.append(
            {
                "entity_type": row.entity_types[0] if len(row.entity_types) == 1 else ", ".join(row.entity_types),
                "entity_types": list(row.entity_types),
                "label": row.display,
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
    ``mapped``, then type, name, ``entity_id`` and ``mapping``; at most ``max_entities`` rows. With ``group_by``, one row per
    entity, with ``group`` and ``mapping`` (``None`` and ``allowed_text`` ``no rule`` when no row judges it).

    req-compliance-core-dimension-mapping
    """
    mapping, wanted, max_entities = _entity_inputs(inputs)
    group_by, excluded = _grouping(inputs)
    texts = [row.keys_text for row in mapping]  # one string per mapping row, shared by every entity row of it
    seen = 0

    def entity_row(index: int | None, pk: Any, name: str, entity_type: str, state: str, found: dict[str, Any]) -> Any:
        return (_STATE_ORDER[state], entity_type, name, str(pk), -1 if index is None else index), {
            "mapping": index,
            "entity_id": str(pk),
            "entity_type": entity_type,
            "label": _label(entity_type),
            "name": name,
            "status": state,
            "found": found,
            "found_text": "\n".join(f"{k} = {_value_text(v)}" for k, v in found.items()) or "not set",
            "allowed_text": NO_RULE if index is None else texts[index],
        }

    def stream() -> Any:
        nonlocal seen
        if group_by is not None:
            for group, pk, name, entity_type, state, found, index in _grouped_stream(
                mapping, group_by, excluded, db_alias=db_alias
            ):
                if wanted is not None and state != wanted:
                    continue
                seen += 1
                key, row = entity_row(index, pk, name, entity_type, state, found)
                yield key, {**row, "group": group}
            return
        for index, row in enumerate(mapping):
            for pk, name, entity_type, dimensions in _entities(row.entity_types, db_alias=db_alias):
                state, found = classify(dimensions, row)
                if wanted is not None and state != wanted:
                    continue
                seen += 1
                yield entity_row(index, pk, name, entity_type, state, found)

    # Only the first max_entities rows are kept while the entities stream past, so memory is bounded by the cap, not by
    # the grid or by the number of mapping rows; the count of the rest is exact.
    kept = heapq.nsmallest(max_entities, stream(), key=lambda item: item[0])
    rows = [row for _key, row in kept]
    warnings = _warnings(mapping, db_alias=db_alias, extra_keys=(group_by,) if group_by else ())
    if seen > max_entities:
        warnings["entities_omitted"] = [
            f"{seen - max_entities} entity rows were left out; max_entities is {max_entities}"
        ]
    return _envelope(rows, warnings)
