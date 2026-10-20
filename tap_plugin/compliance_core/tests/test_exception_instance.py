"""Exception fields, the exception instance node and its edges (`req-compliance-core-exception*`).

Everything goes through the service layer, as a producer's write would.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration

from tap_grid.models import Entity
from tap_grid.registry import get_model_class
from tap_grid.services import create_edge, create_node, delete_node, replace_node

CC = "compliance_core__compliance_"
EXCEPTION = f"{CC}exception"
INSTANCE = f"{CC}exception_instance"
FINDING = f"{CC}finding"
VULN = f"{CC}vulnerability"
EVIDENCE = f"{CC}evidence"
GRANTS = "GRANTS_COMPLIANCE_EXCEPTION_INSTANCE__compliance_core"
EXEMPTS = "EXEMPTS_COMPLIANCE_VULNERABILITY__compliance_core"
SCOPED = "SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET__compliance_core"
COVERS = "COVERS_COMPLIANCE_FINDING__compliance_core"
CITES = "CITES_COMPLIANCE_EVIDENCE__compliance_core"

NEW_FIELDS = ("kind", "justification", "approver", "granted_at", "review_by", "expires_at", "verify_within_hours")
INSTANCE_PAYLOAD = {"source": "test", "source_key": "rule-1/CVE-1/pkg", "name": "rule-1 CVE-1 pkg", "anchor_count": 1}


def _node(type_slug: str, payload: dict[str, Any]) -> Entity:
    result = create_node(type_slug, payload)
    assert result.success, result.errors  # nosec B101
    return Entity.objects.get(pk=result.entity_id)


def _row(type_slug: str, entity: Entity) -> Any:
    return get_model_class(type_slug).objects.get(entity=entity)


def _ok(type_slug: str, payload: dict[str, Any]) -> bool:
    return create_node(type_slug, payload).success


@pytest.mark.django_db
class TestExceptionFields:
    def test_a_bare_exception_reads_back_with_the_new_fields_null(self) -> None:
        """req-compliance-core-exception-1: a producer that sets only a name keeps working."""
        row = _row(EXCEPTION, _node(EXCEPTION, {"name": "x"}))
        assert {f: getattr(row, f) for f in NEW_FIELDS} == dict.fromkeys(NEW_FIELDS)

    def test_every_field_round_trips(self) -> None:
        row = _row(
            EXCEPTION,
            _node(
                EXCEPTION,
                {
                    "name": "x",
                    "kind": "not-affected",
                    "justification": "vulnerable-code-not-in-execute-path",
                    "approver": "security-board",
                    "granted_at": "2026-10-01T00:00:00Z",
                    "review_by": "2027-01-01T00:00:00Z",
                    "expires_at": "2027-04-01T00:00:00Z",
                    "verify_within_hours": 24,
                },
            ),
        )
        assert row.kind == "not-affected"
        assert row.justification == "vulnerable-code-not-in-execute-path"
        assert row.expires_at.isoformat() == "2027-04-01T00:00:00+00:00"
        assert row.verify_within_hours == 24

    @pytest.mark.parametrize("kind", ["false-positive", "not-affected", "mitigated", "operational-requirement", "accepted-risk"])
    def test_the_five_kinds_are_accepted(self, kind: str) -> None:
        payload = {"name": "x", "kind": kind}
        if kind == "not-affected":
            payload["justification"] = "component-not-present"
        assert _ok(EXCEPTION, payload)

    def test_a_kind_outside_the_five_is_refused(self) -> None:
        """req-compliance-core-exception-2."""
        assert not _ok(EXCEPTION, {"name": "x", "kind": "ignored"})

    def test_a_justification_outside_the_five_labels_is_refused(self) -> None:
        assert not _ok(EXCEPTION, {"name": "x", "kind": "not-affected", "justification": "because"})

    @pytest.mark.parametrize("kind", [None, "false-positive", "mitigated", "operational-requirement", "accepted-risk"])
    def test_a_justification_with_any_other_kind_is_refused(self, kind: str | None) -> None:
        """req-compliance-core-exception-2: the whole-record rule, not a per-field one."""
        assert not _ok(EXCEPTION, {"name": "x", "kind": kind, "justification": "component-not-present"})

    def test_the_justification_rule_also_holds_on_replace(self) -> None:
        """req-compliance-core-exception-2: the whole-record hook is on the replace path, not only create."""
        entity = _node(EXCEPTION, {"name": "x", "kind": "mitigated"})
        refused = replace_node(entity.pk, {"name": "x", "kind": "mitigated", "justification": "component-not-present"})
        assert not refused.success
        accepted = replace_node(entity.pk, {"name": "x", "kind": "not-affected", "justification": "component-not-present"})
        assert accepted.success, accepted.errors

    @pytest.mark.parametrize("bad", [0, -1, 1.5, "24", True])
    def test_verify_window_must_be_a_positive_integer(self, bad: Any) -> None:
        """req-compliance-core-exception-3."""
        assert not _ok(EXCEPTION, {"name": "x", "verify_within_hours": bad})

    def test_verify_window_of_one_is_the_smallest_accepted(self) -> None:
        assert _ok(EXCEPTION, {"name": "x", "verify_within_hours": 1})

    @pytest.mark.parametrize("field", ["granted_at", "review_by", "expires_at"])
    @pytest.mark.parametrize("bad", ["soon", "2026-10-01", 7])
    def test_dates_are_instants(self, field: str, bad: Any) -> None:
        assert not _ok(EXCEPTION, {"name": "x", field: bad})

    def test_identity_is_unchanged(self) -> None:
        """req-compliance-core-exception-5."""
        assert get_model_class(EXCEPTION).NATURAL_KEY == ("source", "source_key")

    def test_instances_are_the_declared_containment(self) -> None:
        """req-compliance-core-exception-4."""
        model = get_model_class(EXCEPTION)
        assert model.CONTAINMENT_EDGES == (GRANTS,)


@pytest.mark.django_db
class TestInstanceNode:
    def test_type_key_and_dimension(self) -> None:
        """req-compliance-core-exception-instance-1."""
        model = get_model_class(INSTANCE)
        assert model.ENTITY_TYPE == INSTANCE
        assert model.NATURAL_KEY == ("source", "source_key")
        entity = _node(INSTANCE, INSTANCE_PAYLOAD)
        assert entity.dimensions == {"compliance": "exception-instance"}

    def test_outcome_and_time_start_unobserved(self) -> None:
        row = _row(INSTANCE, _node(INSTANCE, INSTANCE_PAYLOAD))
        assert (row.outcome, row.verified_at, row.detail) == (None, None, None)

    @pytest.mark.parametrize("outcome", ["held", "falsified"])
    def test_outcome_accepts_held_and_falsified(self, outcome: str) -> None:
        """req-compliance-core-exception-instance-2."""
        row = _row(INSTANCE, _node(INSTANCE, {**INSTANCE_PAYLOAD, "outcome": outcome}))
        assert row.outcome == outcome

    @pytest.mark.parametrize("bad", ["", "ok", "HELD", 1])
    def test_outcome_outside_the_two_is_refused(self, bad: Any) -> None:
        assert not _ok(INSTANCE, {**INSTANCE_PAYLOAD, "outcome": bad})

    @pytest.mark.parametrize("missing", ["anchor_count", "name"])
    def test_required_fields(self, missing: str) -> None:
        """req-compliance-core-exception-instance-3."""
        payload = {k: v for k, v in INSTANCE_PAYLOAD.items() if k != missing}
        assert not _ok(INSTANCE, payload)

    @pytest.mark.parametrize("bad", [0, -1, 1.5, "1", None])
    def test_anchor_count_is_at_least_one(self, bad: Any) -> None:
        assert not _ok(INSTANCE, {**INSTANCE_PAYLOAD, "anchor_count": bad})

    def test_verified_at_is_an_instant(self) -> None:
        assert _ok(INSTANCE, {**INSTANCE_PAYLOAD, "verified_at": "2026-10-20T01:00:00Z"})
        assert not _ok(INSTANCE, {**INSTANCE_PAYLOAD, "source_key": "k2", "verified_at": "2026-10-20"})

    def test_the_same_key_is_the_same_node(self) -> None:
        """req-compliance-core-exception-instance-4 (through the grid's own resolution of the key)."""
        from tap_grid.grift import grift_import

        def doc(outcome: str) -> dict[str, Any]:
            return {
                "metadata": {"grift_version": "0"},
                "_reserved": {},
                "batches": [
                    {
                        "batch_entity": {"entity_id": __import__("uuid").uuid4().__str__(), "entity_type": "batch", "name": "inst", "dimensions": {}},
                        "batch_node": {"name": "inst", "description": "", "description_json": None, "source": "test", "metadata": {}},
                        "nodes": [
                            {
                                "entity": {"ref": "i", "entity_type": INSTANCE, "name": INSTANCE_PAYLOAD["name"], "dimensions": {}},
                                "node": {**INSTANCE_PAYLOAD, "outcome": outcome},
                            }
                        ],
                        "edges": [],
                    }
                ],
            }

        for outcome in ("held", "falsified"):
            result = grift_import(doc(outcome))
            assert result.success, result.errors
        model = get_model_class(INSTANCE)
        assert model.objects.live().count() == 1
        assert model.objects.live().get().outcome == "falsified"


@pytest.mark.django_db
class TestEdges:
    def setup_method(self) -> None:
        self.exc = _node(EXCEPTION, {"source": "test", "source_key": "rule-1", "name": "rule-1"})
        self.inst = _node(INSTANCE, INSTANCE_PAYLOAD)
        self.vuln = _node(VULN, {"vuln_id": "CVE-1", "title": "one"})
        self.finding = _node(FINDING, {"source": "test", "source_key": "f1", "name": "f1"})
        self.evidence = _node(EVIDENCE, {"name": "e1", "kind": "scanner_output"})
        self.anchor = _node(f"{CC}artifact", {"name": "pkg:maven/log4j@2.14", "kind": "iiw", "source": "test", "source_key": "pkg"})

    def test_the_sentences_connect_and_carry_their_dimension(self) -> None:
        """req-compliance-core-exception-edges-1."""
        grants = create_edge(self.exc, self.inst, GRANTS)
        exempts = create_edge(self.inst, self.vuln, EXEMPTS)
        scoped = create_edge(self.inst, self.anchor, SCOPED)
        covers = create_edge(self.inst, self.finding, COVERS)
        dims = {e.entity.dimensions["compliance"] for e in (grants, exempts, scoped, covers)}
        assert dims == {"exception-instance", "vulnerability", "finding"}

    def test_an_anchor_may_be_any_node(self) -> None:
        """req-compliance-core-exception-edges-3."""
        for target in (self.anchor, self.finding, self.vuln, self.exc):
            create_edge(self.inst, target, SCOPED)

    def test_scoped_to_refuses_any_other_source(self) -> None:
        # Refused where a closed end forbids it. A source whose type declares no outbound edges at all
        # (a finding) is not refused, because edge validation is a permission union and an
        # unconstrained end allows everything (tap_grid/constraints.py).
        for source in (self.exc, self.vuln):
            with pytest.raises(Exception):  # noqa: B017 - the refusal type is the service layer's
                create_edge(source, self.anchor, SCOPED)

    def test_covers_moves_to_the_instance(self) -> None:
        """req-compliance-core-exception-edges-4."""
        create_edge(self.inst, self.finding, COVERS)
        with pytest.raises(Exception):  # noqa: B017
            create_edge(self.exc, self.finding, COVERS)

    def test_cites_accepts_an_instance_or_a_finding(self) -> None:
        props = {"support_kind": "passing"}
        create_edge(self.inst, self.evidence, CITES, props)
        create_edge(self.finding, self.evidence, CITES, props)
        with pytest.raises(Exception):  # noqa: B017
            create_edge(self.exc, self.evidence, CITES, props)

    @pytest.mark.parametrize(
        ("edge", "src", "dst"),
        [
            (GRANTS, "inst", "exc"),
            (GRANTS, "exc", "vuln"),
            (EXEMPTS, "vuln", "inst"),
            (COVERS, "finding", "inst"),
        ],
    )
    def test_wrong_ends_are_refused(self, edge: str, src: str, dst: str) -> None:
        """req-compliance-core-exception-instance-5."""
        ends = {"exc": self.exc, "inst": self.inst, "finding": self.finding, "vuln": self.vuln}
        with pytest.raises(Exception):  # noqa: B017
            create_edge(ends[src], ends[dst], edge)

    def test_containment_is_only_the_grant(self) -> None:
        """req-compliance-core-exception-edges-2: deleting the exception retires its instances, and only them."""
        create_edge(self.exc, self.inst, GRANTS)
        create_edge(self.inst, self.vuln, EXEMPTS)
        create_edge(self.inst, self.anchor, SCOPED)
        create_edge(self.inst, self.finding, COVERS)
        assert delete_node(self.exc.pk, cascade="contained").success
        for entity in (self.exc, self.inst):
            entity.refresh_from_db()
            assert entity.deleted_at is not None
        for entity in (self.vuln, self.anchor, self.finding):
            entity.refresh_from_db()
            assert entity.deleted_at is None

    def test_deleting_an_instance_leaves_everything_else(self) -> None:
        create_edge(self.exc, self.inst, GRANTS)
        create_edge(self.inst, self.vuln, EXEMPTS)
        create_edge(self.inst, self.finding, COVERS)
        assert delete_node(self.inst.pk, cascade="contained").success
        for entity in (self.exc, self.vuln, self.finding):
            entity.refresh_from_db()
            assert entity.deleted_at is None

    @pytest.mark.parametrize("edge", [GRANTS, EXEMPTS, SCOPED, COVERS])
    def test_edges_declare_plain_identity(self, edge: str) -> None:
        """req-compliance-core-exception-edges-6: no discriminators, so a re-sent edge is the same edge."""
        path = Path(compliance.__file__).parent.parent / "edges" / f"{edge.removesuffix('__compliance_core')}.edge.json"
        assert json.loads(path.read_text())["identity"] == {"discriminators": []}
