"""Grouped dimension mapping (`req-compliance-core-dimension-mapping-16` to `-24`, `-4`, `-5`).

Two entity types (exception and artifact) carry an `inventory` category and a `team`. The mapping asks exceptions for a team
(any value) and artifacts for a `zone`.
"""

from __future__ import annotations

from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.searches.dimension_coverage import _label
from tap_plugin.compliance_core.searches.dimension_mapping import dimension_mapping_entities, dimension_mapping_summary

from tap_grid.models import Entity, Search
from tap_grid.service_types import WriteOperation
from tap_grid.services import delete_node, write_batch

CC = "compliance_core__compliance_"
EXCEPTION = f"{CC}exception"
ARTIFACT = f"{CC}artifact"
FINDING = f"{CC}finding"

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])

TEAM_ANY = {"key": "team"}
ZONE = {"key": "zone", "allowed": ["red"]}


def _node(type_slug: str, payload: dict[str, Any], dimensions: dict[str, Any] | None = None) -> Entity:
    result = write_batch(
        [WriteOperation(verb="create_node", type_slug=type_slug, payload=payload, dimensions=dimensions)]
    )
    assert result.success, result.errors or [r.errors for r in result.results]  # nosec B101
    return Entity.objects.get(pk=result.results[0].entity_id)


def _declare(**values: str) -> None:
    _node("dimension", {"name": "inventory", "description": "Inventory."})
    for value, text in values.items():
        _node("dimension", {"name": f"inventory.{value}", "description": text})


def _summary(mappings: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return dimension_mapping_summary(
        Search(), {"mappings": mappings, "group_by": "inventory", **extra}, db_alias="default"
    )


def _entities(mappings: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return dimension_mapping_entities(
        Search(), {"mappings": mappings, "group_by": "inventory", **extra}, db_alias="default"
    )


def _rows(out: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["group"]: r for r in out["rows"]}


def build() -> None:
    _node(EXCEPTION, {"name": "e-ok"}, {"inventory": "servers", "team": "a"})
    _node(EXCEPTION, {"name": "e-none"}, {"inventory": "servers"})
    _node(ARTIFACT, {"name": "a-ok", "kind": "iiw"}, {"inventory": "apps", "zone": "red"})
    _node(ARTIFACT, {"name": "a-wrong", "kind": "iiw"}, {"inventory": "apps", "zone": "blue"})
    _node(FINDING, {"source": "t", "source_key": "f", "name": "f"}, {"inventory": "apps"})  # no rule names a finding
    _node(EXCEPTION, {"name": "no-group"}, {"team": "a"})  # no inventory: not in the population


MAPPINGS = [{"entity_type": EXCEPTION, "keys": [TEAM_ANY]}, {"entity_type": ARTIFACT, "keys": [ZONE]}]


class TestGroupedSummary:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-18")
    def test_the_population_is_every_entity_carrying_the_key_grouped_by_its_value(self) -> None:
        build()
        rows = _rows(_summary(MAPPINGS))
        assert set(rows) == {"servers", "apps"}
        assert rows["servers"]["denominator"] == 2 and rows["apps"]["denominator"] == 3  # the finding is in apps

    @pytest.mark.spec("req-compliance-core-dimension-mapping-17")
    def test_a_key_with_no_allowed_accepts_any_present_value_and_is_never_incorrect(self) -> None:
        build()
        servers = _rows(_summary(MAPPINGS))["servers"]
        assert (servers["mapped"], servers["unmapped"], servers["mapped_incorrectly"]) == (1, 1, 0)

    @pytest.mark.spec("req-compliance-core-dimension-mapping-20")
    def test_an_entity_no_row_names_is_unmapped_and_a_gap(self) -> None:
        build()
        out = _summary(MAPPINGS)
        apps = _rows(out)["apps"]
        assert (apps["mapped"], apps["mapped_incorrectly"], apps["unmapped"], apps["no_rule"]) == (1, 1, 1, 1)
        assert out["warnings"]["no_rule_types"] == [f"{FINDING}: 1"]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-19")
    def test_the_first_row_naming_the_type_judges_and_the_catch_all_takes_the_rest(self) -> None:
        build()
        mappings = [
            {"entity_type": ARTIFACT, "keys": [ZONE]},
            {"entity_types": [ARTIFACT, EXCEPTION], "keys": [{"key": "team"}]},  # the artifact never reaches this row
            {"entity_types": ["*"], "keys": [{"key": "inventory"}]},  # every other type: has an inventory, so mapped
        ]
        rows = _rows(_summary(mappings))
        assert rows["apps"]["mapped"] == 2 and rows["apps"]["mapped_incorrectly"] == 1 and rows["apps"]["no_rule"] == 0
        assert (
            rows["servers"]["mapped"] == 1 and rows["servers"]["unmapped"] == 1
        )  # the exceptions, judged by the group row

    @pytest.mark.spec("req-compliance-core-dimension-mapping-21")
    def test_every_declared_group_is_listed_in_name_order_then_the_others(self) -> None:
        build()
        _declare(servers="Servers: where they run.", apps="Applications.", zebra="Zebras: none exist.")
        out = _summary(MAPPINGS)
        assert [r["group"] for r in out["rows"]] == ["apps", "servers", "zebra"]
        zebra = _rows(out)["zebra"]
        assert (zebra["denominator"], zebra["percent_mapped"]) == (0, None)
        assert [r["label"] for r in out["rows"]] == ["Applications", "Servers", "Zebras"]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-21")
    def test_an_undeclared_value_is_listed_after_the_declared_ones_with_its_value_as_label(self) -> None:
        build()
        _declare(servers="Servers.")
        out = _summary(MAPPINGS)
        assert [r["group"] for r in out["rows"]] == ["servers", "apps"]
        assert _rows(out)["apps"]["label"] == "apps"

    @pytest.mark.spec("req-compliance-core-dimension-mapping-22")
    def test_the_counts_add_up(self) -> None:
        build()
        for row in _summary(MAPPINGS)["rows"]:
            assert row["mapped"] + row["unmapped"] + row["mapped_incorrectly"] == row["denominator"]
            assert row["no_rule"] <= row["unmapped"]
            assert row["percent_mapped"] == round(100 * row["mapped"] / row["denominator"], 1)

    @pytest.mark.spec("req-compliance-core-dimension-mapping-18")
    def test_a_tombstoned_entity_contributes_nothing_and_a_null_group_is_not_in_the_population(self) -> None:
        build()
        gone = _node(EXCEPTION, {"name": "gone"}, {"inventory": "servers", "team": "a"})
        delete_node(gone.pk)
        nulled = _node(EXCEPTION, {"name": "nulled"})
        Entity.objects.filter(pk=nulled.pk).update(dimensions={"inventory": None, "team": "a"})
        assert _rows(_summary(MAPPINGS))["servers"]["denominator"] == 2

    @pytest.mark.spec("req-compliance-core-dimension-mapping-24")
    def test_an_excluded_group_is_left_out_everywhere(self) -> None:
        build()
        _declare(servers="Servers.", apps="Applications.")
        out = _summary(MAPPINGS, exclude_groups=["apps"])
        assert [r["group"] for r in out["rows"]] == ["servers"]
        assert "no_rule_types" not in out["warnings"]  # the finding sat in the excluded group
        entities = _entities(MAPPINGS, exclude_groups=["apps"])
        assert {r["group"] for r in entities["rows"]} == {"servers"}

    @pytest.mark.spec("req-compliance-core-dimension-mapping-16")
    def test_a_group_row_counts_its_types_together_with_its_label_without_group_by(self) -> None:
        build()
        rows = dimension_mapping_summary(
            Search(),
            {"mappings": [{"entity_types": [EXCEPTION, ARTIFACT], "label": "Things", "keys": [{"key": "inventory"}]}]},
            db_alias="default",
        )["rows"]
        (row,) = rows
        assert (row["label"], row["denominator"], row["mapped"]) == (
            "Things",
            5,
            4,
        )  # the exception with no inventory is unmapped
        assert row["entity_types"] == [EXCEPTION, ARTIFACT]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-16")
    def test_a_row_reads_all_its_types_in_one_query(self, django_assert_max_num_queries: Any) -> None:
        build()
        row = {
            "entity_types": [EXCEPTION, ARTIFACT, FINDING, *[f"nope_{i}" for i in range(40)]],
            "keys": [{"key": "inventory"}],
        }
        with django_assert_max_num_queries(8):
            dimension_mapping_summary(Search(), {"mappings": [row]}, db_alias="default")

    @pytest.mark.spec("req-compliance-core-dimension-mapping-5")
    def test_without_group_by_a_single_type_row_is_as_before(self) -> None:
        build()
        (row,) = dimension_mapping_summary(
            Search(), {"mappings": [{"entity_type": EXCEPTION, "keys": [TEAM_ANY]}]}, db_alias="default"
        )["rows"]
        assert (row["denominator"], row["entity_type"], row["label"]) == (3, EXCEPTION, _label(EXCEPTION))


class TestAnyValueKeys:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-17")
    def test_an_any_value_key_never_makes_a_row_incorrect_but_a_listed_wrong_value_still_does(self) -> None:
        _node(EXCEPTION, {"name": "wrong-zone"}, {"team": "a", "zone": "blue"})
        _node(EXCEPTION, {"name": "ok"}, {"team": "a", "zone": "red"})
        e = Entity.objects.create(entity_type=EXCEPTION, name="odd-team")
        Entity.objects.filter(pk=e.pk).update(
            dimensions={"team": 5, "zone": "red"}
        )  # a non-string value is still present
        got = {
            r["name"]: r["status"]
            for r in dimension_mapping_entities(
                Search(), {"mappings": [{"entity_type": EXCEPTION, "keys": [TEAM_ANY, ZONE]}]}, db_alias="default"
            )["rows"]
        }
        assert got == {"wrong-zone": "mapped_incorrectly", "ok": "mapped", "odd-team": "mapped"}


class TestGroupedEntities:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-23")
    def test_one_row_per_entity_with_group_and_judging_row(self) -> None:
        build()
        rows = {r["name"]: r for r in _entities(MAPPINGS)["rows"]}
        assert len(rows) == 5
        assert (rows["e-ok"]["group"], rows["e-ok"]["mapping"], rows["e-ok"]["status"]) == ("servers", 0, "mapped")
        assert (rows["a-wrong"]["mapping"], rows["a-wrong"]["status"]) == (1, "mapped_incorrectly")
        assert (rows["f"]["mapping"], rows["f"]["status"], rows["f"]["allowed_text"]) == (None, "unmapped", "no rule")

    @pytest.mark.spec("req-compliance-core-dimension-mapping-23")
    def test_status_and_max_entities_are_honoured_and_the_omitted_number_reported(self) -> None:
        build()
        assert {r["status"] for r in _entities(MAPPINGS, status="unmapped")["rows"]} == {"unmapped"}
        out = _entities(MAPPINGS, max_entities=2)
        assert len(out["rows"]) == 2
        assert out["warnings"]["entities_omitted"] == ["3 entity rows were left out; max_entities is 2"]
        assert out["rows"][0]["status"] == "mapped_incorrectly"  # worst first, as before

    @pytest.mark.spec("req-compliance-core-dimension-mapping-17")
    def test_the_allowed_text_of_an_any_value_key_says_so(self) -> None:
        build()
        rows = {r["name"]: r for r in _entities(MAPPINGS)["rows"]}
        assert rows["e-ok"]["allowed_text"] == "team: any value"


class TestGroupedInputs:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-4")
    @pytest.mark.parametrize(
        ("mapping", "match"),
        [
            ({"keys": [TEAM_ANY]}, "exactly one"),
            ({"entity_type": EXCEPTION, "entity_types": [EXCEPTION], "keys": [TEAM_ANY]}, "exactly one"),
            ({"entity_type": None, "entity_types": [EXCEPTION], "keys": [TEAM_ANY]}, "exactly one"),
            ({"entity_type": EXCEPTION, "entity_types": None, "keys": [TEAM_ANY]}, "exactly one"),
            ({"entity_types": [], "keys": [TEAM_ANY]}, "entity_types"),
            ({"entity_types": "x", "keys": [TEAM_ANY]}, "entity_types"),
            ({"entity_types": [EXCEPTION, 5], "keys": [TEAM_ANY]}, "entity_types"),
            ({"entity_types": [f"t{i}" for i in range(51)], "keys": [TEAM_ANY]}, "at most 50"),
            ({"entity_type": EXCEPTION, "label": "x" * 129, "keys": [TEAM_ANY]}, "label"),
            ({"entity_type": EXCEPTION, "label": 5, "keys": [TEAM_ANY]}, "label"),
            ({"entity_type": EXCEPTION, "keys": [{"key": "k", "allowed": []}]}, "allowed"),
        ],
    )
    def test_a_bad_row_is_refused(self, mapping: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            dimension_mapping_summary(Search(), {"mappings": [mapping]}, db_alias="default")

    @pytest.mark.spec("req-compliance-core-dimension-mapping-24")
    @pytest.mark.parametrize(
        ("extra", "match"),
        [
            ({"group_by": ""}, "group_by"),
            ({"group_by": 5}, "group_by"),
            ({"group_by": "x" * 129}, "group_by"),
            ({"group_by": "inventory", "exclude_groups": "apps"}, "exclude_groups"),
            ({"group_by": "inventory", "exclude_groups": [1]}, "exclude_groups"),
            ({"group_by": "inventory", "exclude_groups": ["g"] * 51}, "exclude_groups"),
            ({"exclude_groups": ["apps"]}, "needs group_by"),
        ],
    )
    @pytest.mark.parametrize("runner", [dimension_mapping_summary, dimension_mapping_entities])
    def test_bad_grouping_inputs_are_refused_naming_them(self, runner: Any, extra: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            runner(Search(), {"mappings": MAPPINGS, **extra}, db_alias="default")

    @pytest.mark.spec("req-compliance-core-dimension-mapping-3")
    def test_the_runner_still_names_no_entity_type_or_key(self) -> None:
        from pathlib import Path

        import tap_plugin.compliance_core.searches.dimension_mapping as module

        text = Path(module.__file__).read_text(encoding="utf-8")
        for name in ("inventory", "compliance_core__", "team", "zone"):
            assert name not in text.replace("`inventory`", ""), name
