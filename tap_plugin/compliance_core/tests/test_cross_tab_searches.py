"""Vulnerability cross-tab Search runners (`req-compliance-core-searches`).

The graph is built fresh per test through the service layer, with real nodes and edges:

    carriers   alpha (exception), beta (artifact), gamma (exception), delta (exception),
               tomb (exception), excl (boundary - the excluded type)
    vulns      V9 cvss 9.8 KEV | V7 cvss 7.0 | V69 cvss 6.9 | V4 cvss 4.0 | V39 cvss 3.9 |
               VN no score | VC, VX (only ever reached through a closed / excluded finding)
    open findings   alpha: V9 V7 V69 V4 V39 VN   beta: V9 VN   gamma: V7   delta: V7
                    tomb: V9 (then retired)    excl: V9 VX
    closed finding  beta: VC
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.searches.cross_tabs import component_severity, vulnerability_components

from tap_grid.models import Edge, Entity, Search
from tap_grid.registry import get_model_class
from tap_grid.search import execute_search
from tap_grid.services import create_edge, create_node, delete_edge_by_entity, delete_node

CC = "compliance_core__compliance_"
EXCLUDED = "compliance_core__compliance_boundary"
CARRIES = "CARRIES_COMPLIANCE_FINDING__compliance_core"
CONCERNS = "CONCERNS_COMPLIANCE_VULNERABILITY__compliance_core"
KEY = "tap_plugin.compliance_core.searches.cross_tabs"

VULNS: dict[str, dict[str, Any]] = {
    "V9": {"vuln_id": "CVE-9", "title": "nine", "cvss_score": 9.8, "kev": True, "published_at": "2026-01-02T03:04:05+00:00"},
    "V7": {"vuln_id": "CVE-7", "title": "seven", "cvss_score": 7.0, "kev": False},
    "V69": {"vuln_id": "CVE-6.9", "title": "six nine", "cvss_score": 6.9},
    "V4": {"vuln_id": "CVE-4", "title": "four", "cvss_score": 4.0},
    "V39": {"vuln_id": "CVE-3.9", "title": "three nine", "cvss_score": 3.9},
    "VN": {"vuln_id": "CVE-NULL", "title": "unscored"},
    "VC": {"vuln_id": "CVE-CLOSED", "cvss_score": 8.0},
    "VX": {"vuln_id": "CVE-EXCLUDED", "cvss_score": 8.5},
}
CARRIERS: dict[str, tuple[str, dict[str, Any]]] = {
    "alpha": (f"{CC}exception", {"name": "alpha"}),
    "beta": (f"{CC}artifact", {"name": "beta", "kind": "iiw"}),
    "gamma": (f"{CC}exception", {"name": "gamma"}),
    "delta": (f"{CC}exception", {"name": "delta"}),
    "tomb": (f"{CC}exception", {"name": "tomb"}),
    "excl": (EXCLUDED, {"name": "excl"}),
}
OPEN = {
    "alpha": ["V9", "V7", "V69", "V4", "V39", "VN"],
    "beta": ["V9", "VN"],
    "gamma": ["V7"],
    "delta": ["V7"],
    "tomb": ["V9"],
    "excl": ["V9", "VX"],
}
CLOSED = {"beta": ["VC"]}
INPUTS = {"exclude_types": [EXCLUDED]}


def _node(type_slug: str, payload: dict[str, Any]) -> Entity:
    result = create_node(type_slug, payload)
    assert result.success, result.errors  # nosec B101
    return Entity.objects.get(pk=result.entity_id)


class Graph:
    def __init__(self) -> None:
        self.vulns = {k: _node(f"{CC}vulnerability", v) for k, v in VULNS.items()}
        self.carriers = {k: _node(t, p) for k, (t, p) in CARRIERS.items()}
        self.carry_edges: dict[tuple[str, str], Edge] = {}
        self.findings: dict[tuple[str, str], Entity] = {}
        for status, table in (("open", OPEN), ("resolved", CLOSED)):
            for carrier, vulns in table.items():
                for v in vulns:
                    finding = _node(f"{CC}finding", {"name": f"{carrier}-{v}", "status": status})
                    self.findings[(carrier, v)] = finding
                    self.carry_edges[(carrier, v)] = create_edge(self.carriers[carrier], finding, CARRIES)
                    create_edge(finding, self.vulns[v], CONCERNS)


def vulns(**kw: Any) -> list[dict[str, Any]]:
    return vulnerability_components(Search(), kw.get("inputs", INPUTS), db_alias="default")["rows"]


def components(**kw: Any) -> list[dict[str, Any]]:
    return component_severity(Search(), kw.get("inputs", INPUTS), db_alias="default")["rows"]


def by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {r[key]: r for r in rows}


pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


class TestRegistration:
    @pytest.mark.spec("req-compliance-core-searches-1")
    def test_both_runners_are_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        assert get_search_runner(f"{KEY}:vulnerability-components") is vulnerability_components
        assert get_search_runner(f"{KEY}:component-severity") is component_severity

    @pytest.mark.spec("req-compliance-core-searches-2")
    @pytest.mark.parametrize("key", ["vulnerability-components", "component-severity"])
    def test_a_module_search_runs_through_the_search_service(self, key: str) -> None:
        Graph()
        search = Search(
            search_type="module",
            root="node",
            name=key,
            definition={"runner_key": f"{KEY}:{key}"},
            input_schema={
                "type": "object",
                "properties": {"exclude_types": {"type": "array", "items": {"type": "string"}, "default": [EXCLUDED]}},
            },
        )
        envelope = execute_search(search, {})
        assert envelope["nodes"] == [] and envelope["edges"] == []
        assert isinstance(envelope["info"], dict) and isinstance(envelope["warnings"], dict)
        assert envelope["rows"], "the read-only search connection saw no rows"
        json.dumps(envelope["rows"])  # every value is JSON-serialisable
        # the schema default excluded the boundary carrier
        names = {r.get("component") for r in envelope["rows"]} | {
            n for r in envelope["rows"] for n in r.get("component_names", "").split(", ")
        }
        assert "excl" not in names

    @pytest.mark.spec("req-compliance-core-searches-8")
    @pytest.mark.parametrize("bad", ["excluded", [1], {"a": 1}])
    def test_exclude_types_must_be_strings(self, bad: Any) -> None:
        with pytest.raises(ValueError, match="exclude_types"):
            vulnerability_components(Search(), {"exclude_types": bad}, db_alias="default")
        with pytest.raises(ValueError, match="exclude_types"):
            component_severity(Search(), {"exclude_types": bad}, db_alias="default")


class TestVulnerabilityComponents:
    @pytest.mark.spec("req-compliance-core-searches-5")
    def test_rows_fields_and_order(self) -> None:
        Graph()
        rows = vulns()
        # cvss descending, nulls last; the closed-only (VC) and excluded-only (VX) vulns are absent
        assert [r["id"] for r in rows] == ["CVE-9", "CVE-7", "CVE-6.9", "CVE-4", "CVE-3.9", "CVE-NULL"]
        nine, seven, unscored = rows[0], rows[1], rows[-1]
        assert nine == {
            "id": "CVE-9",
            "title": "nine",
            "cvss": 9.8,
            "kev": True,
            "published": "2026-01-02T03:04:05+00:00",
            "components": 3,  # alpha, beta, tomb - excl is excluded
            "component_names": "alpha, beta, tomb",
        }
        assert seven["components"] == 3 and seven["component_names"] == "alpha, delta, gamma"  # two carriers share it
        assert seven["kev"] is False and seven["published"] is None
        assert unscored["cvss"] is None and unscored["kev"] is False  # null kev reads as false
        assert all(isinstance(r["components"], int) for r in rows)
        json.dumps(rows)

    @pytest.mark.spec("req-compliance-core-searches-3")
    def test_closed_findings_and_excluded_carriers_are_not_counted(self) -> None:
        Graph()
        ids = {r["id"] for r in vulns()}
        assert "CVE-CLOSED" not in ids and "CVE-EXCLUDED" not in ids
        assert "excl" not in by(vulns(), "id")["CVE-9"]["component_names"]
        # without the exclusion input the boundary carrier counts and its vulnerability appears
        everything = by(vulns(inputs={}), "id")
        assert "excl" in everything["CVE-9"]["component_names"]
        assert "CVE-EXCLUDED" in everything and "CVE-CLOSED" not in everything

    @pytest.mark.spec("req-compliance-core-searches-5")
    def test_equal_scores_order_by_id(self) -> None:
        g = Graph()
        for vid in ("CVE-B-TIE", "CVE-A-TIE"):
            tie = _node(f"{CC}vulnerability", {"vuln_id": vid, "cvss_score": 5.5})
            finding = _node(f"{CC}finding", {"name": vid, "status": "open"})
            create_edge(g.carriers["gamma"], finding, CARRIES)
            create_edge(finding, tie, CONCERNS)
        ids = [r["id"] for r in vulns()]
        assert ids.index("CVE-A-TIE") + 1 == ids.index("CVE-B-TIE")


class TestComponentSeverity:
    @pytest.mark.spec("req-compliance-core-searches-6")
    def test_boundaries_and_unscored(self) -> None:
        g = Graph()
        rows = by(components(), "component")
        # 9.8 and 7.0 are high (the boundary is inclusive); 6.9 and 4.0 medium; 3.9 low; none unscored-in-a-band
        assert rows["alpha"] == {
            "cid": str(g.carriers["alpha"].pk),
            "component": "alpha",
            "type": f"{CC}exception",
            "high": 2,
            "medium": 2,
            "low": 1,
            "unscored": 1,
            "kev": 1,
            "total": 6,
        }
        assert rows["beta"]["type"] == f"{CC}artifact"
        assert (rows["beta"]["high"], rows["beta"]["medium"], rows["beta"]["low"]) == (1, 0, 0)
        assert (rows["beta"]["unscored"], rows["beta"]["kev"], rows["beta"]["total"]) == (1, 1, 2)  # VC is closed
        for r in rows.values():
            assert r["high"] + r["medium"] + r["low"] + r["unscored"] == r["total"]
            assert all(isinstance(r[k], int) for k in ("high", "medium", "low", "unscored", "kev", "total"))
        json.dumps(list(rows.values()))

    @pytest.mark.spec("req-compliance-core-searches-3")
    def test_excluded_carrier_has_no_row(self) -> None:
        Graph()
        assert "excl" not in by(components(), "component")
        assert "excl" in by(components(inputs={}), "component")

    @pytest.mark.spec("req-compliance-core-searches-7")
    def test_order(self) -> None:
        Graph()
        # kev desc (alpha 1, beta 1, tomb 1), high desc (alpha 2, beta 1, tomb 1), total desc, then name
        assert [r["component"] for r in components()] == ["alpha", "beta", "tomb", "delta", "gamma"]


class TestReadScope:
    """A retired element contributes nothing, however it was retired."""

    @pytest.mark.spec("req-compliance-core-searches-4")
    def test_a_retired_carrier_is_gone(self) -> None:
        g = Graph()
        assert by(vulns(), "id")["CVE-9"]["components"] == 3
        result = delete_node(str(g.carriers["tomb"].pk), reason="operator")
        assert result.success, result.errors  # nosec B101
        assert "tomb" not in by(components(), "component")
        nine = by(vulns(), "id")["CVE-9"]
        assert (nine["components"], nine["component_names"]) == (2, "alpha, beta")

    @pytest.mark.spec("req-compliance-core-searches-4")
    def test_a_retired_carries_edge_is_gone(self) -> None:
        g = Graph()
        result = delete_edge_by_entity(str(g.carry_edges[("tomb", "V9")].entity_id), reason="operator")
        assert result.success, result.errors  # nosec B101
        assert "tomb" not in by(components(), "component")
        assert by(vulns(), "id")["CVE-9"]["components"] == 2

    @pytest.mark.spec("req-compliance-core-searches-4")
    def test_a_retired_concerns_edge_is_gone(self) -> None:
        g = Graph()
        concerns = Edge.objects.get(from_entity=g.findings[("alpha", "V4")], edge_type=CONCERNS)
        result = delete_edge_by_entity(str(concerns.entity_id), reason="operator")
        assert result.success, result.errors  # nosec B101
        alpha = by(components(), "component")["alpha"]
        assert (alpha["medium"], alpha["total"]) == (1, 5)
        assert "CVE-4" not in {r["id"] for r in vulns()}

    @pytest.mark.spec("req-compliance-core-searches-4")
    @pytest.mark.parametrize("what", ["finding", "vulnerability"])
    def test_a_tombstoned_endpoint_with_live_edges_is_gone(self, what: str) -> None:
        """The write path ends a retired node's edges; the read must not rely on that."""
        from django.utils import timezone

        g = Graph()
        victim = g.findings[("alpha", "V4")] if what == "finding" else g.vulns["V4"]
        Entity.objects.filter(pk=victim.pk).update(deleted_at=timezone.now())
        alpha = by(components(), "component")["alpha"]
        assert (alpha["medium"], alpha["total"]) == (1, 5)
        assert "CVE-4" not in {r["id"] for r in vulns()}

    @pytest.mark.spec("req-compliance-core-searches-4")
    def test_a_tombstoned_carrier_with_live_edges_is_gone(self) -> None:
        from django.utils import timezone

        g = Graph()
        Entity.objects.filter(pk=g.carriers["tomb"].pk).update(deleted_at=timezone.now())
        assert "tomb" not in by(components(), "component")
        assert by(vulns(), "id")["CVE-9"]["components"] == 2


def test_the_vulnerability_model_resolves() -> None:
    """Guard the lowercase-class-name join path the runners rely on."""
    for cls_slug, name in ((f"{CC}finding", "compliancefinding"), (f"{CC}vulnerability", "compliancevulnerability")):
        assert get_model_class(cls_slug).__name__.lower() == name
