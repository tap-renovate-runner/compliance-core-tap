"""Findings-reached Search runners (`req-compliance-core-reach`).

The graph is built per test through the service layer with real nodes and edges, using this plugin's own wildcard-end
edges so no other plugin's type is needed:

    roots      S1, S2 (scanners)
    path A     scanner -PERFORMS_COMPLIANCE_SCAN_RUN-> scan run -SCANNED_COMPLIANCE_TARGET-> carrier   (two edges)
    path B     scanner -RUNS_AT_LOCATION-> carrier                                                      (one edge)
    S1         path A -> carrierA ; path B -> carrierA (the same carrier, so the findings are reached twice) and carrierB
    S2         path A -> carrierC
    carrierA   open fA1 (V9 9.8), open fA2 (V7 7.0), open fShared (V4 4.0)
    carrierB   open fB1 (V69 6.9), fShared again (carried by both carriers), open fMulti (concerns V9 and V4),
               resolved fClosed, open fNoConcern (concerns nothing), open fTomb (its carries edge is retired)
    carrierC   open fC1 (V9)
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.searches.reach import (
    MAX_PATH_LENGTH,
    MAX_PATHS,
    findings_reached_count,
    findings_reached_list,
)

from tap_grid.models import Entity, Search
from tap_grid.search import execute_search
from tap_grid.services import create_edge, create_node, delete_edge_by_entity, delete_node

CC = "compliance_core__compliance_"
SCANNER = f"{CC}scanner"
CARRIES = "CARRIES_COMPLIANCE_FINDING__compliance_core"
CONCERNS = "CONCERNS_COMPLIANCE_VULNERABILITY__compliance_core"
PERFORMS = "PERFORMS_COMPLIANCE_SCAN_RUN__compliance_core"
SCANNED = "SCANNED_COMPLIANCE_TARGET__compliance_core"
RUNS_AT = "RUNS_AT_LOCATION__compliance_core"
KEY = "tap_plugin.compliance_core.searches.reach"
PATH_A = [PERFORMS, SCANNED]
PATH_B = [RUNS_AT]
INPUTS = {"root_type": SCANNER, "paths": [PATH_A, PATH_B]}

VULNS = {
    "V9": {"vuln_id": "CVE-9", "title": "nine", "cvss_score": 9.8},
    "V7": {"vuln_id": "CVE-7", "title": "seven", "cvss_score": 7.0},
    "V69": {"vuln_id": "CVE-6.9", "title": "six nine", "cvss_score": 6.9},
    "V4": {"vuln_id": "CVE-4", "title": "four", "cvss_score": 4.0},
    "VN": {"vuln_id": "CVE-NULL"},
}

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


def _node(type_slug: str, payload: dict[str, Any]) -> Entity:
    result = create_node(type_slug, payload)
    assert result.success, result.errors  # nosec B101
    return Entity.objects.get(pk=result.entity_id)


class Graph:
    def __init__(self) -> None:
        self.v = {k: _node(f"{CC}vulnerability", p) for k, p in VULNS.items()}
        self.s1 = _node(SCANNER, {"source": "test", "scanner_key": "S1", "name": "S1"})
        self.s2 = _node(SCANNER, {"source": "test", "scanner_key": "S2", "name": "S2"})
        self.car = {k: _node(f"{CC}exception", {"name": k}) for k in ("carrierA", "carrierB", "carrierC")}
        run1 = _node(f"{CC}scan_run", {"source": "test", "run_key": "run1"})
        run2 = _node(f"{CC}scan_run", {"source": "test", "run_key": "run2"})
        for scanner, run, carrier in ((self.s1, run1, "carrierA"), (self.s2, run2, "carrierC")):
            create_edge(scanner, run, PERFORMS)
            create_edge(run, self.car[carrier], SCANNED, properties={"outcome": "scanned"})
        create_edge(self.s1, self.car["carrierA"], RUNS_AT)
        create_edge(self.s1, self.car["carrierB"], RUNS_AT)
        self.f: dict[str, Entity] = {}
        self.carry: dict[str, Any] = {}
        spec = [
            ("fA1", "carrierA", "open", ["V9"]),
            ("fA2", "carrierA", "open", ["V7"]),
            ("fShared", "carrierA", "open", ["V4"]),
            ("fB1", "carrierB", "open", ["V69"]),
            ("fMulti", "carrierB", "open", ["V4", "V9"]),
            ("fClosed", "carrierB", "resolved", ["V9"]),
            ("fNoConcern", "carrierB", "open", []),
            ("fTomb", "carrierB", "open", ["V9"]),
            ("fC1", "carrierC", "open", ["V9"]),
        ]
        for name, carrier, status, vulns in spec:
            finding = _node(f"{CC}finding", {"name": name, "status": status})
            self.f[name] = finding
            self.carry[name] = create_edge(self.car[carrier], finding, CARRIES)
            for v in vulns:
                create_edge(finding, self.v[v], CONCERNS)
        create_edge(self.car["carrierB"], self.f["fShared"], CARRIES)  # carried by two carriers
        assert delete_edge_by_entity(str(self.carry["fTomb"].entity_id), reason="operator").success  # retired


def count(inputs: dict[str, Any] | None = None) -> dict[str, int]:
    rows = findings_reached_count(Search(), inputs or INPUTS, db_alias="default")["rows"]
    return {r["entity_id"]: r["count"] for r in rows}


def listing(inputs: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return findings_reached_list(Search(), inputs or INPUTS, db_alias="default")["rows"]


class TestRegistration:
    @pytest.mark.spec("req-compliance-core-reach-1")
    def test_both_runners_are_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        assert get_search_runner(f"{KEY}:findings-reached-count") is findings_reached_count
        assert get_search_runner(f"{KEY}:findings-reached-list") is findings_reached_list

    @pytest.mark.spec("req-compliance-core-reach-2")
    @pytest.mark.parametrize("key", ["findings-reached-count", "findings-reached-list"])
    def test_a_module_search_runs_through_the_search_service_with_the_schema_defaults(self, key: str) -> None:
        g = Graph()
        search = Search(
            search_type="module",
            root="node",
            name=key,
            definition={"runner_key": f"{KEY}:{key}"},
            input_schema={
                "type": "object",
                "properties": {
                    "root_type": {"type": "string", "default": SCANNER},
                    "paths": {"type": "array", "default": [PATH_A, PATH_B]},
                },
            },
        )
        envelope = execute_search(search, {})
        assert envelope["nodes"] == [] and envelope["edges"] == []
        assert isinstance(envelope["info"], dict) and isinstance(envelope["warnings"], dict)
        assert {r["entity_id"] for r in envelope["rows"]} == {str(g.s1.pk), str(g.s2.pk)}
        json.dumps(envelope["rows"])


class TestCount:
    @pytest.mark.spec("req-compliance-core-reach-3")
    def test_findings_reached_by_two_paths_or_two_carriers_count_once(self) -> None:
        g = Graph()
        # S1: fA1 fA2 fShared (carrierA, reached by both paths; fShared also on carrierB) + fB1 + fMulti = 5
        assert count() == {str(g.s1.pk): 5, str(g.s2.pk): 1}

    @pytest.mark.spec("req-compliance-core-reach-3")
    def test_each_path_alone_reaches_less_and_the_union_is_what_gryphon_cannot_sum(self) -> None:
        g = Graph()
        only_a = count({**INPUTS, "paths": [PATH_A]})
        only_b = count({**INPUTS, "paths": [PATH_B]})
        assert only_a[str(g.s1.pk)] == 3  # carrierA
        assert only_b[str(g.s1.pk)] == 5  # carrierA and carrierB
        assert count()[str(g.s1.pk)] == 5  # not 3 + 5: the shared findings count once

    @pytest.mark.spec("req-compliance-core-reach-4")
    def test_closed_unconcerning_and_retired_edge_findings_are_not_counted(self) -> None:
        g = Graph()
        before = count()[str(g.s1.pk)]
        names = {r["finding_id"] for r in listing()}
        for excluded in ("fClosed", "fNoConcern"):
            assert str(g.f[excluded].pk) not in names
        assert str(g.f["fTomb"].pk) not in names  # its only carries edge is retired
        assert delete_edge_by_entity(str(g.carry["fB1"].entity_id), reason="operator").success
        assert count()[str(g.s1.pk)] == before - 1

    @pytest.mark.spec("req-compliance-core-reach-5")
    def test_a_tombstoned_carrier_and_a_retired_path_edge_contribute_nothing(self) -> None:
        g = Graph()
        assert delete_node(str(g.car["carrierC"].pk), reason="operator").success
        assert str(g.s2.pk) not in count()
        assert delete_node(str(g.car["carrierB"].pk), reason="operator").success
        assert count()[str(g.s1.pk)] == 3

    @pytest.mark.spec("req-compliance-core-reach-6")
    def test_entity_id_restricts_to_one_root(self) -> None:
        g = Graph()
        assert count({**INPUTS, "entity_id": str(g.s2.pk)}) == {str(g.s2.pk): 1}


class TestList:
    @pytest.mark.spec("req-compliance-core-reach-7")
    def test_one_row_per_finding_highest_cvss_first_named_id_cvss_title(self) -> None:
        g = Graph()
        rows = [r for r in listing() if r["entity_id"] == str(g.s1.pk)]
        assert [r["id"] for r in rows] == ["CVE-9", "CVE-9", "CVE-7", "CVE-6.9", "CVE-4"]  # fA1 and fMulti are both CVE-9
        assert len(rows) == count()[str(g.s1.pk)] == 5
        assert rows[0]["name"] == "CVE-9 | CVSS 9.8 | nine"
        assert rows[0]["cvss"] == 9.8 and rows[0]["title"] == "nine" and rows[0]["finding_id"]
        assert [r["cvss"] for r in rows] == sorted((r["cvss"] for r in rows), reverse=True)

    @pytest.mark.spec("req-compliance-core-reach-7")
    def test_a_finding_that_concerns_two_vulnerabilities_is_listed_once_under_the_higher_score(self) -> None:
        g = Graph()
        multi = [r for r in listing() if r["finding_id"] == str(g.f["fMulti"].pk)]
        assert len(multi) == 1 and multi[0]["id"] == "CVE-9"

    @pytest.mark.spec("req-compliance-core-reach-7")
    def test_an_unscored_vulnerability_reads_n_a_and_sorts_last(self) -> None:
        g = Graph()
        finding = _node(f"{CC}finding", {"name": "fN", "status": "open"})
        create_edge(g.car["carrierC"], finding, CARRIES)
        create_edge(finding, g.v["VN"], CONCERNS)
        rows = [r for r in listing() if r["entity_id"] == str(g.s2.pk)]
        assert rows[-1]["name"] == "CVE-NULL | CVSS n/a" and rows[-1]["cvss"] is None
        assert rows[0]["id"] == "CVE-9"

    @pytest.mark.spec("req-compliance-core-reach-8")
    def test_max_results_limits_the_rows(self) -> None:
        Graph()
        assert len(listing({**INPUTS, "max_results": 2})) == 2


class TestInputs:
    @pytest.mark.spec("req-compliance-core-reach-9")
    @pytest.mark.parametrize(
        "bad, match",
        [
            ({"paths": [PATH_A]}, "root_type"),
            ({"root_type": SCANNER}, "paths"),
            ({"root_type": SCANNER, "paths": []}, "paths"),
            ({"root_type": SCANNER, "paths": [[]]}, "non-empty"),
            ({"root_type": SCANNER, "paths": ["EDGE"]}, "non-empty"),
            ({"root_type": SCANNER, "paths": [[1]]}, "edge type"),
            ({"root_type": SCANNER, "paths": [["A B"]]}, "edge type"),
            ({"root_type": SCANNER, "paths": [PATH_A], "entity_id": 7}, "entity_id"),
            ({"root_type": SCANNER, "paths": [PATH_A], "max_results": 0}, "max_results"),
            ({"root_type": SCANNER, "paths": [PATH_A], "max_results": 10**6}, "max_results"),
            ({"root_type": SCANNER, "paths": [PATH_A], "max_results": True}, "max_results"),
        ],
    )
    def test_bad_inputs_are_refused_with_a_clear_error(self, bad: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            findings_reached_count(Search(), bad, db_alias="default")
        with pytest.raises(ValueError, match=match):
            findings_reached_list(Search(), bad, db_alias="default")

    @pytest.mark.spec("req-compliance-core-reach-9")
    def test_the_length_and_count_limits(self) -> None:
        too_long = {"root_type": SCANNER, "paths": [[RUNS_AT] * (MAX_PATH_LENGTH + 1)]}
        too_many = {"root_type": SCANNER, "paths": [[RUNS_AT]] * (MAX_PATHS + 1)}
        for bad, match in ((too_long, "at most"), (too_many, "at most")):
            with pytest.raises(ValueError, match=match):
                findings_reached_count(Search(), bad, db_alias="default")
        findings_reached_count(Search(), {"root_type": SCANNER, "paths": [[RUNS_AT] * MAX_PATH_LENGTH]}, db_alias="default")
