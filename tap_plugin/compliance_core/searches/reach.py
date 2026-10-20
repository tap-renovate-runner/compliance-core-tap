"""Findings reached from a root along edge paths, as `module` Search runners (`req-compliance-core-reach`).

Gryphon has no multi-path aggregate: a query with several MATCH clauses is a union of the clauses but
cannot aggregate across them, so it cannot give "the open findings of this system, reached by two different
routes, counted once". These two runners do, with Django ORM reads under the read rules Gryphon applies
(``tap_grid.gryphon.read_scope``: the scoped edge relation, so a tombstoned node or edge contributes nothing;
the caller's ``db_alias`` for every query).

They know no other plugin's type names. The root entity type and the edge-type chains come from the Search's
inputs (its ``input_schema`` defaults), never from code:

    root_type   the ``entity_type`` of the roots (a string)
    paths       a list of chains of edge types; each chain is followed outward (edge ``from`` to ``to``)
                from a root, and the entities it ends on are the carriers
    entity_id   optional: only this root

A carrier is anything a chain ends on. A finding counts for a root when it is ``open``, a carrier carries it
(``CARRIES_COMPLIANCE_FINDING``, carrier to finding) and it concerns a live vulnerability
(``CONCERNS_COMPLIANCE_VULNERABILITY``, finding to vulnerability). A finding reached by two chains, or by two
carriers, counts once for the root.

``findings-reached-count`` returns one row per root with at least one finding: ``entity_id`` (the root), ``count``.
``findings-reached-list`` returns one row per counted finding: ``entity_id`` (the root), ``name`` (the display
text ``<id> | CVSS <score> | <title>``), ``id``, ``cvss``, ``title`` and ``finding_id``; a finding that concerns
several vulnerabilities is listed once, under its highest-scored vulnerability. ``component`` is the display name of
the carrier(s) the finding was reached through: distinct names sorted, joined by ``", "``, at most ``MAX_COMPONENT_NAMES``
of them followed by ``"+k more"`` for the rest; ``""`` when no carrier has a name. It never changes the row count.
Order: highest ``cvss`` first
(unscored last), then ``id``, then ``finding_id``. The badge population and info window of tap_viz read exactly
these fields: the first needs ``entity_id`` and ``count``, the second ``entity_id`` and ``name`` (and ``id`` for a
row link).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from tap_grid.gryphon import read_scope
from tap_grid.models import Search

from ..models.compliance_finding import ComplianceFinding
from ..models.compliance_vulnerability import ComplianceVulnerability

CARRIES_EDGE = "CARRIES_COMPLIANCE_FINDING__compliance_core"
CONCERNS_EDGE = "CONCERNS_COMPLIANCE_VULNERABILITY__compliance_core"
_FINDING_ROW = ComplianceFinding.__name__.lower()

MAX_PATHS = 8
MAX_PATH_LENGTH = 8
DEFAULT_MAX_RESULTS = 1000
MAX_RESULTS = 5000
MAX_COMPONENT_NAMES = 3
_EDGE_TYPE = re.compile(r"^[A-Za-z0-9_]{1,128}$")


def _envelope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"nodes": [], "edges": [], "rows": rows, "info": {"row_count": len(rows)}, "warnings": {}}


def _inputs(inputs: dict[str, Any]) -> tuple[str, list[list[str]], str | None, int]:
    """Validate the inputs: ``(root_type, paths, entity_id, max_results)``; ValueError names the bad one."""
    root_type = inputs.get("root_type")
    if not isinstance(root_type, str) or not root_type:
        raise ValueError("root_type must be a non-empty string")
    paths = inputs.get("paths")
    if not isinstance(paths, list) or not paths:
        raise ValueError("paths must be a non-empty array of edge-type chains")
    if len(paths) > MAX_PATHS:
        raise ValueError(f"paths has {len(paths)} chains; at most {MAX_PATHS} are allowed")
    for chain in paths:
        if not isinstance(chain, list) or not chain:
            raise ValueError("each of paths must be a non-empty array of edge types")
        if len(chain) > MAX_PATH_LENGTH:
            raise ValueError(f"a chain in paths has {len(chain)} edges; at most {MAX_PATH_LENGTH} are allowed")
        if not all(isinstance(edge, str) and _EDGE_TYPE.match(edge) for edge in chain):
            raise ValueError("every edge type in paths must be a string of letters, digits and underscores")
    entity_id = inputs.get("entity_id")
    if entity_id is not None and (not isinstance(entity_id, str) or not entity_id):
        raise ValueError("entity_id must be a non-empty string when given")
    max_results = inputs.get("max_results", DEFAULT_MAX_RESULTS)
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"max_results must be an integer from 1 to {MAX_RESULTS}")
    return root_type, paths, entity_id, max_results


def _step(edge_type: str, frontier: dict[str, set[str]], *, db_alias: str) -> dict[str, set[str]]:
    """Follow one outward edge type from every entity in the frontier; the frontier maps root -> entities."""
    wanted = {entity for entities in frontier.values() for entity in entities}
    if not wanted:
        return {}
    pairs = (
        read_scope.edge_relation(read_scope.DEFAULT_SCOPE, db_alias=db_alias)
        .filter(edge_type=edge_type, from_entity_id__in=sorted(wanted))
        .values_list("from_entity_id", "to_entity_id")
    )
    targets: dict[str, set[str]] = defaultdict(set)
    for source, target in pairs:
        targets[str(source)].add(str(target))
    nxt: dict[str, set[str]] = {}
    for root, entities in frontier.items():
        reached = {t for entity in entities for t in targets.get(entity, ())}
        if reached:
            nxt[root] = reached
    return nxt


def _roots(root_type: str, entity_id: str | None, *, db_alias: str) -> dict[str, str]:
    """Live roots of the type, ``{entity_id: name}``."""
    qs = read_scope.node_relation(read_scope.DEFAULT_SCOPE, None, db_alias=db_alias).filter(entity_type=root_type)
    if entity_id is not None:
        qs = qs.filter(pk=entity_id)
    return {str(pk): name for pk, name in qs.values_list("pk", "name")}


def _carriers(root_type: str, paths: list[list[str]], entity_id: str | None, *, db_alias: str) -> dict[str, set[str]]:
    """Per root, the carriers every chain ends on (the chains' union)."""
    carriers: dict[str, set[str]] = defaultdict(set)
    for chain in paths:
        frontier = {root: {root} for root in _roots(root_type, entity_id, db_alias=db_alias)}
        for edge_type in chain:
            frontier = _step(edge_type, frontier, db_alias=db_alias)
        for root, entities in frontier.items():
            carriers[root] |= entities
    return carriers


def _findings(
    carriers: dict[str, set[str]], *, db_alias: str
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[tuple[str, str], set[str]]]:
    """``(by_root, concerns, via)``: per root the open findings its carriers carry that concern a live vulnerability,
    ``concerns`` mapping each such finding to the vulnerabilities it concerns, and ``via`` mapping each
    ``(root, finding)`` to the carriers it was reached through."""
    scope = read_scope.DEFAULT_SCOPE
    wanted = sorted({c for entities in carriers.values() for c in entities})
    if not wanted:
        return {}, {}, {}
    carried: dict[str, set[str]] = defaultdict(set)
    for carrier, finding in (
        read_scope.edge_relation(scope, db_alias=db_alias)
        .filter(
            edge_type=CARRIES_EDGE,
            from_entity_id__in=wanted,
            to_entity__entity_type=ComplianceFinding.ENTITY_TYPE,
            **{f"to_entity__{_FINDING_ROW}__status": "open"},
        )
        .values_list("from_entity_id", "to_entity_id")
    ):
        carried[str(carrier)].add(str(finding))
    finding_ids = sorted({f for fs in carried.values() for f in fs})
    concerns: dict[str, set[str]] = defaultdict(set)
    if finding_ids:
        for finding, vuln in (
            read_scope.edge_relation(scope, db_alias=db_alias)
            .filter(
                edge_type=CONCERNS_EDGE,
                from_entity_id__in=finding_ids,
                to_entity__entity_type=ComplianceVulnerability.ENTITY_TYPE,
            )
            .values_list("from_entity_id", "to_entity_id")
        ):
            concerns[str(finding)].add(str(vuln))
    by_root: dict[str, set[str]] = {}
    via: dict[tuple[str, str], set[str]] = defaultdict(set)
    for root, entities in carriers.items():
        for carrier in entities:
            for finding in carried.get(carrier, ()):
                if finding in concerns:
                    by_root.setdefault(root, set()).add(finding)
                    via[(root, finding)].add(carrier)
    return by_root, dict(concerns), dict(via)


def _component(names: set[str]) -> str:
    """Distinct carrier names sorted and joined; past ``MAX_COMPONENT_NAMES`` the rest read ``+k more``."""
    ordered = sorted(names)
    text = ", ".join(ordered[:MAX_COMPONENT_NAMES])
    if len(ordered) > MAX_COMPONENT_NAMES:
        text += f" +{len(ordered) - MAX_COMPONENT_NAMES} more"
    return text


def findings_reached_count(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per root with at least one finding: ``entity_id`` (the root) and ``count`` (distinct findings).

    req-compliance-core-reach-count
    """
    root_type, paths, entity_id, _ = _inputs(inputs)
    by_root, _, _ = _findings(_carriers(root_type, paths, entity_id, db_alias=db_alias), db_alias=db_alias)
    rows = [{"entity_id": root, "count": len(found)} for root, found in sorted(by_root.items())]
    return _envelope(rows)


def findings_reached_list(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per counted finding, highest CVSS first: ``entity_id`` (the root), ``name``, ``id``, ``cvss``,
    ``title``, ``finding_id``, ``component``. ``name`` is ``<id> | CVSS <score or n/a> | <title>``; ``component`` is the
    carrier name(s), up to ``MAX_COMPONENT_NAMES`` then ``+k more`` (``""`` when unnamed); at most ``max_results`` rows.

    req-compliance-core-reach-list
    """
    root_type, paths, entity_id, max_results = _inputs(inputs)
    scope = read_scope.DEFAULT_SCOPE
    by_root, concerns, via = _findings(_carriers(root_type, paths, entity_id, db_alias=db_alias), db_alias=db_alias)
    carrier_ids = sorted({c for cs in via.values() for c in cs})
    carrier_names: dict[str, str] = {}
    if carrier_ids:
        carrier_names = {
            str(pk): name or ""
            for pk, name in read_scope.node_relation(scope, None, db_alias=db_alias)
            .filter(pk__in=carrier_ids)
            .values_list("pk", "name")
        }
    vuln_ids = sorted({v for vs in concerns.values() for v in vs})
    details: dict[str, tuple[str, str, float | None]] = {}
    if vuln_ids:
        for row in read_scope.node_relation(scope, ComplianceVulnerability, db_alias=db_alias).filter(entity_id__in=vuln_ids):
            details[str(row.entity_id)] = (row.vuln_id, row.title or "", row.cvss_score)

    def best(finding: str) -> str:
        known = [v for v in concerns[finding] if v in details]
        return min(known, key=lambda v: (-(details[v][2] if details[v][2] is not None else -1.0), details[v][0], v))

    rows: list[dict[str, Any]] = []
    for root, found in by_root.items():
        for finding in found:
            vuln = best(finding)
            vid, title, cvss = details[vuln]
            score = "n/a" if cvss is None else f"{cvss:g}"
            rows.append(
                {
                    "entity_id": root,
                    "name": f"{vid} | CVSS {score} | {title}" if title else f"{vid} | CVSS {score}",
                    "id": vid,
                    "cvss": cvss,
                    "title": title,
                    "finding_id": finding,
                    "component": _component(
                        {n for c in via[(root, finding)] if (n := carrier_names.get(c, "").strip())}
                    ),
                }
            )
    rows.sort(key=lambda r: (-(r["cvss"] if r["cvss"] is not None else -1.0), r["id"], r["finding_id"]))
    return _envelope(rows[:max_results])
