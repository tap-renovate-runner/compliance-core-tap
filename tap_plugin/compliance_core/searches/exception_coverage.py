"""Whether a finding is covered by an exception, and which exceptions are due for review, as `module` Search runners
(`req-compliance-core-exception-coverage`).

Coverage is computed when asked, from facts, and never stored. The runners use Django ORM reads and the standard
library's ``datetime`` under the read rules Gryphon applies (``tap_grid.gryphon.read_scope``: the scoped edge
relation, so a tombstoned node or edge contributes nothing; the caller's ``db_alias`` for every query). Neither
writes.

``finding-exception-coverage`` inputs: ``entity_id`` (optional, one finding), ``as_of`` (optional ISO date-time with a
UTC offset; default now), ``max_results`` (1 to 5000, default 1000). One row per open finding with at least one
``COVERS_COMPLIANCE_FINDING`` edge from an exception instance: ``entity_id`` (the finding), ``covered``,
``instance_id``, ``exception_id``, ``reason``. An instance covers a finding only when every condition below holds;
a finding with several instances is covered if any covers, and otherwise reports the instance that passes the most
conditions (ties break on instance id). ``reason`` is ``covered``, or ``condition <n>: <name>`` for the first failing
condition of that instance.

    1  a live COVERS edge runs from the instance to the finding     (how a row exists at all)
    2  the finding's status is open                                  (how a row exists at all)
    3  the finding concerns the one vulnerability the instance exempts
    4  the instance's outcome is held
    5  verified_at is set, not after as_of, and within the exception's verify_within_hours (which must be set)
    6  the exception is live, has a kind, is active, was granted by as_of and has not expired
    7  the instance has at least anchor_count live scope anchors
    8  nothing on the path is tombstoned                              (read scope: a tombstone is never read, so it
                                                                      surfaces as the condition its absence breaks)

Null or stale anywhere means uncovered. That a live anchor actually reaches the covered finding is NOT checked: the
checker's binding is trusted (``req-compliance-core-exception-coverage-11``, Backlog).

``exceptions-due-review`` inputs: ``as_of``, ``max_results``. One row per live exception with at least one reason:
``review-overdue`` (``review_by`` before ``as_of``), ``no-review-date``, ``expired`` (``expires_at`` at or before
``as_of``), ``no-verify-window``. Row: ``entity_id`` (the exception), ``name``, ``reasons`` (list),
``instance_count`` (its live instances).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from tap_grid.gryphon import read_scope
from tap_grid.models import Search

from ..models.compliance_exception import ComplianceException
from ..models.compliance_exception_instance import ComplianceExceptionInstance
from ..models.compliance_finding import ComplianceFinding
from ..models.compliance_vulnerability import ComplianceVulnerability

COVERS_EDGE = "COVERS_COMPLIANCE_FINDING__compliance_core"
CONCERNS_EDGE = "CONCERNS_COMPLIANCE_VULNERABILITY__compliance_core"
GRANTS_EDGE = "GRANTS_COMPLIANCE_EXCEPTION_INSTANCE__compliance_core"
EXEMPTS_EDGE = "EXEMPTS_COMPLIANCE_VULNERABILITY__compliance_core"
SCOPED_EDGE = "SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET__compliance_core"
_FINDING_ROW = ComplianceFinding.__name__.lower()

DEFAULT_MAX_RESULTS = 1000
MAX_RESULTS = 5000

CONDITIONS = {
    3: "finding concerns the exempted vulnerability",
    4: "instance outcome is held",
    5: "instance check is fresh",
    6: "exception is live, active, granted and unexpired",
    7: "instance has its declared anchors",
}


def _envelope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"nodes": [], "edges": [], "rows": rows, "info": {"row_count": len(rows)}, "warnings": {}}


def _inputs(inputs: dict[str, Any]) -> tuple[str | None, datetime, int]:
    """Validate the inputs: ``(entity_id, as_of, max_results)``; ValueError names the bad one."""
    entity_id = inputs.get("entity_id")
    if entity_id is not None and (not isinstance(entity_id, str) or not entity_id):
        raise ValueError("entity_id must be a non-empty string when given")
    raw = inputs.get("as_of")
    if raw is None:
        as_of = datetime.now(UTC)
    else:
        if not isinstance(raw, str):
            raise ValueError("as_of must be an ISO date-time string")
        try:
            as_of = datetime.fromisoformat(raw)
        except ValueError:
            raise ValueError("as_of must be an ISO date-time string") from None
        if as_of.tzinfo is None:
            raise ValueError("as_of must include a UTC offset (a bare date or local time is ambiguous)")
    max_results = inputs.get("max_results", DEFAULT_MAX_RESULTS)
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"max_results must be an integer from 1 to {MAX_RESULTS}")
    return entity_id, as_of, max_results


def _pairs(edge_type: str, *, db_alias: str, **filters: Any) -> list[tuple[str, str]]:
    rows = (
        read_scope.edge_relation(read_scope.DEFAULT_SCOPE, db_alias=db_alias)
        .filter(edge_type=edge_type, **filters)
        .values_list("from_entity_id", "to_entity_id")
    )
    return [(str(a), str(b)) for a, b in rows]


@dataclass
class _Facts:
    """Everything one instance's conditions read, gathered in a handful of queries."""

    instance: dict[str, ComplianceExceptionInstance]
    exemptions: dict[str, set[str]]  # instance -> vulnerabilities it exempts
    anchors: dict[str, int]  # instance -> live anchors
    exceptions: dict[str, ComplianceException]  # exception id -> live row
    granted_by: dict[str, set[str]]  # instance -> live granting exceptions
    concerns: dict[str, set[str]]  # finding -> live vulnerabilities


def _gather(instance_ids: list[str], finding_ids: list[str], *, db_alias: str) -> _Facts:
    scope = read_scope.DEFAULT_SCOPE
    instances = {
        str(row.entity_id): row
        for row in read_scope.node_relation(scope, ComplianceExceptionInstance, db_alias=db_alias).filter(
            entity_id__in=instance_ids
        )
    }
    exemptions: dict[str, set[str]] = defaultdict(set)
    for instance, vuln in _pairs(
        EXEMPTS_EDGE,
        db_alias=db_alias,
        from_entity_id__in=instance_ids,
        to_entity__entity_type=ComplianceVulnerability.ENTITY_TYPE,
    ):
        exemptions[instance].add(vuln)
    anchor_targets: dict[str, set[str]] = defaultdict(set)
    for instance, target in _pairs(SCOPED_EDGE, db_alias=db_alias, from_entity_id__in=instance_ids):
        anchor_targets[instance].add(target)
    granted_by: dict[str, set[str]] = defaultdict(set)
    for exception, instance in _pairs(
        GRANTS_EDGE,
        db_alias=db_alias,
        to_entity_id__in=instance_ids,
        from_entity__entity_type=ComplianceException.ENTITY_TYPE,
    ):
        granted_by[instance].add(exception)
    exception_ids = sorted({e for es in granted_by.values() for e in es})
    exceptions = {
        str(row.entity_id): row
        for row in read_scope.node_relation(scope, ComplianceException, db_alias=db_alias).filter(
            entity_id__in=exception_ids
        )
    }
    concerns: dict[str, set[str]] = defaultdict(set)
    for finding, vuln in _pairs(
        CONCERNS_EDGE,
        db_alias=db_alias,
        from_entity_id__in=finding_ids,
        to_entity__entity_type=ComplianceVulnerability.ENTITY_TYPE,
    ):
        concerns[finding].add(vuln)
    return _Facts(instances, exemptions, {i: len(t) for i, t in anchor_targets.items()}, exceptions, granted_by, concerns)


def _exception_covers(exception: ComplianceException, as_of: datetime) -> bool:
    return bool(
        exception.kind
        and exception.status == "active"
        and exception.granted_at is not None
        and exception.granted_at <= as_of
        and (exception.expires_at is None or exception.expires_at > as_of)
    )


def _fresh(instance: ComplianceExceptionInstance, window_hours: int | None, as_of: datetime) -> bool:
    """A check time that is null, in the future, or older than the window proves nothing."""
    if window_hours is None or instance.verified_at is None or instance.verified_at > as_of:
        return False
    return as_of - instance.verified_at <= timedelta(hours=window_hours)


def _evaluate(instance_id: str, finding_id: str, facts: _Facts, as_of: datetime) -> dict[int, bool]:
    """Conditions 3 to 7 for one instance bound to one finding (1, 2 and 8 hold by construction)."""
    row = facts.instance.get(instance_id)
    exempted = facts.exemptions.get(instance_id, set())
    granters = facts.granted_by.get(instance_id, set())
    exception = facts.exceptions.get(next(iter(granters))) if len(granters) == 1 else None
    return {
        # Exactly one vulnerability: an instance that exempts none, or several, covers nothing.
        3: len(exempted) == 1 and exempted <= facts.concerns.get(finding_id, set()),
        4: row is not None and row.outcome == "held",
        5: row is not None and _fresh(row, exception.verify_within_hours if exception else None, as_of),
        6: exception is not None and _exception_covers(exception, as_of),
        7: row is not None and facts.anchors.get(instance_id, 0) >= row.anchor_count,
    }


def finding_exception_coverage(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per open finding bound to at least one instance: ``entity_id`` (the finding), ``covered``,
    ``instance_id``, ``exception_id``, ``reason``.

    req-compliance-core-exception-coverage
    """
    entity_id, as_of, max_results = _inputs(inputs)
    filters: dict[str, Any] = {
        "to_entity__entity_type": ComplianceFinding.ENTITY_TYPE,
        f"to_entity__{_FINDING_ROW}__status": "open",
        "from_entity__entity_type": ComplianceExceptionInstance.ENTITY_TYPE,
    }
    if entity_id is not None:
        filters["to_entity_id"] = entity_id
    bound: dict[str, set[str]] = defaultdict(set)  # finding -> instances bound to it
    for instance, finding in _pairs(COVERS_EDGE, db_alias=db_alias, **filters):
        bound[finding].add(instance)
    if not bound:
        return _envelope([])
    instance_ids = sorted({i for instances in bound.values() for i in instances})
    facts = _gather(instance_ids, sorted(bound), db_alias=db_alias)
    rows: list[dict[str, Any]] = []
    for finding in sorted(bound):
        best: tuple[int, str, dict[int, bool]] | None = None
        for instance in sorted(bound[finding]):
            conditions = _evaluate(instance, finding, facts, as_of)
            passed = sum(conditions.values())
            if best is None or passed > best[0]:  # sorted ascending, so a tie keeps the lower instance id
                best = (passed, instance, conditions)
        assert best is not None  # nosec B101 - bound[finding] is never empty
        _, instance, conditions = best
        failing = next((n for n in sorted(conditions) if not conditions[n]), None)
        granters = facts.granted_by.get(instance, set())
        rows.append(
            {
                "entity_id": finding,
                "covered": failing is None,
                "instance_id": instance,
                "exception_id": next(iter(granters)) if len(granters) == 1 else None,
                "reason": "covered" if failing is None else f"condition {failing}: {CONDITIONS[failing]}",
            }
        )
    return _envelope(rows[:max_results])


def exceptions_due_review(
    search: Search, inputs: dict[str, Any], *, db_alias: str, layer: str = "full"
) -> dict[str, Any]:
    """One row per live exception with a reason to look at it: ``entity_id``, ``name``, ``reasons``,
    ``instance_count``.

    req-compliance-core-exception-coverage-8
    """
    _, as_of, max_results = _inputs(inputs)
    scope = read_scope.DEFAULT_SCOPE
    exceptions = list(read_scope.node_relation(scope, ComplianceException, db_alias=db_alias))
    counts: dict[str, int] = defaultdict(int)
    for exception, _instance in _pairs(
        GRANTS_EDGE,
        db_alias=db_alias,
        from_entity_id__in=[str(e.entity_id) for e in exceptions],
        to_entity__entity_type=ComplianceExceptionInstance.ENTITY_TYPE,
    ):
        counts[exception] += 1
    rows: list[dict[str, Any]] = []
    for exception in exceptions:
        reasons = []
        if exception.review_by is None:
            reasons.append("no-review-date")
        elif exception.review_by < as_of:
            reasons.append("review-overdue")
        if exception.expires_at is not None and exception.expires_at <= as_of:
            reasons.append("expired")
        if exception.verify_within_hours is None:
            reasons.append("no-verify-window")
        if reasons:
            rows.append(
                {
                    "entity_id": str(exception.entity_id),
                    "name": exception.name,
                    "reasons": reasons,
                    "instance_count": counts.get(str(exception.entity_id), 0),
                }
            )
    rows.sort(key=lambda r: (r["name"], r["entity_id"]))
    return _envelope(rows[:max_results])
