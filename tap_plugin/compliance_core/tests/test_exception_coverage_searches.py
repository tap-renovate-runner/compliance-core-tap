"""Exception coverage and review-due Search runners (`req-compliance-core-exception-coverage`).

Each test builds a real graph through the service layer: one exception that grants one instance, the instance exempting
one vulnerability, scoped to two anchors and covering one finding that concerns that vulnerability. The baseline is
covered at AS_OF; every other test breaks one thing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.searches.exception_coverage import (
    exceptions_due_review,
    finding_exception_coverage,
)

from tap_grid.models import Entity, Search
from tap_grid.search import execute_search
from tap_grid.services import create_edge, create_node, delete_edge_by_entity, delete_node, replace_node

CC = "compliance_core__compliance_"
GRANTS = "GRANTS_COMPLIANCE_EXCEPTION_INSTANCE__compliance_core"
EXEMPTS = "EXEMPTS_COMPLIANCE_VULNERABILITY__compliance_core"
SCOPED = "SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET__compliance_core"
COVERS = "COVERS_COMPLIANCE_FINDING__compliance_core"
CONCERNS = "CONCERNS_COMPLIANCE_VULNERABILITY__compliance_core"
KEY = "tap_plugin.compliance_core.searches.exception_coverage"

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])

AS_OF = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def iso(delta: timedelta) -> str:
    return (AS_OF + delta).isoformat().replace("+00:00", "Z")


def _node(type_slug: str, payload: dict[str, Any]) -> Entity:
    result = create_node(type_slug, payload)
    assert result.success, result.errors  # nosec B101
    return Entity.objects.get(pk=result.entity_id)


EXCEPTION_OK = {
    "source": "test",
    "source_key": "rule-1",
    "name": "rule-1",
    "kind": "mitigated",
    "status": "active",
    "granted_at": iso(timedelta(days=-30)),
    "review_by": iso(timedelta(days=60)),
    "expires_at": iso(timedelta(days=90)),
    "verify_within_hours": 24,
}
INSTANCE_OK = {
    "source": "test",
    "source_key": "rule-1/CVE-1",
    "name": "rule-1 CVE-1",
    "anchor_count": 2,
    "outcome": "held",
    "verified_at": iso(timedelta(hours=-1)),
}


class Case:
    """The covered baseline, with each part replaceable before it is wired."""

    def __init__(self, exception: dict[str, Any] | None = None, instance: dict[str, Any] | None = None, key: str = "1") -> None:
        self.exc = _node(f"{CC}exception", {**EXCEPTION_OK, "source_key": f"rule-{key}", "name": f"rule-{key}", **(exception or {})})
        self.inst = _node(
            f"{CC}exception_instance",
            {**INSTANCE_OK, "source_key": f"rule-{key}/CVE-{key}", "name": f"rule-{key} CVE-{key}", **(instance or {})},
        )
        self.vuln = _node(f"{CC}vulnerability", {"vuln_id": f"CVE-{key}", "title": "t"})
        self.finding = _node(f"{CC}finding", {"source": "test", "source_key": f"f{key}", "name": f"f{key}"})
        self.anchors = [
            _node(f"{CC}artifact", {"name": f"a{n}-{key}", "kind": "iiw", "source": "test", "source_key": f"a{n}-{key}"})
            for n in (1, 2)
        ]
        self.grants = create_edge(self.exc, self.inst, GRANTS)
        self.exempts = create_edge(self.inst, self.vuln, EXEMPTS)
        self.scoped = [create_edge(self.inst, a, SCOPED) for a in self.anchors]
        self.covers = create_edge(self.inst, self.finding, COVERS)
        self.concerns = create_edge(self.finding, self.vuln, CONCERNS)


def rows(inputs: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    out = finding_exception_coverage(Search(), {"as_of": AS_OF.isoformat(), **(inputs or {})}, db_alias="default")
    return {r["entity_id"]: r for r in out["rows"]}


def verdict(case: Case, inputs: dict[str, Any] | None = None) -> tuple[bool, str]:
    row = rows(inputs)[str(case.finding.pk)]
    return row["covered"], row["reason"]


class TestRegistration:
    @pytest.mark.spec("req-compliance-core-exception-coverage-1")
    def test_both_runners_are_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        assert get_search_runner(f"{KEY}:finding-exception-coverage") is finding_exception_coverage
        assert get_search_runner(f"{KEY}:exceptions-due-review") is exceptions_due_review

    @pytest.mark.spec("req-compliance-core-exception-coverage-1")
    def test_a_module_search_runs_through_the_search_service(self) -> None:
        case = Case()
        search = Search(
            search_type="module",
            root="node",
            name="coverage",
            definition={"runner_key": f"{KEY}:finding-exception-coverage"},
            input_schema={"type": "object", "properties": {"as_of": {"type": "string", "default": AS_OF.isoformat()}}},
        )
        envelope = execute_search(search, {})
        assert envelope["nodes"] == [] and envelope["edges"] == []
        assert [r["entity_id"] for r in envelope["rows"]] == [str(case.finding.pk)]
        json.dumps(envelope["rows"])


class TestConditions:
    @pytest.mark.spec("req-compliance-core-exception-coverage-2")
    def test_the_baseline_is_covered(self) -> None:
        case = Case()
        row = rows()[str(case.finding.pk)]
        assert row == {
            "entity_id": str(case.finding.pk),
            "covered": True,
            "instance_id": str(case.inst.pk),
            "exception_id": str(case.exc.pk),
            "reason": "covered",
        }

    @pytest.mark.spec("req-compliance-core-exception-coverage-2")
    def test_condition_2_a_resolved_finding_has_no_row(self) -> None:
        case = Case()
        done = replace_node(case.finding.pk, {"source": "test", "source_key": "f1", "name": "f1", "status": "resolved"})
        assert done.success, done.errors
        assert str(case.finding.pk) not in rows()

    @pytest.mark.spec("req-compliance-core-exception-coverage-2")
    def test_condition_3_a_different_vulnerability_is_not_covered(self) -> None:
        case = Case()
        other = _node(f"{CC}vulnerability", {"vuln_id": "CVE-OTHER", "title": "o"})
        delete_edge_by_entity(str(case.concerns.entity_id), reason="operator")
        create_edge(case.finding, other, CONCERNS)
        assert verdict(case) == (False, "condition 3: finding concerns the exempted vulnerability")

    @pytest.mark.spec("req-compliance-core-exception-coverage-3")
    def test_condition_3_an_instance_with_no_vulnerability_covers_nothing(self) -> None:
        case = Case()
        delete_edge_by_entity(str(case.exempts.entity_id), reason="operator")
        assert verdict(case)[1].startswith("condition 3")

    @pytest.mark.spec("req-compliance-core-exception-coverage-3")
    def test_condition_3_an_instance_that_exempts_two_vulnerabilities_covers_nothing(self) -> None:
        case = Case()
        create_edge(case.inst, _node(f"{CC}vulnerability", {"vuln_id": "CVE-2", "title": "2"}), EXEMPTS)
        assert verdict(case)[1].startswith("condition 3")

    @pytest.mark.spec("req-compliance-core-exception-coverage-2")
    @pytest.mark.parametrize("outcome", ["falsified", None])
    def test_condition_4_only_held_covers(self, outcome: str | None) -> None:
        case = Case(instance={"outcome": outcome})
        assert verdict(case) == (False, "condition 4: instance outcome is held")

    @pytest.mark.spec("req-compliance-core-exception-coverage-3")
    @pytest.mark.parametrize(
        ("instance", "exception"),
        [({"verified_at": None}, {}), ({}, {"verify_within_hours": None})],
        ids=["no check time", "no verify window"],
    )
    def test_condition_5_unset_is_not_fresh(self, instance: dict[str, Any], exception: dict[str, Any]) -> None:
        assert verdict(Case(exception=exception, instance=instance))[1].startswith("condition 5")

    @pytest.mark.spec("req-compliance-core-exception-coverage-4")
    def test_condition_5_stale_is_not_covered_and_inside_the_window_is(self) -> None:
        assert verdict(Case(instance={"verified_at": iso(timedelta(hours=-25))}))[1].startswith("condition 5")
        assert verdict(Case(instance={"verified_at": iso(timedelta(hours=-23))}, key="2")) == (True, "covered")

    @pytest.mark.spec("req-compliance-core-exception-coverage-4")
    def test_condition_5_exactly_at_the_window_edge_still_counts(self) -> None:
        assert verdict(Case(instance={"verified_at": iso(timedelta(hours=-24))}))[0] is True

    @pytest.mark.spec("req-compliance-core-exception-coverage-10")
    @pytest.mark.parametrize("ahead", [timedelta(minutes=1), timedelta(days=365)])
    def test_condition_5_a_future_check_time_is_unverified(self, ahead: timedelta) -> None:
        case = Case(instance={"verified_at": iso(ahead)})
        assert verdict(case) == (False, "condition 5: instance check is fresh")

    @pytest.mark.spec("req-compliance-core-exception-coverage-2")
    @pytest.mark.parametrize(
        "exception",
        [{"kind": None}, {"status": "revoked"}, {"status": "expired"}],
        ids=["no kind", "revoked", "expired status"],
    )
    def test_condition_6_the_exception_must_be_a_live_active_decision(self, exception: dict[str, Any]) -> None:
        assert verdict(Case(exception=exception)) == (False, "condition 6: exception is live, active, granted and unexpired")

    @pytest.mark.spec("req-compliance-core-exception-coverage-12")
    @pytest.mark.parametrize("granted", [None, timedelta(days=1)], ids=["null", "future"])
    def test_condition_6_coverage_does_not_begin_before_the_grant(self, granted: timedelta | None) -> None:
        case = Case(exception={"granted_at": None if granted is None else iso(granted)})
        assert verdict(case)[1].startswith("condition 6")

    @pytest.mark.spec("req-compliance-core-exception-coverage-12")
    def test_condition_6_granted_exactly_at_as_of_can_cover(self) -> None:
        assert verdict(Case(exception={"granted_at": iso(timedelta(0))}))[0] is True

    @pytest.mark.spec("req-compliance-core-exception-coverage-5")
    def test_condition_6_expiry_is_computed_not_trusted_from_status(self) -> None:
        case = Case(exception={"status": "active", "expires_at": iso(timedelta(seconds=-1))})
        assert verdict(case)[1].startswith("condition 6")

    @pytest.mark.spec("req-compliance-core-exception-coverage-5")
    def test_condition_6_no_ceiling_means_no_expiry(self) -> None:
        assert verdict(Case(exception={"expires_at": None}))[0] is True

    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    def test_a_tombstoned_exception_covers_nothing(self) -> None:
        case = Case()
        assert delete_node(case.exc.pk).success
        # With no live exception there is no verify window either, so the first failing condition is 5.
        covered, reason = verdict(case)
        assert covered is False and reason.startswith("condition")

    @pytest.mark.spec("req-compliance-core-exception-coverage-2")
    def test_condition_7_fewer_anchors_than_declared_is_not_covered(self) -> None:
        case = Case(instance={"anchor_count": 3})
        assert verdict(case) == (False, "condition 7: instance has its declared anchors")

    @pytest.mark.spec("req-compliance-core-exception-coverage-6")
    def test_condition_7_a_lost_anchor_never_widens_the_scope(self) -> None:
        case = Case()
        assert verdict(case)[0] is True
        assert delete_node(case.anchors[0].pk).success
        assert verdict(case) == (False, "condition 7: instance has its declared anchors")

    @pytest.mark.spec("req-compliance-core-exception-coverage-3")
    def test_condition_7_an_instance_with_no_anchor_covers_nothing_even_if_it_declares_zero(self) -> None:
        """The model refuses anchor_count 0; the runner does not rely on that (a row edited under it)."""
        from tap_plugin.compliance_core.models import ComplianceExceptionInstance

        case = Case()
        for edge in case.scoped:
            delete_edge_by_entity(str(edge.entity_id), reason="operator")
        ComplianceExceptionInstance.objects.filter(entity=case.inst).update(anchor_count=0)
        assert verdict(case) == (False, "condition 7: instance has its declared anchors")

    @pytest.mark.spec("req-compliance-core-exception-coverage-6")
    def test_a_scope_edge_from_a_non_instance_is_never_read(self) -> None:
        """The scope edge is permitted from a finding (permission union); coverage reads it only from the instance."""
        case = Case(instance={"anchor_count": 3})
        create_edge(case.finding, _node(f"{CC}artifact", {"name": "third", "kind": "iiw", "source": "t", "source_key": "third"}), SCOPED)
        assert verdict(case) == (False, "condition 7: instance has its declared anchors")

    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    def test_condition_8_a_tombstoned_instance_covers_nothing(self) -> None:
        case = Case()
        assert delete_node(case.inst.pk).success
        assert str(case.finding.pk) not in rows()

    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    def test_a_retired_cover_edge_leaves_no_row(self) -> None:
        case = Case()
        delete_edge_by_entity(str(case.covers.entity_id), reason="operator")
        assert str(case.finding.pk) not in rows()


class TestSeveralInstances:
    @pytest.mark.spec("req-compliance-core-exception-coverage-7")
    def test_one_covering_instance_among_failing_ones_is_enough(self) -> None:
        case = Case()
        second = Case(instance={"outcome": "falsified"}, key="2")
        create_edge(second.inst, case.finding, COVERS)
        create_edge(case.finding, second.vuln, CONCERNS)
        row = rows()[str(case.finding.pk)]
        assert row["covered"] is True and row["instance_id"] == str(case.inst.pk)

    @pytest.mark.spec("req-compliance-core-exception-coverage-7")
    def test_two_failing_instances_report_the_closer_one(self) -> None:
        far = Case(instance={"outcome": "falsified", "verified_at": None}, key="1")
        near = Case(instance={"outcome": "falsified"}, key="2")
        # `near` fails only condition 4; `far` fails 4 and 5. Bind both to far's finding.
        create_edge(near.inst, far.finding, COVERS)
        create_edge(far.finding, near.vuln, CONCERNS)
        row = rows()[str(far.finding.pk)]
        assert row["covered"] is False
        assert row["instance_id"] == str(near.inst.pk)
        assert row["reason"] == "condition 4: instance outcome is held"

    @pytest.mark.spec("req-compliance-core-exception-coverage-7")
    def test_a_tie_breaks_on_the_lower_instance_id(self) -> None:
        first = Case(instance={"outcome": "falsified"}, key="1")
        second = Case(instance={"outcome": "falsified"}, key="2")
        create_edge(second.inst, first.finding, COVERS)
        create_edge(first.finding, second.vuln, CONCERNS)
        row = rows()[str(first.finding.pk)]
        assert row["instance_id"] == min(str(first.inst.pk), str(second.inst.pk))


class TestOtherFindingsAndLimits:
    @pytest.mark.spec("req-compliance-core-exception-coverage-2")
    def test_entity_id_limits_to_one_finding(self) -> None:
        a, b = Case(key="1"), Case(key="2")
        assert set(rows()) == {str(a.finding.pk), str(b.finding.pk)}
        assert set(rows({"entity_id": str(b.finding.pk)})) == {str(b.finding.pk)}

    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    def test_max_results_limits_the_rows(self) -> None:
        for key in ("1", "2", "3"):
            Case(key=key)
        assert len(finding_exception_coverage(Search(), {"as_of": AS_OF.isoformat(), "max_results": 2}, db_alias="default")["rows"]) == 2

    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    def test_a_finding_with_no_instance_has_no_row(self) -> None:
        loose = _node(f"{CC}finding", {"source": "test", "source_key": "loose", "name": "loose"})
        assert str(loose.pk) not in rows()

    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    def test_the_runner_writes_nothing(self) -> None:
        Case()
        before = (Entity.objects.count(), Entity.objects.filter(deleted_at__isnull=False).count())
        rows()
        exceptions_due_review(Search(), {"as_of": AS_OF.isoformat()}, db_alias="default")
        assert (Entity.objects.count(), Entity.objects.filter(deleted_at__isnull=False).count()) == before


class TestDueReview:
    def due(self, extra: dict[str, Any] | None = None) -> dict[str, list[str]]:
        out = exceptions_due_review(Search(), {"as_of": AS_OF.isoformat(), **(extra or {})}, db_alias="default")
        return {r["name"]: r["reasons"] for r in out["rows"]}

    @pytest.mark.spec("req-compliance-core-exception-coverage-8")
    def test_each_reason_and_the_clean_exception(self) -> None:
        Case(key="clean")
        Case(exception={"review_by": iso(timedelta(days=-1))}, key="overdue")
        Case(exception={"review_by": None}, key="undated")
        Case(exception={"expires_at": iso(timedelta(days=-1))}, key="expired")
        Case(exception={"verify_within_hours": None}, key="nowindow")
        assert self.due() == {
            "rule-overdue": ["review-overdue"],
            "rule-undated": ["no-review-date"],
            "rule-expired": ["expired"],
            "rule-nowindow": ["no-verify-window"],
        }

    @pytest.mark.spec("req-compliance-core-exception-coverage-8")
    def test_reasons_accumulate_and_instances_are_counted(self) -> None:
        case = Case(exception={"review_by": None, "verify_within_hours": None}, key="x")
        extra = _node(f"{CC}exception_instance", {**INSTANCE_OK, "source_key": "rule-x/second", "name": "second"})
        create_edge(case.exc, extra, GRANTS)
        out = exceptions_due_review(Search(), {"as_of": AS_OF.isoformat()}, db_alias="default")["rows"]
        assert [(r["reasons"], r["instance_count"]) for r in out] == [(["no-review-date", "no-verify-window"], 2)]

    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    def test_a_tombstoned_exception_is_not_listed(self) -> None:
        case = Case(exception={"review_by": None}, key="gone")
        assert delete_node(case.exc.pk).success
        assert self.due() == {}


class TestInputs:
    @pytest.mark.spec("req-compliance-core-exception-coverage-9")
    @pytest.mark.parametrize(
        ("bad", "match"),
        [
            ({"as_of": "yesterday"}, "as_of"),
            ({"as_of": "2026-10-20"}, "as_of"),
            ({"as_of": "2026-10-20T12:00:00"}, "as_of"),
            ({"as_of": 7}, "as_of"),
            ({"entity_id": 7}, "entity_id"),
            ({"entity_id": ""}, "entity_id"),
            ({"max_results": 0}, "max_results"),
            ({"max_results": 5001}, "max_results"),
            ({"max_results": True}, "max_results"),
            ({"max_results": "9"}, "max_results"),
        ],
    )
    @pytest.mark.parametrize("runner", [finding_exception_coverage, exceptions_due_review])
    def test_a_bad_input_is_refused_naming_it(self, runner: Any, bad: dict[str, Any], match: str) -> None:
        if runner is exceptions_due_review and "entity_id" in bad:
            pytest.skip("exceptions-due-review takes no entity_id")
        with pytest.raises(ValueError, match=match):
            runner(Search(), bad, db_alias="default")
