"""The snapshot series reader (`req-compliance-core-search-snapshot-series`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.searches import snapshot_series
from tap_plugin.compliance_core.searches.snapshot_series import search_snapshot_series

from tap_grid.models import Entity, Search
from tap_grid.services import create_edge, create_node

SNAPSHOT = "compliance_core__compliance_search_snapshot"
CAPTURES = "CAPTURES_SEARCH__compliance_core"
KEY = "tap_plugin.compliance_core.searches.snapshot_series"
T0 = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


def _search(name: str = "coverage") -> Entity:
    made = create_node(
        "search",
        {
            "name": name,
            "search_type": "module",
            "root": "node",
            "definition": {"runner_key": "x:y"},
            "input_schema": {"type": "object"},
        },
    )
    assert made.success, made.errors
    return Entity.objects.get(pk=made.entity_id)


def _snapshot(
    search: Entity, at: datetime, rows: list[dict[str, Any]], *, truncated: bool = False, n: int = 0
) -> Entity:
    stamp = at.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = {
        "name": f"s @ {stamp}",
        "source": "tests",
        "snapshot_key": f"{search.pk}@{stamp}-{n}",
        "search_name": search.name,
        "observed_at": at.isoformat(),
        "row_count": len(rows) + (1 if truncated else 0),
        "rows": rows,
        "truncated": truncated,
        "inputs_text": "{}",
    }
    made = create_node(SNAPSHOT, payload)
    assert made.success, made.errors
    snapshot = Entity.objects.get(pk=made.entity_id)
    create_edge(snapshot, search, CAPTURES)
    return snapshot


def read(search: Entity, **extra: Any) -> dict[str, Any]:
    inputs = {"search_id": str(search.pk), "series_field": "group", "value_field": "pct", **extra}
    return search_snapshot_series(Search(), inputs, db_alias="default")  # type: ignore[arg-type]


def points(out: dict[str, Any]) -> list[tuple[str, str, Any, bool]]:
    return [(r["observed_at"], r["series"], r["value"], r["aggregate"]) for r in out["rows"]]


class TestSeries:
    @pytest.mark.spec("req-compliance-core-search-snapshot-series-1")
    def test_it_is_registered_from_the_manifest(self) -> None:
        from tap_grid.registry import get_search_runner

        assert get_search_runner(f"{KEY}:search-snapshot-series") is search_snapshot_series

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-4")
    @pytest.mark.spec("req-compliance-core-search-snapshot-series-5")
    @pytest.mark.spec("req-compliance-core-search-snapshot-series-7")
    def test_one_row_per_snapshot_and_series_with_the_plain_mean_on_top(self) -> None:
        s = _search()
        _snapshot(s, T0 + timedelta(hours=1), [{"group": "b", "pct": 100.0}, {"group": "a", "pct": 50}])
        _snapshot(s, T0, [{"group": "a", "pct": 20}, {"group": "b", "pct": 40.5}])
        assert points(read(s)) == [
            ("2026-10-20T12:00:00Z", "a", 20, False),
            ("2026-10-20T12:00:00Z", "b", 40.5, False),
            ("2026-10-20T12:00:00Z", "Overall", 30.2, True),  # (20 + 40.5) / 2 = 30.25 to one decimal
            ("2026-10-20T13:00:00Z", "a", 50, False),
            ("2026-10-20T13:00:00Z", "b", 100.0, False),
            ("2026-10-20T13:00:00Z", "Overall", 75.0, True),
        ]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-5")
    def test_the_aggregate_is_unweighted_and_can_be_renamed_or_left_out(self) -> None:
        s = _search()
        _snapshot(
            s, T0, [{"group": "big", "pct": 0, "denominator": 1000}, {"group": "small", "pct": 100, "denominator": 1}]
        )
        assert points(read(s, aggregate_label="All"))[-1] == ("2026-10-20T12:00:00Z", "All", 50.0, True)
        assert not [r for r in read(s, aggregate_label="")["rows"] if r["aggregate"]]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-6")
    def test_a_gap_is_not_a_zero_and_is_counted(self) -> None:
        s = _search()
        _snapshot(
            s,
            T0,
            [
                {"group": "a", "pct": 40},
                {"group": "b", "pct": None},
                {"group": "c", "pct": "n/a"},
                {"group": "d", "pct": True},
                {"pct": 5},
            ],
        )
        out = read(s)
        assert points(out) == [
            ("2026-10-20T12:00:00Z", "a", 40, False),
            ("2026-10-20T12:00:00Z", "Overall", 40.0, True),
        ]
        assert out["warnings"]["rows_skipped"] == [
            "4 rows had a missing or non-numeric series or value and are not points"
        ]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-6")
    def test_a_snapshot_with_no_usable_value_has_no_aggregate(self) -> None:
        s = _search()
        _snapshot(s, T0, [{"group": "a", "pct": None}])
        assert read(s)["rows"] == []

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-8")
    def test_only_the_most_recent_snapshots_are_read_and_older_ones_are_counted(self) -> None:
        s = _search()
        for i in range(4):
            _snapshot(s, T0 + timedelta(hours=i), [{"group": "a", "pct": i}])
        out = read(s, max_snapshots=2, aggregate_label="")
        assert [r["observed_at"] for r in out["rows"]] == ["2026-10-20T14:00:00Z", "2026-10-20T15:00:00Z"]
        assert out["warnings"]["snapshots_omitted"] == ["2 older snapshots were left out; max_snapshots is 2"]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-8")
    def test_since_keeps_snapshots_at_or_after_it(self) -> None:
        s = _search()
        for i in range(3):
            _snapshot(s, T0 + timedelta(hours=i), [{"group": "a", "pct": i}])
        out = read(s, since="2026-10-20T13:00:00Z", aggregate_label="")
        assert [r["value"] for r in out["rows"]] == [1, 2]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-9")
    def test_a_truncated_snapshot_is_read_from_its_rows_and_flagged(self) -> None:
        s = _search()
        _snapshot(s, T0, [{"group": "a", "pct": 10}], truncated=True)
        out = read(s)
        assert points(out)[0] == ("2026-10-20T12:00:00Z", "a", 10, False)
        assert out["warnings"]["truncated_snapshots"] == [
            "1 snapshots were truncated and are read from the rows they hold"
        ]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-4")
    def test_only_the_snapshots_of_the_named_search_are_read(self) -> None:
        a, b = _search("a"), _search("b")
        _snapshot(a, T0, [{"group": "x", "pct": 1}])
        _snapshot(b, T0, [{"group": "y", "pct": 2}])
        assert {r["series"] for r in read(a)["rows"]} == {"x", "Overall"}

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-4")
    def test_a_repeated_series_in_one_snapshot_keeps_the_first_and_says_so(self) -> None:
        s = _search()
        _snapshot(s, T0, [{"group": "a", "pct": 10}, {"group": "a", "pct": 90}])
        out = read(s, aggregate_label="")
        assert [r["value"] for r in out["rows"]] == [10]
        assert out["warnings"]["duplicate_series"]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-3")
    @pytest.mark.parametrize(
        ("extra", "match"),
        [
            ({"search_id": ""}, "search_id"),
            ({"search_id": 5}, "search_id"),
            ({"series_field": ""}, "series_field"),
            ({"value_field": None}, "value_field"),
            ({"aggregate_label": 5}, "aggregate_label"),
            ({"since": "yesterday"}, "since"),
            ({"since": 5}, "since"),
            ({"max_snapshots": 0}, "max_snapshots"),
            ({"max_snapshots": 5001}, "max_snapshots"),
            ({"max_snapshots": True}, "max_snapshots"),
        ],
    )
    def test_bad_inputs_are_refused_naming_them(self, extra: dict[str, Any], match: str) -> None:
        s = _search()
        inputs = {"search_id": str(s.pk), "series_field": "group", "value_field": "pct", **extra}
        with pytest.raises(ValueError, match=match):
            search_snapshot_series(Search(), inputs, db_alias="default")  # type: ignore[arg-type]

    @pytest.mark.spec("req-compliance-core-search-snapshot-series-2")
    @pytest.mark.spec("req-compliance-core-search-snapshot-series-10")
    def test_it_names_nothing_and_writes_nothing(self) -> None:
        text = Path(snapshot_series.__file__).read_text(encoding="utf-8")
        for name in ("percent_mapped", "group", "dimension", "coverage"):
            assert f'"{name}"' not in text, name
        for verb in ("create_node", "patch_node", "replace_node", "delete_node", ".save(", ".update(", ".delete("):
            assert verb not in text, verb
        s = _search()
        _snapshot(s, T0, [{"group": "a", "pct": 1}])
        before = Entity.objects.count()
        read(s)
        assert Entity.objects.count() == before
