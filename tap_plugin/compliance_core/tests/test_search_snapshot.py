"""The Search snapshot node and its abstract collector (`req-compliance-core-search-snapshot*`).

Everything runs against a real grid through the service layer. Where a test needs a Search result no real Search
would give (a nested value, a graph, too many rows), it replaces `execute_search` inside the collector module, which
is the one place the collector reaches the search service.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import tap_plugin.compliance_core.apps as compliance_apps
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from tap_plugin.compliance_core.collectors.search_snapshot import SearchSnapshotCollector
from tap_plugin.compliance_core.collectors.search_snapshot import collector as collector_module

from tap.pytest_harness import isolated_registry
from tap_cares.models import CollectionJobStatus, Collector
from tap_cares.registry import collector_registry, reconcile_collector_nodes, register_collector
from tap_cares.services import run_collection
from tap_grid.models import Edge, Entity
from tap_grid.registry import get_model_class
from tap_grid.services import create_edge, create_node

SNAPSHOT = "compliance_core__compliance_search_snapshot"
CAPTURES = "CAPTURES_SEARCH__compliance_core"
EXCEPTION = "compliance_core__compliance_exception"
KEY = "tap_plugin.compliance_core.searches.dimension_mapping"

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])

GOOD = {
    "name": "coverage @ 2026-10-20T12:00:00.000000Z",
    "source": "tests",
    "snapshot_key": "abc@2026-10-20T12:00:00.000000Z",
    "search_name": "coverage",
    "observed_at": "2026-10-20T12:00:00Z",
    "row_count": 2,
    "rows": [{"a": 1}, {"a": 2}],
    "truncated": False,
    "inputs_text": "{}",
}


def _ok(payload: dict[str, Any]) -> bool:
    return create_node(SNAPSHOT, payload).success


@pytest.fixture
def isolate_collector_registry() -> Iterator[None]:
    with isolated_registry(collector_registry):
        yield


def _search(name: str = "coverage", defaults: dict[str, Any] | None = None) -> Entity:
    made = create_node(
        "search",
        {
            "name": name,
            "search_type": "module",
            "root": "node",
            "definition": {"runner_key": f"{KEY}:dimension-mapping-summary"},
            "input_schema": {
                "type": "object",
                "properties": defaults
                if defaults is not None
                else {"mappings": {"type": "array", "default": [{"entity_type": EXCEPTION, "keys": [{"key": "zone", "allowed": ["red"]}]}]}},
            },
        },
    )
    assert made.success, made.errors
    return Entity.objects.get(pk=made.entity_id)


def _subclass(search_ids: tuple[str, ...], *, source: str = "tests", max_rows: int | None = None) -> type[SearchSnapshotCollector]:
    attrs: dict[str, Any] = {"SOURCE": source, "SEARCH_ENTITY_IDS": search_ids}
    if max_rows is not None:
        attrs["MAX_ROWS"] = max_rows
    return type("FixtureSnapshotCollector", (SearchSnapshotCollector,), attrs)


def _register(cls: type[SearchSnapshotCollector], key: str = "snap") -> Collector:
    register_collector(key=key, cls=cls, scope="tap_plugin.compliance_core.tests", name="snapshot fixture", description="fixture")
    reconcile_collector_nodes()
    return Collector.objects.get(collector_registry=f"tap_plugin.compliance_core.tests:{key}")


def _run_registered(collector: Collector, *, expect: str = CollectionJobStatus.SUCCESSFUL.value) -> Any:
    job = run_collection(collector)
    job.refresh_from_db()
    assert job.status == expect, (job.status, job.summary, job.results)
    return job


def _run(cls: type[SearchSnapshotCollector], *, expect: str = CollectionJobStatus.SUCCESSFUL.value) -> Any:
    return _run_registered(_register(cls), expect=expect)


def _snapshots() -> list[Any]:
    return list(get_model_class(SNAPSHOT).objects.live().order_by("observed_at", "snapshot_key"))


class TestNode:
    @pytest.mark.spec("req-compliance-core-search-snapshot-1")
    def test_a_good_snapshot_is_created_with_its_dimension(self) -> None:
        made = create_node(SNAPSHOT, GOOD)
        assert made.success, made.errors
        assert Entity.objects.get(pk=made.entity_id).dimensions == {"compliance": "search-snapshot"}
        row = get_model_class(SNAPSHOT).objects.get(entity_id=made.entity_id)
        assert row.rows == [{"a": 1}, {"a": 2}] and row.truncated is False and row.row_count == 2

    @pytest.mark.spec("req-compliance-core-search-snapshot-2")
    def test_identity_is_source_and_key_and_a_second_time_is_a_second_node(self) -> None:
        assert get_model_class(SNAPSHOT).NATURAL_KEY == ("source", "snapshot_key")
        assert _ok(GOOD)
        assert _ok({**GOOD, "snapshot_key": "abc@2026-10-20T13:00:00.000000Z", "observed_at": "2026-10-20T13:00:00Z"})
        assert len(_snapshots()) == 2

    @pytest.mark.spec("req-compliance-core-search-snapshot-3")
    @pytest.mark.parametrize("missing", ["name", "source", "snapshot_key", "observed_at", "row_count", "rows", "truncated", "inputs_text"])
    def test_required_fields(self, missing: str) -> None:
        assert not _ok({k: v for k, v in GOOD.items() if k != missing})

    @pytest.mark.spec("req-compliance-core-search-snapshot-3")
    @pytest.mark.parametrize("bad", [None, "2026-10-20", "noon", 5])
    def test_observed_at_is_a_real_instant(self, bad: Any) -> None:
        assert not _ok({**GOOD, "observed_at": bad})

    @pytest.mark.spec("req-compliance-core-search-snapshot-4")
    def test_rows_are_bounded_scalar_objects(self) -> None:
        many = [{"i": i} for i in range(1000)]
        assert _ok({**GOOD, "snapshot_key": "k1", "rows": many, "row_count": 1000})
        assert not _ok({**GOOD, "snapshot_key": "k2", "rows": [*many, {"i": 1000}], "row_count": 1001})
        assert not _ok({**GOOD, "snapshot_key": "k3", "rows": [{"a": [1]}], "row_count": 1})
        assert not _ok({**GOOD, "snapshot_key": "k4", "rows": [{"a": {"b": 1}}], "row_count": 1})
        assert not _ok({**GOOD, "snapshot_key": "k5", "rows": [{"a": "x" * 4097}], "row_count": 1})
        assert _ok({**GOOD, "snapshot_key": "k6", "rows": [{"a": "x" * 4096, "b": None, "c": True, "d": 1.5}], "row_count": 1})
        assert not _ok({**GOOD, "snapshot_key": "k7", "rows": [{f"p{i}": 1 for i in range(51)}], "row_count": 1})
        assert not _ok({**GOOD, "snapshot_key": "k8", "rows": [{"n" * 129: 1}], "row_count": 1})
        assert not _ok({**GOOD, "snapshot_key": "k9", "rows": {"a": 1}, "row_count": 1})

    @pytest.mark.spec("req-compliance-core-search-snapshot-5")
    @pytest.mark.parametrize(
        ("truncated", "row_count", "ok"),
        [(False, 2, True), (False, 3, False), (False, 1, False), (True, 3, True), (True, 2, False), (True, 1, False)],
    )
    def test_truncated_must_agree_with_the_counts(self, truncated: bool, row_count: int, ok: bool) -> None:
        assert _ok({**GOOD, "truncated": truncated, "row_count": row_count}) is ok

    @pytest.mark.spec("req-compliance-core-search-snapshot-5")
    def test_zero_rows_is_a_snapshot(self) -> None:
        assert _ok({**GOOD, "rows": [], "row_count": 0, "truncated": False})

    @pytest.mark.spec("req-compliance-core-search-snapshot-6")
    def test_the_edge_links_a_snapshot_to_a_real_search(self) -> None:
        snapshot = Entity.objects.get(pk=create_node(SNAPSHOT, GOOD).entity_id)
        edge = create_edge(snapshot, _search(), CAPTURES)
        assert edge.entity.dimensions == {"compliance": "search-snapshot"}

    @pytest.mark.spec("req-compliance-core-search-snapshot-8")
    def test_the_package_has_no_code_that_updates_a_snapshot(self) -> None:
        root = Path(collector_module.__file__).parent.parent.parent
        offenders = [
            str(path.relative_to(root))
            for path in root.rglob("*.py")
            if "tests" not in path.parts and "migrations" not in path.parts
            and any(token in path.read_text() for token in ("replace_node(", "update_node("))
            and "snapshot" in path.read_text().lower()
        ]
        assert offenders == []


class TestSubclassContract:
    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-1")
    def test_the_base_is_abstract_and_unregistered(self) -> None:
        assert issubclass(SearchSnapshotCollector, collector_module.CollectorBase)
        assert SearchSnapshotCollector.SOURCE == "" and SearchSnapshotCollector.SEARCH_ENTITY_IDS == ()
        assert "register_collector" not in Path(collector_module.__file__).read_text()
        assert "register_collector" not in Path(compliance_apps.__file__).read_text()

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-2")
    @pytest.mark.parametrize(
        "attrs",
        [
            {"SEARCH_ENTITY_IDS": (str(uuid.uuid4()),)},
            {"SOURCE": "", "SEARCH_ENTITY_IDS": (str(uuid.uuid4()),)},
            {"SOURCE": "x" * 65, "SEARCH_ENTITY_IDS": (str(uuid.uuid4()),)},
            {"SOURCE": "s"},
            {"SOURCE": "s", "SEARCH_ENTITY_IDS": ()},
            {"SOURCE": "s", "SEARCH_ENTITY_IDS": [str(uuid.uuid4())]},
            {"SOURCE": "s", "SEARCH_ENTITY_IDS": ("not-a-uuid",)},
            {"SOURCE": "s", "SEARCH_ENTITY_IDS": (7,)},
            {"SOURCE": "s", "SEARCH_ENTITY_IDS": (str(uuid.uuid4()),), "MAX_ROWS": 1001},
            {"SOURCE": "s", "SEARCH_ENTITY_IDS": (str(uuid.uuid4()),), "MAX_ROWS": 0},
        ],
    )
    def test_a_bad_subclass_is_refused_at_definition(self, attrs: dict[str, Any]) -> None:
        with pytest.raises(TypeError):
            type("Bad", (SearchSnapshotCollector,), attrs)

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-2")
    def test_a_good_subclass_is_accepted(self) -> None:
        assert _subclass((str(uuid.uuid4()),)).SOURCE == "tests"


class TestRun:
    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-10")
    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-9")
    def test_one_run_writes_one_snapshot_and_a_second_run_a_second(self, isolate_collector_registry: Any) -> None:
        for name in ("e1", "e2"):
            made = create_node(EXCEPTION, {"name": name})
            assert made.success
        search = _search()
        collector = _register(_subclass((str(search.pk),)))
        job = _run_registered(collector)
        first = _snapshots()
        assert len(first) == 1 and "1 search" in job.summary
        snap = first[0]
        assert snap.source == "tests" and snap.search_name == "coverage"
        assert snap.snapshot_key == f"{search.pk}@{snap.observed_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"
        assert snap.row_count == 1 and len(snap.rows) == 1 and snap.truncated is False
        assert snap.rows[0]["denominator"] == 2 and snap.rows[0]["entity_type"] == EXCEPTION
        edges = Edge.objects.filter(edge_type=CAPTURES)
        assert [(str(e.from_entity_id), str(e.to_entity_id)) for e in edges] == [(str(snap.entity_id), str(search.pk))]
        _run_registered(collector)
        assert len(_snapshots()) == 2, "a second run writes a second snapshot, not a replacement"

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-8")
    def test_inputs_text_is_canonical_json_of_the_defaults(
        self, isolate_collector_registry: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(collector_module, "execute_search", lambda search, *a, **k: {"nodes": [], "edges": [], "rows": []})
        search = _search(defaults={"b": {"default": 2}, "a": {"default": {"y": 1, "x": [1, 2]}}, "nodefault": {"type": "string"}})
        _run(_subclass((str(search.pk),)))
        assert _snapshots()[0].inputs_text == '{"a":{"x":[1,2],"y":1},"b":2}'

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-3")
    @pytest.mark.parametrize("which", ["missing", "not_a_search"])
    def test_an_unresolvable_id_fails_the_run_and_writes_nothing(self, isolate_collector_registry: Any, which: str) -> None:
        good = _search()
        bad = str(uuid.uuid4()) if which == "missing" else str(create_node(EXCEPTION, {"name": "not a search"}).entity_id)
        job = _run(_subclass((str(good.pk), bad)), expect=CollectionJobStatus.FAILED.value)
        assert bad in json.dumps(job.results)
        assert _snapshots() == [] and Edge.objects.filter(edge_type=CAPTURES).count() == 0

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-4")
    def test_a_search_that_raises_fails_the_run_and_writes_nothing(
        self, isolate_collector_registry: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(search: Any, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("the runner broke")

        monkeypatch.setattr(collector_module, "execute_search", boom)
        _run(_subclass((str(_search().pk),)), expect=CollectionJobStatus.FAILED.value)
        assert _snapshots() == []

    def _fake(self, monkeypatch: pytest.MonkeyPatch, envelope: dict[str, Any]) -> None:
        monkeypatch.setattr(collector_module, "execute_search", lambda search, *a, **k: envelope)

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-5")
    def test_no_rows_key_and_an_empty_graph_is_zero_rows(self, isolate_collector_registry: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self._fake(monkeypatch, {"nodes": [], "edges": []})
        _run(_subclass((str(_search().pk),)))
        snap = _snapshots()[0]
        assert (snap.row_count, snap.rows, snap.truncated) == (0, [], False)

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-5")
    def test_a_graph_shaped_result_fails_the_run(self, isolate_collector_registry: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self._fake(monkeypatch, {"nodes": [{"id": "x"}], "edges": []})
        _run(_subclass((str(_search().pk),)), expect=CollectionJobStatus.FAILED.value)
        assert _snapshots() == []

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-6")
    def test_rows_are_bounded_and_the_count_stays_exact(self, isolate_collector_registry: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self._fake(monkeypatch, {"nodes": [], "edges": [], "rows": [{"i": i} for i in range(7)]})
        _run(_subclass((str(_search().pk),), max_rows=3))
        snap = _snapshots()[0]
        assert (snap.row_count, len(snap.rows), snap.truncated) == (7, 3, True)
        assert [r["i"] for r in snap.rows] == [0, 1, 2]

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-7")
    def test_nested_values_become_text_long_strings_are_cut_and_one_warning_counts_them(
        self, isolate_collector_registry: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [{"list": [1, 2], "obj": {"b": 1, "a": 2}, "long": "x" * 5000, "ok": 3, "none": None}]
        self._fake(monkeypatch, {"nodes": [], "edges": [], "rows": rows})
        job = _run(_subclass((str(_search().pk),)))
        row = _snapshots()[0].rows[0]
        assert row["list"] == "[1,2]" and row["obj"] == '{"a":2,"b":1}'
        assert len(row["long"]) == 4096 and row["ok"] == 3 and row["none"] is None
        warns = [w for w in job.results["warn"] if w["message_code"] == "VALUES_CONVERTED"]
        assert len(warns) == 1 and warns[0]["message_data"]["count"] == 3

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-7")
    def test_a_row_the_snapshot_cannot_hold_fails_the_run(self, isolate_collector_registry: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self._fake(monkeypatch, {"nodes": [], "edges": [], "rows": [{f"p{i}": i for i in range(51)}]})
        _run(_subclass((str(_search().pk),)), expect=CollectionJobStatus.FAILED.value)
        assert _snapshots() == []

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-9")
    def test_one_run_shares_one_observed_time_across_its_searches(self, isolate_collector_registry: Any) -> None:
        a, b = _search("one"), _search("two")
        _run(_subclass((str(a.pk), str(b.pk))))
        snaps = _snapshots()
        assert len(snaps) == 2 and snaps[0].observed_at == snaps[1].observed_at
        assert {s.search_name for s in snaps} == {"one", "two"}

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-11")
    def test_a_search_with_no_rows_still_writes_a_snapshot(self, isolate_collector_registry: Any) -> None:
        _run(_subclass((str(_search().pk),)))  # no exception exists, so the summary row has a zero denominator
        snap = _snapshots()[0]
        assert snap.row_count == 1 and snap.rows[0]["denominator"] == 0 and snap.rows[0]["percent_mapped"] is None

    @pytest.mark.spec("req-compliance-core-search-snapshot-collector-12")
    def test_the_collector_reads_no_earlier_snapshot(self) -> None:
        import inspect

        assert "ComplianceSearchSnapshot" not in inspect.getsource(collector_module)
        assert "objects" not in inspect.getsource(collector_module)
