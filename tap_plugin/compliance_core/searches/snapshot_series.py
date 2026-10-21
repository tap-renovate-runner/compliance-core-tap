"""A Search's snapshots read back as chart points, as a `module` Search runner (`req-compliance-core-search-snapshot-series`).

A snapshot holds one run of a Search; a line chart needs one row per point: a time, the line it belongs to and a value. This
reads the snapshots of one Search (the ones a ``CAPTURES_SEARCH`` edge points at it) and returns that shape. It knows no Search,
field or metric: the Search, the row field that names a line and the row field that is the number are all inputs. Reads use the
read rules Gryphon applies (``tap_grid.gryphon.read_scope``, the caller's ``db_alias``); it writes nothing.

Inputs:

    search_id        required, the entity id of the Search whose snapshots are read
    series_field     required, the row field whose value names the line
    value_field      required, the row field that is the point's number
    aggregate_label  optional, default ``Overall``: the aggregate line's name; an empty string omits the aggregate
    since            optional ISO 8601 date-time: only snapshots observed at or after it
    max_snapshots    optional, 1 to 5000, default 720: the most recent snapshots read

One row per snapshot per distinct series value (``observed_at``, ``series``, ``value``, ``aggregate`` false), then one aggregate
row per snapshot whose value is the plain, unweighted mean of that snapshot's series values to one decimal. A null or non-numeric
value is not a point and is not in the mean: a gap is stated, never drawn as 0. Ordered by ``observed_at``, non-aggregate before
aggregate, then ``series``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tap_grid.gryphon import read_scope
from tap_grid.models import Search

from ..models.compliance_search_snapshot import ComplianceSearchSnapshot

CAPTURES_EDGE = "CAPTURES_SEARCH__compliance_core"
DEFAULT_AGGREGATE = "Overall"
DEFAULT_MAX_SNAPSHOTS = 720
MAX_SNAPSHOTS = 5000


def _text(inputs: dict[str, Any], name: str) -> str:
    value = inputs.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _since(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("since must be an ISO 8601 date-time string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("since must be an ISO 8601 date-time string") from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _inputs(inputs: dict[str, Any]) -> tuple[str, str, str, str, datetime | None, int]:
    search_id, series_field, value_field = (
        _text(inputs, "search_id"),
        _text(inputs, "series_field"),
        _text(inputs, "value_field"),
    )
    aggregate = inputs.get("aggregate_label", DEFAULT_AGGREGATE)
    if not isinstance(aggregate, str):
        raise ValueError("aggregate_label must be a string")
    limit = inputs.get("max_snapshots", DEFAULT_MAX_SNAPSHOTS)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_SNAPSHOTS:
        raise ValueError(f"max_snapshots must be an integer from 1 to {MAX_SNAPSHOTS}")
    return search_id, series_field, value_field, aggregate, _since(inputs.get("since")), limit


def _number(value: Any) -> float | int | None:
    return value if isinstance(value, int | float) and not isinstance(value, bool) else None


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_snapshot_series(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """Rows `observed_at`, `series`, `value`, `aggregate`; `warnings` counts skipped rows, truncated and omitted snapshots.

    req-compliance-core-search-snapshot-series
    """
    search_id, series_field, value_field, aggregate_label, since, limit = _inputs(inputs)
    scope = read_scope.DEFAULT_SCOPE
    snapshot_ids = [
        str(pk)
        for pk in read_scope.edge_relation(scope, db_alias=db_alias)
        .filter(edge_type=CAPTURES_EDGE, to_entity_id=search_id)
        .values_list("from_entity_id", flat=True)
    ]
    snapshots = read_scope.node_relation(scope, ComplianceSearchSnapshot, db_alias=db_alias).filter(
        entity_id__in=snapshot_ids
    )
    if since is not None:
        snapshots = snapshots.filter(observed_at__gte=since)
    total = snapshots.count()
    recent = list(snapshots.order_by("-observed_at")[:limit])
    skipped = truncated = duplicates = 0
    out: list[dict[str, Any]] = []
    for snapshot in sorted(recent, key=lambda s: s.observed_at):
        if snapshot.truncated:
            truncated += 1
        seen: dict[str, float | int] = {}
        for row in snapshot.rows if isinstance(snapshot.rows, list) else []:
            series = row.get(series_field) if isinstance(row, dict) else None
            value = _number(row.get(value_field)) if isinstance(row, dict) else None
            if not isinstance(series, str) or value is None:
                skipped += 1
                continue
            if series in seen:
                duplicates += 1  # the first value of a repeated series is the point
                continue
            seen[series] = value
        observed = _stamp(snapshot.observed_at)
        out.extend({"observed_at": observed, "series": s, "value": v, "aggregate": False} for s, v in seen.items())
        if aggregate_label and seen:
            mean = round(sum(seen.values()) / len(seen), 1)
            out.append({"observed_at": observed, "series": aggregate_label, "value": mean, "aggregate": True})
    out.sort(key=lambda r: (r["observed_at"], r["aggregate"], r["series"]))
    warnings: dict[str, Any] = {}
    if skipped:
        warnings["rows_skipped"] = [f"{skipped} rows had a missing or non-numeric series or value and are not points"]
    if duplicates:
        warnings["duplicate_series"] = [f"{duplicates} rows repeated a series within one snapshot; the first was kept"]
    if truncated:
        warnings["truncated_snapshots"] = [f"{truncated} snapshots were truncated and are read from the rows they hold"]
    if total > len(recent):
        warnings["snapshots_omitted"] = [
            f"{total - len(recent)} older snapshots were left out; max_snapshots is {limit}"
        ]
    return {
        "nodes": [],
        "edges": [],
        "rows": out,
        "info": {"row_count": len(out), "snapshot_count": len(recent)},
        "warnings": warnings,
    }
