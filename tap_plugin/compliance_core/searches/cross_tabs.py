"""Vulnerability cross-tabs as `module` Search runners (req-compliance-core-searches).

Gryphon has no conditional count and no group-concat, so these two tables are computed with
Django ORM aggregation (George's ruling; `req-grid-search-module`). They obey the read rules
Gryphon applies: every relation is started from ``tap_grid.gryphon.read_scope`` (the scoped
base relation, the scoped joined edge and endpoint), so tombstoned nodes and edges are excluded
and the compiled query is checked by ``assert_query_scoped`` before it runs; the caller's
``db_alias`` is used for every query.

Both runners return a rows-only envelope: ``rows`` is a list of flat JSON-serialisable dicts
(counts are ints), ``nodes`` and ``edges`` are empty. ``layer`` selects a subgraph layer of nodes
and edges; there are none here, so it is accepted and unused.

The carrier rule shared by both: a finding counts when its status is ``open``, it concerns a
vulnerability (``CONCERNS_COMPLIANCE_VULNERABILITY``, finding to vulnerability) and a carrier
(``CARRIES_COMPLIANCE_FINDING``, carrier to finding) whose ``entity_type`` is not in the input
``exclude_types`` carries it. Which carrier types to exclude is the Search's input, never code.
"""

from __future__ import annotations

from typing import Any

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, F, Q
from django.db.models.functions import JSONObject

from tap_grid.gryphon import read_scope
from tap_grid.models import Search

from ..models.compliance_finding import ComplianceFinding
from ..models.compliance_vulnerability import ComplianceVulnerability

CARRIES_EDGE = "CARRIES_COMPLIANCE_FINDING__compliance_core"
CONCERNS_EDGE = "CONCERNS_COMPLIANCE_VULNERABILITY__compliance_core"

# Entity.<related_name> from the spine row to the typed row (BaseModel.entity related_name="%(class)s").
_FINDING_ROW = ComplianceFinding.__name__.lower()
_VULNERABILITY_ROW = ComplianceVulnerability.__name__.lower()

# George's rule: critical folds into high. Unscored (null cvss) findings are in none of the bands.
_HIGH_MIN = 7
_MEDIUM_MIN = 4


def _exclude_types(inputs: dict[str, Any]) -> list[str]:
    """The ``exclude_types`` input: an array of strings, absent meaning none."""
    value = inputs.get("exclude_types") or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("exclude_types must be an array of strings")
    return value


def _open_vulnerability_findings(exclude_types: list[str], *, db_alias: str) -> tuple[Any, str]:
    """Carrier edges to open findings that concern a vulnerability, plus the vulnerability path.

    The base is the scoped edge relation, so the carries edge and both endpoints (the carrier
    and the finding) are live. The second hop (finding to vulnerability) is joined with its edge
    and endpoint predicates merged into the SAME ``filter()`` call as its other conditions, as
    ``read_scope`` requires for a multi-valued relation. Returns ``(queryset, vuln_path)`` where
    ``vuln_path`` is the ORM path from the carries edge to the vulnerability's spine row.
    """
    scope = read_scope.DEFAULT_SCOPE
    hop = read_scope.reverse_edge_path("to_entity", "out")
    vuln_entity = f"{hop}__to_entity"
    qs = read_scope.edge_relation(scope, db_alias=db_alias).filter(
        **{
            "edge_type": CARRIES_EDGE,
            "to_entity__entity_type": ComplianceFinding.ENTITY_TYPE,
            f"to_entity__{_FINDING_ROW}__status": "open",
            f"{hop}__edge_type": CONCERNS_EDGE,
            f"{vuln_entity}__entity_type": ComplianceVulnerability.ENTITY_TYPE,
            **read_scope.edge_scope_filters(scope, hop),
            **read_scope.node_scope_filters(scope, vuln_entity),
        }
    )
    if exclude_types:
        qs = qs.exclude(from_entity__entity_type__in=exclude_types)
    return qs, vuln_entity


def _envelope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"nodes": [], "edges": [], "rows": rows, "info": {"row_count": len(rows)}, "warnings": {}}


def _component_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Carriers as ``{id, name, type}`` (all strings, a missing name or type is ""), one per carrier id, sorted by name then id."""
    distinct = {
        str(item["id"]): {
            "id": str(item["id"]),
            "name": item.get("name") or "",
            "type": item.get("type") or "",
        }
        for item in items
    }
    return sorted(distinct.values(), key=lambda item: (item["name"], item["id"]))


def vulnerability_components(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per vulnerability with an open finding on a non-excluded carrier.

    Row: ``id``, ``title``, ``cvss`` (number or null), ``kev`` (bool), ``published`` (ISO or
    null), ``components`` (distinct carriers), ``component_names`` (distinct carrier names,
    sorted, ", "-joined), ``component_items`` (the same carriers as structured items
    ``{id, name, type}``, distinct by carrier, sorted by name then id; ``id`` is the carrier's
    entity id as a string, so a table can link each one). Order: cvss descending with nulls
    last, then id.

    req-compliance-core-searches-vuln-components
    """
    qs, vuln_entity = _open_vulnerability_findings(_exclude_types(inputs), db_alias=db_alias)
    vuln = f"{vuln_entity}__{_VULNERABILITY_ROW}"
    grouped = (
        qs.values(
            vuln_pk=F(vuln_entity),
            vid=F(f"{vuln}__vuln_id"),
            vtitle=F(f"{vuln}__title"),
            vcvss=F(f"{vuln}__cvss_score"),
            vkev=F(f"{vuln}__kev"),
            vpublished=F(f"{vuln}__published_at"),
        )
        .annotate(
            n_components=Count("from_entity", distinct=True),
            names=ArrayAgg("from_entity__name", distinct=True),
            items=ArrayAgg(
                JSONObject(id="from_entity", name="from_entity__name", type="from_entity__entity_type"), distinct=True
            ),
        )
        .order_by(F("vcvss").desc(nulls_last=True), "vid", "vuln_pk")
    )
    rows = [
        {
            "id": r["vid"],
            "title": r["vtitle"],
            "cvss": r["vcvss"],
            "kev": bool(r["vkev"]),
            "published": r["vpublished"].isoformat() if r["vpublished"] is not None else None,
            "components": int(r["n_components"]),
            "component_names": ", ".join(sorted({name for name in r["names"] if name})),
            "component_items": _component_items(r["items"]),
        }
        for r in grouped
    ]
    return _envelope(rows)


def component_severity(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per carrier with an open vulnerability finding, severity-banded in one query.

    Row: ``cid``, ``component``, ``type``, ``high`` (cvss >= 7), ``medium`` (4 <= cvss < 7),
    ``low`` (cvss < 4), ``unscored`` (vulnerability has no cvss), ``kev`` (vulnerability on KEV),
    ``total`` (all open findings). Counts are distinct findings. Order: kev desc, high desc,
    total desc, component.

    req-compliance-core-searches-component-severity
    """
    qs, vuln_entity = _open_vulnerability_findings(_exclude_types(inputs), db_alias=db_alias)
    cvss = f"{vuln_entity}__{_VULNERABILITY_ROW}__cvss_score"
    kev = f"{vuln_entity}__{_VULNERABILITY_ROW}__kev"

    def findings(condition: Q | None = None) -> Count:
        return Count("to_entity", distinct=True, filter=condition)

    grouped = (
        qs.values(cid=F("from_entity"), component=F("from_entity__name"), type=F("from_entity__entity_type"))
        .annotate(
            high=findings(Q(**{f"{cvss}__gte": _HIGH_MIN})),
            medium=findings(Q(**{f"{cvss}__gte": _MEDIUM_MIN, f"{cvss}__lt": _HIGH_MIN})),
            low=findings(Q(**{f"{cvss}__lt": _MEDIUM_MIN})),
            unscored=findings(Q(**{f"{cvss}__isnull": True})),
            kev_count=findings(Q(**{kev: True})),
            total=findings(),
        )
        .order_by(F("kev_count").desc(), F("high").desc(), F("total").desc(), "component", "cid")
    )
    rows = [
        {
            "cid": str(r["cid"]),
            "component": r["component"],
            "type": r["type"],
            "high": int(r["high"]),
            "medium": int(r["medium"]),
            "low": int(r["low"]),
            "unscored": int(r["unscored"]),
            "kev": int(r["kev_count"]),
            "total": int(r["total"]),
        }
        for r in grouped
    ]
    return _envelope(rows)
