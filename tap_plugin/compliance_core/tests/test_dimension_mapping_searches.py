"""Dimension-mapping Search runners (`req-compliance-core-dimension-mapping`).

The graph is built through the service layer. Exceptions are the mapped type (a type with a free `dimensions` map); the
mapping asks that they carry `zone` (red, green) and `team` (a, b).

    z-ok      zone red,  team a      both correct
    z-half    zone red                one key missing
    z-wrong   zone amber, team a      one key holds a disallowed value
    z-none    no dimensions            nothing set
    z-null    zone null (JSON null), team b
    z-num     zone 5 (a number), team a
    z-case    zone RED, team a        different case is a different value
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.searches.dimension_mapping import (
    MappingRow,
    classify,
    dimension_mapping_entities,
    dimension_mapping_summary,
)

from tap_grid.models import Entity, Search
from tap_grid.search import execute_search
from tap_grid.service_types import WriteOperation
from tap_grid.services import delete_node, write_batch

CC = "compliance_core__compliance_"
EXCEPTION = f"{CC}exception"
ARTIFACT = f"{CC}artifact"
KEY = "tap_plugin.compliance_core.searches.dimension_mapping"

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])

ZONE = {"key": "zone", "allowed": ["red", "green"]}
TEAM = {"key": "team", "allowed": ["a", "b"]}
ROW = {"entity_type": EXCEPTION, "keys": [ZONE, TEAM]}


def _node(type_slug: str, payload: dict[str, Any], dimensions: dict[str, Any] | None = None) -> Entity:
    result = write_batch([WriteOperation(verb="create_node", type_slug=type_slug, payload=payload, dimensions=dimensions)])
    assert result.success, result.errors or [r.errors for r in result.results]  # nosec B101
    return Entity.objects.get(pk=result.results[0].entity_id)


def build() -> dict[str, Entity]:
    nodes = {
        "z-ok": _node(EXCEPTION, {"name": "z-ok"}, {"zone": "red", "team": "a"}),
        "z-half": _node(EXCEPTION, {"name": "z-half"}, {"zone": "red"}),
        "z-wrong": _node(EXCEPTION, {"name": "z-wrong"}, {"zone": "amber", "team": "a"}),
        "z-none": _node(EXCEPTION, {"name": "z-none"}),
        "z-case": _node(EXCEPTION, {"name": "z-case"}, {"zone": "RED", "team": "a"}),
    }
    # JSON null and a number are written straight onto the spine row: the service layer only stamps strings.
    for name, dims in (("z-null", {"zone": None, "team": "b"}), ("z-num", {"zone": 5, "team": "a"})):
        entity = _node(EXCEPTION, {"name": name})
        Entity.objects.filter(pk=entity.pk).update(dimensions=dims)
        nodes[name] = entity
    _node(ARTIFACT, {"name": "art", "kind": "iiw"}, {"zone": "red", "team": "a"})
    return nodes


def summary(mappings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    out = dimension_mapping_summary(Search(), {"mappings": mappings or [ROW]}, db_alias="default")
    return out["rows"]


def entities(extra: dict[str, Any] | None = None, mappings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    inputs = {"mappings": mappings or [ROW], **(extra or {})}
    return dimension_mapping_entities(Search(), inputs, db_alias="default")["rows"]


def by_name(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {r["name"]: r["status"] for r in rows}


class TestRegistration:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-1")
    def test_both_runners_are_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        assert get_search_runner(f"{KEY}:dimension-mapping-summary") is dimension_mapping_summary
        assert get_search_runner(f"{KEY}:dimension-mapping-entities") is dimension_mapping_entities

    @pytest.mark.spec("req-compliance-core-dimension-mapping-2")
    @pytest.mark.parametrize("runner", ["dimension-mapping-summary", "dimension-mapping-entities"])
    def test_a_module_search_runs_through_the_search_service_with_the_schema_defaults(self, runner: str) -> None:
        build()
        search = Search(
            search_type="module",
            root="node",
            name=runner,
            definition={"runner_key": f"{KEY}:{runner}"},
            input_schema={"type": "object", "properties": {"mappings": {"type": "array", "default": [ROW]}}},
        )
        envelope = execute_search(search, {})
        assert envelope["nodes"] == [] and envelope["edges"] == []
        assert envelope["rows"]
        json.dumps(envelope["rows"])


class TestClassification:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-6")
    def test_match_all(self) -> None:
        build()
        assert by_name(entities()) == {
            "z-ok": "mapped",
            "z-half": "unmapped",  # one key correct, the other absent, none disallowed
            "z-wrong": "mapped_incorrectly",
            "z-none": "unmapped",
            "z-case": "mapped_incorrectly",
            "z-null": "unmapped",  # null is absent, team b alone does not map under all
            "z-num": "mapped_incorrectly",
        }

    @pytest.mark.spec("req-compliance-core-dimension-mapping-7")
    def test_match_any(self) -> None:
        build()
        got = by_name(entities(mappings=[{**ROW, "match": "any"}]))
        assert got == {
            "z-ok": "mapped",
            "z-half": "mapped",
            "z-wrong": "mapped",  # team a is correct, so a disallowed zone does not unmap it
            "z-none": "unmapped",
            "z-case": "mapped",
            "z-null": "mapped",  # null zone is absent; team b is correct
            "z-num": "mapped",
        }

    @pytest.mark.spec("req-compliance-core-dimension-mapping-7")
    def test_match_any_with_only_disallowed_values_is_mapped_incorrectly(self) -> None:
        _node(EXCEPTION, {"name": "bad-both"}, {"zone": "amber", "team": "z"})
        assert by_name(entities(mappings=[{**ROW, "match": "any"}])) == {"bad-both": "mapped_incorrectly"}

    @pytest.mark.spec("req-compliance-core-dimension-mapping-8")
    @pytest.mark.parametrize("value", ["RED", "re", "red ", 5, ["red"], {"v": "red"}, True])
    def test_a_value_is_allowed_only_by_exact_string_equality(self, value: Any) -> None:
        row = MappingRow(EXCEPTION, (("zone", ("red", "green")),), "all")
        assert classify({"zone": value}, row)[0] == "mapped_incorrectly"
        assert classify({"zone": "red"}, row)[0] == "mapped"

    @pytest.mark.spec("req-compliance-core-dimension-mapping-8")
    def test_null_and_absent_are_both_unmapped(self) -> None:
        row = MappingRow(EXCEPTION, (("zone", ("red",)),), "all")
        assert classify({"zone": None}, row) == ("unmapped", {})
        assert classify({}, row) == ("unmapped", {})
        assert classify(None, row) == ("unmapped", {})

    @pytest.mark.spec("req-compliance-core-dimension-mapping-8")
    def test_a_value_that_says_none_is_a_real_value(self) -> None:
        row = MappingRow(EXCEPTION, (("dataclass.action", ("none", "read")),), "all")
        assert classify({"dataclass.action": "none"}, row)[0] == "mapped"


class TestSummary:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-5")
    def test_the_denominator_is_the_live_entities_of_the_type(self) -> None:
        nodes = build()
        assert summary()[0]["denominator"] == 7  # the artifact is another type
        assert delete_node(nodes["z-ok"].pk).success
        assert summary()[0]["denominator"] == 6

    @pytest.mark.spec("req-compliance-core-dimension-mapping-9")
    def test_counts_add_up_and_the_percentage_is_one_decimal(self) -> None:
        build()
        row = summary()[0]
        assert (row["mapped"], row["unmapped"], row["mapped_incorrectly"]) == (1, 3, 3)
        assert row["mapped"] + row["unmapped"] + row["mapped_incorrectly"] == row["denominator"]
        assert row["percent_mapped"] == 14.3  # 1 of 7
        assert row["entity_type"] == EXCEPTION and row["match"] == "all"
        assert row["keys_text"] == "zone: red, green\nteam: a, b"

    @pytest.mark.spec("req-compliance-core-dimension-mapping-10")
    def test_a_type_with_nothing_on_the_grid_reports_zero_and_null(self) -> None:
        row = summary([{"entity_type": f"{CC}boundary", "keys": [ZONE]}])[0]
        assert (row["denominator"], row["mapped"], row["unmapped"], row["mapped_incorrectly"]) == (0, 0, 0, 0)
        assert row["percent_mapped"] is None

    @pytest.mark.spec("req-compliance-core-dimension-mapping-11")
    def test_rows_are_independent_and_come_back_in_input_order(self) -> None:
        build()
        rows = summary([{**ROW, "match": "any"}, ROW, {"entity_type": ARTIFACT, "keys": [ZONE]}])
        assert [(r["entity_type"], r["match"], r["mapped"]) for r in rows] == [
            (EXCEPTION, "any", 6),
            (EXCEPTION, "all", 1),
            (ARTIFACT, "all", 1),
        ]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-3")
    def test_the_label_is_the_registered_name(self) -> None:
        assert summary([{"entity_type": EXCEPTION, "keys": [ZONE]}])[0]["label"]


class TestEntities:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-12")
    def test_rows_carry_the_documented_fields_in_the_documented_order(self) -> None:
        build()
        rows = entities()
        assert [r["status"] for r in rows] == ["mapped_incorrectly"] * 3 + ["unmapped"] * 3 + ["mapped"]
        names_in_state = [r["name"] for r in rows if r["status"] == "mapped_incorrectly"]
        assert names_in_state == sorted(names_in_state)
        first = next(r for r in rows if r["name"] == "z-wrong")
        assert set(first) == {
            "mapping", "entity_id", "entity_type", "label", "name", "status", "found", "found_text", "allowed_text",
        }
        assert first["found"] == {"zone": "amber", "team": "a"}
        assert first["found_text"] == "zone = amber\nteam = a"
        assert first["allowed_text"] == "zone: red, green\nteam: a, b"
        none = next(r for r in rows if r["name"] == "z-none")
        assert none["found"] == {} and none["found_text"] == "not set"
        json.dumps(rows)

    @pytest.mark.spec("req-compliance-core-dimension-mapping-12")
    def test_a_non_string_value_is_shown_as_json(self) -> None:
        build()
        num = next(r for r in entities() if r["name"] == "z-num")
        assert num["found"]["zone"] == 5 and "zone = 5" in num["found_text"]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-11")
    def test_an_entity_in_two_rows_is_listed_once_per_row_with_its_index(self) -> None:
        build()
        rows = [r for r in entities(mappings=[ROW, {**ROW, "match": "any"}]) if r["name"] == "z-half"]
        assert sorted((r["mapping"], r["status"]) for r in rows) == [(0, "unmapped"), (1, "mapped")]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-13")
    @pytest.mark.parametrize("state", ["mapped", "unmapped", "mapped_incorrectly"])
    def test_the_status_filter_returns_only_that_state(self, state: str) -> None:
        build()
        rows = entities({"status": state})
        assert rows and {r["status"] for r in rows} == {state}

    @pytest.mark.spec("req-compliance-core-dimension-mapping-14")
    def test_max_entities_bounds_the_rows_and_the_summary_is_untouched(self) -> None:
        build()
        out = dimension_mapping_entities(Search(), {"mappings": [ROW], "max_entities": 2}, db_alias="default")
        assert len(out["rows"]) == 2
        assert out["warnings"]["entities_omitted"] == ["5 entity rows were left out; max_entities is 2"]
        assert [r["status"] for r in out["rows"]] == ["mapped_incorrectly", "mapped_incorrectly"]
        assert summary()[0]["denominator"] == 7

    @pytest.mark.spec("req-compliance-core-dimension-mapping-14")
    def test_repeated_mapping_rows_are_counted_exactly_and_still_capped(self) -> None:
        build()
        out = dimension_mapping_entities(Search(), {"mappings": [ROW, ROW, ROW], "max_entities": 1}, db_alias="default")
        assert len(out["rows"]) == 1
        assert out["warnings"]["entities_omitted"] == ["20 entity rows were left out; max_entities is 1"]  # 3 x 7 - 1

    @pytest.mark.spec("req-compliance-core-dimension-mapping-5")
    def test_a_tombstoned_entity_is_not_listed(self) -> None:
        nodes = build()
        assert delete_node(nodes["z-wrong"].pk).success
        assert "z-wrong" not in by_name(entities())


class TestWarnings:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-15")
    def test_undeclared_keys_and_values_warn_and_change_no_state(self) -> None:
        build()
        _node("dimension", {"name": "zone", "description": "The zone."})
        _node("dimension", {"name": "zone.red", "description": "Red."})
        before = by_name(entities())
        out = dimension_mapping_summary(Search(), {"mappings": [ROW]}, db_alias="default")
        assert out["warnings"]["undeclared_keys"] == ["team"]  # zone has a node, team has none
        assert out["warnings"]["undeclared_values"] == ["team = a", "team = b", "zone = green"]
        assert by_name(entities()) == before

    @pytest.mark.spec("req-compliance-core-dimension-mapping-15")
    def test_a_fully_declared_mapping_has_no_warnings(self) -> None:
        for name in ("zone", "zone.red", "zone.green", "team", "team.a", "team.b"):
            _node("dimension", {"name": name, "description": name})
        assert dimension_mapping_summary(Search(), {"mappings": [ROW]}, db_alias="default")["warnings"] == {}


class TestInputs:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-4")
    @pytest.mark.parametrize(
        ("inputs", "match"),
        [
            ({}, "mappings"),
            ({"mappings": []}, "mappings"),
            ({"mappings": "x"}, "mappings"),
            ({"mappings": ["x"]}, "mappings\\[0\\]"),
            ({"mappings": [{"keys": [ZONE]}]}, "entity_type"),
            ({"mappings": [{"entity_type": EXCEPTION}]}, "keys"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": []}]}, "keys"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": [{"allowed": ["a"]}]}]}, "key"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": [{"key": "k", "allowed": []}]}]}, "allowed"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": [{"key": "k", "allowed": [1]}]}]}, "allowed"),
            ({"mappings": [{**ROW, "match": "some"}]}, "match"),
            ({"mappings": [ROW] * 51}, "at most 50"),
            ({"mappings": [{**ROW, "entity_type": "x" * 129}]}, "entity_type"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": [{"key": "k" * 129, "allowed": ["a"]}]}]}, "key"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": [{"key": "k", "allowed": ["v" * 257]}]}]}, "longer than 256"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": [{"key": f"k{i}", "allowed": ["a"]} for i in range(21)]}]}, "at most 20"),
            ({"mappings": [{"entity_type": EXCEPTION, "keys": [{"key": "k", "allowed": [str(i) for i in range(101)]}]}]}, "at most 100"),
        ],
    )
    @pytest.mark.parametrize("runner", [dimension_mapping_summary, dimension_mapping_entities])
    def test_a_bad_mapping_is_refused_naming_the_input(self, runner: Any, inputs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            runner(Search(), inputs, db_alias="default")

    @pytest.mark.spec("req-compliance-core-dimension-mapping-4")
    @pytest.mark.parametrize(
        ("extra", "match"),
        [
            ({"status": "bogus"}, "status"),
            ({"status": 7}, "status"),
            ({"max_entities": 0}, "max_entities"),
            ({"max_entities": 5001}, "max_entities"),
            ({"max_entities": True}, "max_entities"),
            ({"max_entities": "9"}, "max_entities"),
        ],
    )
    def test_a_bad_entities_input_is_refused_naming_it(self, extra: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            dimension_mapping_entities(Search(), {"mappings": [ROW], **extra}, db_alias="default")

    @pytest.mark.spec("req-compliance-core-dimension-mapping-3")
    def test_no_entity_type_key_or_value_is_named_in_the_runner_code(self) -> None:
        from pathlib import Path

        import tap_plugin.compliance_core.searches.dimension_mapping as module

        source = Path(module.__file__).read_text()
        for name in ("compliance_core__", "dataclass.", "customer"):
            assert name not in source
