"""The dimension-coverage Search runner (`req-compliance-core-dimension-coverage`).

The graph is built per test through the service layer:

    dictionary   dimension nodes ``zone`` (described), ``zone.red``, ``zone.green``, ``zone.blue`` (all described),
                 and ``other.red`` (another key, must not leak in)
    entities     red:   two exceptions, one artifact           green: one exception
                 blue:  none                                   amber (no dictionary node): one artifact
                 unstamped exception, and an exception stamped ``other`` = red
                 a retired exception stamped red (tombstoned), an edge-typed boundary stamped red (excluded by input)
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.searches.dimension_coverage import dimension_coverage

from tap_grid.models import Entity, Search
from tap_grid.search import execute_search
from tap_grid.service_types import WriteOperation
from tap_grid.services import delete_node, write_batch

CC = "compliance_core__compliance_"
EXCEPTION = f"{CC}exception"
ARTIFACT = f"{CC}artifact"
BOUNDARY = f"{CC}boundary"
KEY = "tap_plugin.compliance_core.searches.dimension_coverage"

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


def _node(type_slug: str, payload: dict[str, Any], dimensions: dict[str, str] | None = None) -> Entity:
    result = write_batch([WriteOperation(verb="create_node", type_slug=type_slug, payload=payload, dimensions=dimensions)])
    assert result.success, result.errors or [r.errors for r in result.results]  # nosec B101
    return Entity.objects.get(pk=result.results[0].entity_id)


class Graph:
    def __init__(self) -> None:
        for name, text in (
            ("zone", "The zone an item sits in."),
            ("zone.red", "The red zone."),
            ("zone.green", "The green zone."),
            ("zone.blue", "The blue zone, which nothing is in."),
            ("other.red", "A different key's red."),
        ):
            _node("dimension", {"name": name, "description": text})
        red = {"zone": "red"}
        _node(EXCEPTION, {"name": "e1"}, red)
        _node(EXCEPTION, {"name": "e2"}, red)
        _node(ARTIFACT, {"name": "a1", "kind": "iiw"}, red)
        _node(EXCEPTION, {"name": "e3"}, {"zone": "green"})
        _node(ARTIFACT, {"name": "a2", "kind": "iiw"}, {"zone": "amber"})
        _node(EXCEPTION, {"name": "unstamped"})
        _node(EXCEPTION, {"name": "elsewhere"}, {"other": "red"})
        retired = _node(EXCEPTION, {"name": "retired"}, red)
        assert delete_node(str(retired.pk)).success  # nosec B101
        _node(BOUNDARY, {"name": "b1"}, red)


def run(**inputs: Any) -> dict[str, Any]:
    envelope = dimension_coverage(Search(), {"dimension_key": "zone", **inputs}, db_alias="default")
    assert len(envelope["rows"]) == 1  # nosec B101
    return envelope["rows"][0]  # type: ignore[no-any-return]


def values(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {v["value"]: v for v in row["values"]}


class TestRegistration:
    @pytest.mark.spec("req-compliance-core-dimension-coverage-1")
    def test_the_runner_is_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        assert get_search_runner(f"{KEY}:dimension-coverage") is dimension_coverage

    @pytest.mark.spec("req-compliance-core-dimension-coverage-2")
    def test_a_module_search_runs_through_the_search_service_with_the_schema_defaults(self) -> None:
        Graph()
        search = Search(
            search_type="module",
            root="node",
            name="coverage",
            definition={"runner_key": f"{KEY}:dimension-coverage"},
            input_schema={
                "type": "object",
                "properties": {
                    "dimension_key": {"type": "string", "default": "zone"},
                    "exclude_types": {"type": "array", "items": {"type": "string"}, "default": [BOUNDARY]},
                },
            },
        )
        envelope = execute_search(search, {})
        assert envelope["nodes"] == [] and envelope["edges"] == []
        assert isinstance(envelope["info"], dict) and isinstance(envelope["warnings"], dict)
        json.dumps(envelope["rows"])  # every value is JSON-serialisable
        row = envelope["rows"][0]
        assert row["total"] == 5  # the read-only search connection saw the graph; the boundary is excluded


class TestCounts:
    @pytest.mark.spec("req-compliance-core-dimension-coverage-3")
    def test_each_value_is_counted_by_entity_type(self) -> None:
        Graph()
        row = run(exclude_types=[BOUNDARY])
        by = values(row)
        assert by["red"]["count"] == 3
        assert by["red"]["by_type"] == [
            {"type": EXCEPTION, "label": "compliance exception", "count": 2},
            {"type": ARTIFACT, "label": "compliance artifact", "count": 1},
        ]
        assert by["green"]["by_type"] == [{"type": EXCEPTION, "label": "compliance exception", "count": 1}]
        assert row["total"] == 5

    @pytest.mark.spec("req-compliance-core-dimension-coverage-4")
    def test_a_declared_value_nothing_carries_is_an_honest_zero(self) -> None:
        Graph()
        blue = values(run())["blue"]
        assert blue["count"] == 0 and blue["by_type"] == [] and blue["declared"] is True
        assert blue["description"] == "The blue zone, which nothing is in."

    @pytest.mark.spec("req-compliance-core-dimension-coverage-5")
    def test_an_undeclared_value_is_counted_and_marked(self) -> None:
        Graph()
        row = run(exclude_types=[BOUNDARY])
        amber = values(row)["amber"]
        assert amber["count"] == 1 and amber["declared"] is False and amber["description"] is None
        assert [v["value"] for v in row["values"]] == ["blue", "green", "red", "amber"]  # declared first, then not

    @pytest.mark.spec("req-compliance-core-dimension-coverage-6")
    def test_another_key_and_unstamped_entities_do_not_count(self) -> None:
        Graph()
        row = run(exclude_types=[BOUNDARY])
        assert row["total"] == 5  # not the unstamped exception, not the exception stamped under another key
        assert row["description"] == "The zone an item sits in."

    @pytest.mark.spec("req-compliance-core-dimension-coverage-7")
    def test_a_tombstoned_entity_contributes_nothing(self) -> None:
        Graph()
        assert values(run(exclude_types=[BOUNDARY]))["red"]["count"] == 3  # the retired exception is not the fourth

    @pytest.mark.spec("req-compliance-core-dimension-coverage-8")
    def test_exclude_types_are_not_counted_and_nothing_is_excluded_by_default(self) -> None:
        Graph()
        assert values(run())["red"]["count"] == 4
        assert values(run(exclude_types=[BOUNDARY]))["red"]["count"] == 3

    @pytest.mark.spec("req-compliance-core-dimension-coverage-9")
    def test_a_key_with_no_dimension_node_still_answers(self) -> None:
        Graph()
        envelope = dimension_coverage(Search(), {"dimension_key": "nothing.here"}, db_alias="default")
        row = envelope["rows"][0]
        assert row["description"] is None and row["values"] == [] and row["total"] == 0


class TestText:
    @pytest.mark.spec("req-compliance-core-dimension-coverage-10")
    def test_the_display_strings_are_made_from_the_values(self) -> None:
        Graph()
        row = run(exclude_types=[BOUNDARY])
        assert row["values_text"].splitlines() == [
            "blue: The blue zone, which nothing is in.",
            "green: The green zone.",
            "red: The red zone.",
            "amber: no description in the dictionary",
        ]
        assert row["breakdown_text"].splitlines() == [
            "blue: none",
            "green: 1 component: compliance exception 1",
            "red: 3 components: compliance exception 2, compliance artifact 1",
            "amber: 1 component: compliance artifact 1",
        ]


class TestInputs:
    @pytest.mark.spec("req-compliance-core-dimension-coverage-11")
    @pytest.mark.parametrize("bad", [None, "", "  ", 3, ["zone"]])
    def test_dimension_key_must_be_a_non_empty_string(self, bad: Any) -> None:
        with pytest.raises(ValueError, match="dimension_key"):
            dimension_coverage(Search(), {"dimension_key": bad}, db_alias="default")

    @pytest.mark.spec("req-compliance-core-dimension-coverage-11")
    @pytest.mark.parametrize("bad", ["boundary", [1], {"a": 1}])
    def test_exclude_types_must_be_strings(self, bad: Any) -> None:
        with pytest.raises(ValueError, match="exclude_types"):
            dimension_coverage(Search(), {"dimension_key": "zone", "exclude_types": bad}, db_alias="default")
