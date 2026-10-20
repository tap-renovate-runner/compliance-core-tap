"""Entities per dimension value, by entity type, as a `module` Search runner (`req-compliance-core-dimension-coverage`).

Gryphon cannot answer "how many entities carry each value of this dimension, split by entity type": a labelless
aggregate (a MATCH over every node regardless of type) grouped by ``entity_type`` and by the value of a
dimension key is not supported. This runner computes it with Django ORM aggregation under the read rules Gryphon
applies (``tap_grid.gryphon.read_scope``: the scoped spine relation, so a tombstoned entity contributes nothing;
the caller's ``db_alias`` for every query). It knows no dimension key, no value and no entity type: the key is the
Search's input.

Inputs:

    dimension_key    the dimension to cover, for example ``dataclass.customer`` (required string)
    exclude_types    entity types that are not counted, for example the edge and batch spine rows (array of strings)

The dimension dictionary is read from the grid, not from code. The key's own ``dimension`` node supplies the key's
description; the values come from the ``dimension`` nodes named ``<key>.<value>`` (the dotted name carries the
axis-to-value relationship, ``spec-grid-dimension.md``), each value's description from its node. A value stamped on an
entity that has no dictionary node is still counted, with no description, so an undeclared value is visible rather
than dropped.

One row, for the key: ``key``, ``description`` (null when the key has no dimension node), ``total`` (entities that
carry any value of the key), ``values`` (one item per value, declared values in name order then undeclared values in
name order: ``{value, description, declared, count, by_type}`` where ``by_type`` is ``[{type, label, count}]`` ordered by
count descending then type), and two display strings made from ``values`` so a card can print them:
``values_text`` (one line per value: ``<value>: <description>``) and ``breakdown_text`` (one line per value:
``<value>: <n> <noun>: <label> <n>, ...`` or ``<value>: none``). ``label`` is the entity type's registered name
(the model's ``verbose_name``), else the entity type itself.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Count
from django.db.models.fields.json import KeyTextTransform

from tap_grid.gryphon import read_scope
from tap_grid.models import Dimension, Search
from tap_grid.registry import get_model_class


def _inputs(inputs: dict[str, Any]) -> tuple[str, list[str]]:
    """Validate the inputs: ``(dimension_key, exclude_types)``; ValueError names the bad one."""
    key = inputs.get("dimension_key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("dimension_key must be a non-empty string")
    exclude = inputs.get("exclude_types") or []
    if not isinstance(exclude, list) or not all(isinstance(item, str) for item in exclude):
        raise ValueError("exclude_types must be an array of strings")
    return key, exclude


def _label(entity_type: str) -> str:
    """The entity type's registered name, else the type itself."""
    try:
        return str(get_model_class(entity_type)._meta.verbose_name)  # type: ignore[attr-defined]
    except KeyError:
        return entity_type


def _dictionary(key: str, *, db_alias: str) -> tuple[str | None, dict[str, str]]:
    """The key's description (None without a node) and ``{value: description}`` from the ``<key>.<value>`` nodes."""
    prefix = f"{key}."
    description: str | None = None
    declared: dict[str, str] = {}
    nodes = read_scope.node_relation(read_scope.DEFAULT_SCOPE, Dimension, db_alias=db_alias)
    for name, text in nodes.filter(name__startswith=key).values_list("name", "description"):
        if name == key:
            description = text
        elif name.startswith(prefix) and "." not in name[len(prefix) :]:
            declared[name[len(prefix) :]] = text
    return description, declared


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def dimension_coverage(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """The entities carrying each value of one dimension key, broken down by entity type.

    req-compliance-core-dimension-coverage
    """
    key, exclude = _inputs(inputs)
    description, declared = _dictionary(key, db_alias=db_alias)

    stamped = KeyTextTransform(key, "dimensions")
    entities = read_scope.node_relation(read_scope.DEFAULT_SCOPE, None, db_alias=db_alias)
    if exclude:
        entities = entities.exclude(entity_type__in=exclude)
    grouped = (
        entities.annotate(stamped_value=stamped)
        .filter(stamped_value__isnull=False)
        .values("stamped_value", "entity_type")
        .annotate(n=Count("pk"))
    )
    by_value: dict[str, dict[str, int]] = defaultdict(dict)
    for row in grouped:
        by_value[row["stamped_value"]][row["entity_type"]] = int(row["n"])

    values: list[dict[str, Any]] = []
    for value in [*sorted(declared), *sorted(set(by_value) - set(declared))]:
        counts = by_value.get(value, {})
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        values.append(
            {
                "value": value,
                "description": declared.get(value),
                "declared": value in declared,
                "count": sum(counts.values()),
                "by_type": [{"type": etype, "label": _label(etype), "count": n} for etype, n in ordered],
            }
        )

    values_text = "\n".join(f"{v['value']}: {v['description'] or 'no description in the dictionary'}" for v in values)
    breakdown_lines = []
    for v in values:
        if v["count"] == 0:
            breakdown_lines.append(f"{v['value']}: none")
            continue
        parts = ", ".join(f"{t['label']} {t['count']}" for t in v["by_type"])
        breakdown_lines.append(f"{v['value']}: {_plural(v['count'], 'component')}: {parts}")

    row = {
        "key": key,
        "description": description,
        "total": sum(v["count"] for v in values),
        "values": values,
        "values_text": values_text,
        "breakdown_text": "\n".join(breakdown_lines),
    }
    return {"nodes": [], "edges": [], "rows": [row], "info": {"row_count": 1}, "warnings": {}}
