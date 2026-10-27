"""The shared coverage calculation and the live totals runner (`req-compliance-core-dimension-mapping-totals`)."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core import coverage
from tap_plugin.compliance_core.searches import dimension_mapping_totals as totals_module
from tap_plugin.compliance_core.searches import snapshot_series
from tap_plugin.compliance_core.searches.dimension_mapping_totals import (
    dimension_mapping_totals,
    dimension_mapping_totals_set,
)

from tap_grid.models import Entity, Search
from tap_grid.search import execute_search
from tap_grid.service_types import WriteOperation
from tap_grid.services import create_node, patch_node, write_batch

CC = "compliance_core__compliance_"
EXCEPTION = f"{CC}exception"
ARTIFACT = f"{CC}artifact"
KEY = "tap_plugin.compliance_core.searches.dimension_mapping"
PACKAGE = Path(totals_module.__file__).parents[1]

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


def _node(type_slug: str, payload: dict[str, Any], dimensions: dict[str, Any] | None = None) -> Entity:
    result = write_batch(
        [WriteOperation(verb="create_node", type_slug=type_slug, payload=payload, dimensions=dimensions)]
    )
    assert result.success, result.errors or [r.errors for r in result.results]  # nosec B101
    return Entity.objects.get(pk=result.results[0].entity_id)


def _summary_search(name: str = "summary", **defaults: Any) -> Entity:
    defaults = defaults or {
        "mappings": [
            {"entity_type": EXCEPTION, "keys": [{"key": "team"}]},
            {"entity_type": ARTIFACT, "keys": [{"key": "zone", "allowed": ["red"]}]},
        ],
        "group_by": "inventory",
    }
    made = create_node(
        "search",
        {
            "name": name,
            "search_type": "module",
            "root": "node",
            "definition": {"runner_key": f"{KEY}:dimension-mapping-summary"},
            "input_schema": {"type": "object", "properties": {k: {"default": v} for k, v in defaults.items()}},
        },
    )
    assert made.success, made.errors
    return Entity.objects.get(pk=made.entity_id)


def _build() -> None:
    _node(EXCEPTION, {"name": "e-ok"}, {"inventory": "servers", "team": "a"})
    _node(EXCEPTION, {"name": "e-none"}, {"inventory": "servers"})
    _node(ARTIFACT, {"name": "a-ok", "kind": "iiw"}, {"inventory": "apps", "zone": "red"})
    _node(ARTIFACT, {"name": "a-bad", "kind": "iiw"}, {"inventory": "apps", "zone": "blue"})
    _node(ARTIFACT, {"name": "a-bad2", "kind": "iiw"}, {"inventory": "apps", "zone": "blue"})
    _node("dimension", {"name": "inventory", "description": "Inventory."})
    _node("dimension", {"name": "inventory.empty", "description": "Empty group."})  # declared, no entities


def run(search: Entity) -> dict[str, Any]:
    return dimension_mapping_totals(Search(), {"summary_search_id": str(search.pk)}, db_alias="default")  # type: ignore[arg-type]


class TestPureCalculation:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-7")
    def test_the_module_imports_only_the_standard_library(self) -> None:
        """Django-free by construction: every import in coverage.py is from the standard library."""
        tree = ast.parse((PACKAGE / "coverage.py").read_text(encoding="utf-8"))
        imported = {
            (node.module or "").split(".")[0] if isinstance(node, ast.ImportFrom) else alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in (node.names if isinstance(node, ast.Import) else [None])
        }
        assert imported and imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)
        assert "django" not in imported and "tap_grid" not in imported

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-3")
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            ([20, 40.5], 30.2),
            ([None, 10, "x", True, 30], 20.0),
            ([], None),
            ([None, "a"], None),
            ([0, 0], 0.0),
            ([1, 2, 2], 1.7),
        ],
    )
    def test_plain_mean(self, values: list[Any], expected: float | None) -> None:
        assert coverage.plain_mean(values) == expected

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-4")
    def test_totals_from_rows(self) -> None:
        rows = [
            {
                "percent_mapped": 50.0,
                "denominator": 2,
                "mapped": 1,
                "unmapped": 1,
                "mapped_incorrectly": 0,
                "no_rule": 1,
            },
            {
                "percent_mapped": 100.0,
                "denominator": 8,
                "mapped": 8,
                "unmapped": 0,
                "mapped_incorrectly": 0,
                "no_rule": 0,
            },
            {
                "percent_mapped": None,
                "denominator": 0,
                "mapped": 0,
                "unmapped": 0,
                "mapped_incorrectly": 0,
                "no_rule": 0,
            },
        ]
        got = coverage.totals_from_rows(rows)
        assert got == {
            "groups": 2, "percent_overall": 75.0, "denominator": 10, "mapped": 9, "unmapped": 1,
            "mapped_incorrectly": 0, "no_rule": 1, "percent_pooled": 90.0,
        }  # fmt: skip
        assert (
            coverage.totals_from_rows([])["percent_overall"] is None
            and coverage.totals_from_rows([])["percent_pooled"] is None
        )


class TestRunner:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-1")
    def test_it_is_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        assert (
            get_search_runner(
                f"{PACKAGE.name and 'tap_plugin.compliance_core.searches.dimension_mapping_totals'}:dimension-mapping-totals"
            )
            is dimension_mapping_totals
        )

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-2")
    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-3")
    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-4")
    def test_one_row_with_the_plain_average_and_the_pooled_counts(self) -> None:
        _build()
        out = run(_summary_search())
        (row,) = out["rows"]
        json.dumps(out["rows"])
        # servers: 1 of 2 mapped (50.0); apps: 1 of 3 mapped (33.3); "empty" has no entities and no percent
        assert row["groups"] == 2
        assert row["percent_overall"] == 41.6  # (50.0 + 33.3) / 2 = 41.65, which float rounding takes to 41.6
        assert (row["denominator"], row["mapped"], row["unmapped"], row["mapped_incorrectly"], row["no_rule"]) == (
            5,
            2,
            1,
            2,
            0,
        )
        assert row["mapped"] + row["unmapped"] + row["mapped_incorrectly"] == row["denominator"]
        assert row["percent_pooled"] == 40.0

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-5")
    def test_changing_the_summary_search_changes_the_totals_with_no_other_edit(self) -> None:
        _build()
        search = _summary_search()
        before = run(search)["rows"][0]
        assert patch_node(
            search.pk,
            {
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "mappings": {"default": [{"entity_type": EXCEPTION, "keys": [{"key": "team"}]}]},
                        "group_by": {"default": "inventory"},
                        "exclude_groups": {"default": ["apps"]},
                    },
                }
            },
        ).success
        after = run(search)["rows"][0]
        assert (
            before != after and after["denominator"] == 2 and after["groups"] == 1
        )  # only servers, the apps group excluded

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-6")
    def test_the_mean_is_computed_in_one_place_and_the_chart_agrees_with_the_card(self) -> None:
        for module in (totals_module, snapshot_series):
            text = Path(module.__file__).read_text(encoding="utf-8")
            assert "/ len(" not in text and "statistics" not in text, module.__name__
        assert "plain_mean" in Path(snapshot_series.__file__).read_text(encoding="utf-8")
        assert "totals_from_rows" in Path(totals_module.__file__).read_text(encoding="utf-8")

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-8")
    def test_it_is_live_and_reads_no_snapshot(self) -> None:
        text = Path(totals_module.__file__).read_text(encoding="utf-8")
        assert "snapshot" not in text.replace("no snapshot", "")
        _build()
        search = _summary_search()
        first = run(search)["rows"][0]["denominator"]
        _node(EXCEPTION, {"name": "e-new"}, {"inventory": "servers"})
        assert run(search)["rows"][0]["denominator"] == first + 1

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-9")
    @pytest.mark.parametrize("bad", [None, "", 5, "not-a-uuid", "01a15fdf-0000-7000-8000-000000000000"])
    def test_a_missing_or_unknown_id_is_refused_naming_the_input(self, bad: Any) -> None:
        with pytest.raises(ValueError, match="summary_search_id"):
            dimension_mapping_totals(Search(), {"summary_search_id": bad}, db_alias="default")  # type: ignore[arg-type]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-9")
    def test_a_node_that_is_not_a_search_and_a_search_with_another_runner_are_refused(self) -> None:
        node = _node(EXCEPTION, {"name": "x"})
        with pytest.raises(ValueError, match="summary_search_id"):
            dimension_mapping_totals(Search(), {"summary_search_id": str(node.pk)}, db_alias="default")  # type: ignore[arg-type]
        made = create_node(
            "search",
            {
                "name": "other",
                "search_type": "module",
                "root": "node",
                "definition": {"runner_key": f"{KEY}:dimension-coverage"},
                "input_schema": {"type": "object"},
            },
        )
        with pytest.raises(ValueError, match="dimension-mapping-summary"):
            dimension_mapping_totals(Search(), {"summary_search_id": str(made.entity_id)}, db_alias="default")  # type: ignore[arg-type]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-2")
    def test_it_runs_through_the_search_service(self) -> None:
        _build()
        summary = _summary_search()
        search = Search(
            search_type="module",
            root="node",
            name="totals",
            definition={
                "runner_key": "tap_plugin.compliance_core.searches.dimension_mapping_totals:dimension-mapping-totals"
            },
            input_schema={
                "type": "object",
                "properties": {"summary_search_id": {"type": "string", "default": str(summary.pk)}},
            },
        )
        envelope = execute_search(search, {})
        assert len(envelope["rows"]) == 1 and envelope["nodes"] == [] and envelope["edges"] == []


FIELDS = (
    "groups", "percent_overall", "denominator", "mapped", "unmapped", "mapped_incorrectly", "no_rule", "percent_pooled",
)  # fmt: skip


def run_set(summaries: Any) -> dict[str, Any]:
    return dimension_mapping_totals_set(Search(), {"summaries": summaries}, db_alias="default")  # type: ignore[arg-type]


class TestRunnerSet:
    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-set-1")
    def test_it_is_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        key = "tap_plugin.compliance_core.searches.dimension_mapping_totals:dimension-mapping-totals-set"
        assert get_search_runner(key) is dimension_mapping_totals_set

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-set-2")
    def test_two_summaries_give_one_row_each_equal_to_the_single_runner(self) -> None:
        _build()
        one = _summary_search("one")
        two = _summary_search(
            "two",
            mappings=[{"entity_type": EXCEPTION, "keys": [{"key": "team"}]}],
            group_by="inventory",
            exclude_groups=["apps"],
        )
        out = run_set(
            [
                {"key": "resp", "label": "Responsibility", "summary_search_id": str(one.pk)},
                {"key": "data_class", "summary_search_id": str(two.pk)},
            ]
        )
        json.dumps(out)
        assert out["nodes"] == [] and out["edges"] == [] and out["info"] == {"row_count": 2}
        assert [(r["key"], r["label"]) for r in out["rows"]] == [("resp", "Responsibility"), ("data_class", "data_class")]
        for row, search in zip(out["rows"], (one, two), strict=True):
            assert set(row) == {"key", "label", "percent_text", *FIELDS}
            assert row["percent_text"] == f"{round(row['percent_overall'], 1)}%"
            single = run(search)["rows"][0]
            assert {f: row[f] for f in FIELDS} == {f: single[f] for f in FIELDS}
        assert out["rows"][0]["denominator"] != out["rows"][1]["denominator"]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-set-3")
    def test_warnings_are_the_summaries_own_concatenated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _build()
        a, b = _summary_search("a"), _summary_search("b")
        real = totals_module.dimension_mapping_summary

        def fake(summary: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
            out = real(summary, *args, **kwargs)
            return {**out, "warnings": [f"w-{summary.name}"]}

        monkeypatch.setattr(totals_module, "dimension_mapping_summary", fake)
        out = run_set([{"key": "a", "summary_search_id": str(a.pk)}, {"key": "b", "summary_search_id": str(b.pk)}])
        assert out["warnings"] == ["w-a", "w-b"]

    @pytest.mark.spec("req-compliance-core-dimension-mapping-totals-set-4")
    def test_bad_input_is_refused(self) -> None:
        _build()
        ok = str(_summary_search().pk)
        node = _node(EXCEPTION, {"name": "x"})
        for bad in (
            [],
            None,
            "x",
            [{"key": "a", "summary_search_id": ok}, {"key": "a", "summary_search_id": ok}],
            [{"key": "A", "summary_search_id": ok}],
            [{"key": "1a", "summary_search_id": ok}],
            [{"key": "a-b", "summary_search_id": ok}],
            [{"key": "", "summary_search_id": ok}],
            [{"key": "a", "label": "", "summary_search_id": ok}],
            [{"key": "a", "label": 3, "summary_search_id": ok}],
            [{"summary_search_id": ok}],
            ["a"],
            [{"key": "a", "summary_search_id": str(node.pk)}],
            [{"key": "a", "summary_search_id": ok}, {"key": "b", "summary_search_id": None}],
        ):
            with pytest.raises(ValueError):
                run_set(bad)
