"""The report panel type (`req-compliance-core-panel-report`).

The panel node, its Searches and the `USES_SEARCH` edges are built through the service layer; the Searches' results are
supplied by replacing `execute_search`, the one place the panel reaches the search service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from django.template.loader import render_to_string
from django.test import RequestFactory
from tap_plugin.compliance_core.panels.report import REPORT_PANEL_CONFIG_SCHEMA, ReportPanelType, layout

from tap_grid.models import Entity
from tap_grid.services import create_edge, create_node

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])

PACKAGE = Path(layout.__file__).parents[2]
VIEW = "compliance_core/panels/report.html"


def _search(name: str) -> Entity:
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


def _panel(config: dict[str, Any], linked: list[Entity]) -> Any:
    from tap_web.models import Panel

    made = create_node("panel", {"name": "Report", "slug": "report-test", "view": VIEW, "config": config})
    assert made.success, made.errors
    entity = Entity.objects.get(pk=made.entity_id)
    for search in linked:
        create_edge(entity, search, "USES_SEARCH")
    return Panel.objects.get(entity=entity)


@pytest.fixture
def results(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Search name -> rows (a list) or an exception; counts the runs per name."""
    table: dict[str, Any] = {"_runs": {}}

    def fake(search: Any, inputs: Any = None, **kwargs: Any) -> dict[str, Any]:
        table["_runs"][search.name] = table["_runs"].get(search.name, 0) + 1
        value = table[search.name]
        if isinstance(value, Exception):
            raise value
        return {"rows": value, "nodes": [], "edges": []}

    monkeypatch.setattr("tap_grid.search.execute_search", fake)
    return table


def context(panel: Any) -> dict[str, Any]:
    return ReportPanelType.get_view_context(panel, RequestFactory().get("/"))


def render(panel: Any) -> str:
    ctx = context(panel)
    return render_to_string(VIEW, {**ctx, "panel": panel, "request": RequestFactory().get("/")})


def fig(label: str, search: Entity, field: str, fmt: str = "count", **extra: Any) -> dict[str, Any]:
    return {"kind": "figure", "label": label, "search": str(search.pk), "field": field, "format": fmt, **extra}


def report(items: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"title": "Coverage", "sections": [{"heading": "Summary", "items": items}], **extra}


class TestRegistered:
    @pytest.mark.spec("req-compliance-core-panel-report-1")
    def test_it_is_on_the_registry_with_a_stylesheet_and_no_script(self) -> None:
        from tap_web.registry import panel_type_registry

        assert panel_type_registry.get("report") is ReportPanelType
        assert ReportPanelType.css == ["compliance_core/css/report.css"] and ReportPanelType.js == []
        assert (PACKAGE / "static" / "compliance_core" / "css" / "report.css").is_file()

    @pytest.mark.spec("req-compliance-core-panel-report-1")
    def test_the_schema_describes_every_property_and_refuses_unknown_keys(self) -> None:
        def walk(node: Any, path: str = "") -> None:
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    assert node.get("additionalProperties") is False, path
                    for key, sub in node["properties"].items():
                        assert "description" in sub, f"{path}.{key}"
                for key, sub in node.items():
                    walk(sub, f"{path}.{key}")
            elif isinstance(node, list):
                for sub in node:
                    walk(sub, path)

        walk(REPORT_PANEL_CONFIG_SCHEMA)
        panel = _panel({**report([{"kind": "rule"}]), "bogus": 1}, [])
        assert context(panel)["state"] == "bad_config"

    @pytest.mark.spec("req-compliance-core-panel-report-1")
    def test_it_has_no_script_in_the_template(self) -> None:
        text = (PACKAGE / "templates" / "compliance_core" / "panels" / "report.html").read_text(encoding="utf-8")
        assert "<script" not in text and "javascript:" not in text and "onclick" not in text


class TestSearches:
    @pytest.mark.spec("req-compliance-core-panel-report-2")
    def test_a_search_the_panel_is_not_linked_to_is_a_configuration_error_and_is_not_run(
        self, results: dict[str, Any]
    ) -> None:
        linked, stranger = _search("linked"), _search("stranger")
        results.update({"linked": [{"n": 1}], "stranger": [{"n": 2}]})
        panel = _panel(report([fig("Mine", linked, "n"), fig("Not mine", stranger, "n")]), [linked])
        html = render(panel)
        assert "Configuration error" in html and "stranger" not in results["_runs"]
        assert "Mine" in html

    @pytest.mark.spec("req-compliance-core-panel-report-3")
    def test_a_search_named_by_several_lines_runs_once(self, results: dict[str, Any]) -> None:
        s = _search("shared")
        results["shared"] = [{"a": 1, "b": 2}]
        panel = _panel(
            report(
                [
                    fig("A", s, "a"),
                    fig("B", s, "b"),
                    {
                        "kind": "list",
                        "search": str(s.pk),
                        "label_field": "a",
                        "columns": [{"field": "b", "title": "B", "format": "count"}],
                    },
                ]
            ),
            [s],
        )
        context(panel)
        assert results["_runs"] == {"shared": 1}

    @pytest.mark.spec("req-compliance-core-panel-report-17")
    def test_it_writes_nothing(self, results: dict[str, Any]) -> None:
        s = _search("w")
        results["w"] = [{"n": 1}]
        panel = _panel(report([fig("N", s, "n")]), [s])
        before = Entity.objects.count()
        render(panel)
        assert Entity.objects.count() == before


class TestFigures:
    @pytest.mark.spec("req-compliance-core-panel-report-4")
    def test_a_figure_reads_the_row_or_the_first_where_match_and_shows_of(self, results: dict[str, Any]) -> None:
        s = _search("t")
        results["t"] = [{"g": "a", "n": 1, "d": 10}, {"g": "b", "n": 2, "d": 20}]
        panel = _panel(
            report(
                [
                    fig("Row one", s, "n", row=1),
                    fig("Where b", s, "n", where={"field": "g", "equals": "b"}, of="d"),
                    fig("Default", s, "n"),
                ]
            ),
            [s],
        )
        sections = context(panel)["sections"]
        values = [i["value"] for i in sections[0]["items"]]
        assert values == ["2", "2", "1"] and sections[0]["items"][1]["of"] == "20"

    @pytest.mark.spec("req-compliance-core-panel-report-5")
    @pytest.mark.parametrize(
        ("value", "fmt", "expected"),
        [
            (1234567, "count", "1,234,567"),
            (41.65, "percent", "41.6%"),
            (50, "percent", "50.0%"),
            ("2026-10-21T12:34:56Z", "date", "2026-10-21"),
            ("2026-10-21T12:34:56Z", "datetime", "2026-10-21 12:34 UTC"),
            ("hello", "text", "hello"),
            ("x", "count", "Not observed"),
            ("x", "percent", "Not observed"),
            ("nope", "date", "Not observed"),
            (True, "count", "Not observed"),
        ],
    )
    def test_formats(self, value: Any, fmt: str, expected: str) -> None:
        assert layout.format_value(value, fmt) == expected

    @pytest.mark.spec("req-compliance-core-panel-report-6")
    def test_not_observed_is_never_zero_or_blank(self, results: dict[str, Any]) -> None:
        ok, empty, broken = _search("ok"), _search("empty"), _search("broken")
        results.update({"ok": [{"n": None}], "empty": [], "broken": RuntimeError("secret detail")})
        panel = _panel(
            report([fig("Null", ok, "n"), fig("Missing", empty, "n"), fig("Failed", broken, "n")]), [ok, empty, broken]
        )
        ctx = context(panel)
        assert [i["value"] for i in ctx["sections"][0]["items"]] == ["Not observed"] * 3
        html = render(panel)
        assert "Search unavailable: broken" in html and "secret detail" not in html and ">0<" not in html


class TestLists:
    @pytest.mark.spec("req-compliance-core-panel-report-7")
    def test_a_list_shows_up_to_the_limit_and_says_how_many_were_left_out(self, results: dict[str, Any]) -> None:
        s = _search("rows")
        results["rows"] = [{"name": f"n{i}", "count": i} for i in range(5)]
        item = {
            "kind": "list",
            "search": str(s.pk),
            "label_field": "name",
            "title": "Name",
            "limit": 3,
            "columns": [{"field": "count", "title": "Count", "format": "count"}],
        }
        panel = _panel(report([item]), [s])
        out = context(panel)["sections"][0]["items"][0]
        assert len(out["rows"]) == 3 and out["omitted"] == 2
        assert "2 more not shown" in render(panel)

    @pytest.mark.spec("req-compliance-core-panel-report-7")
    def test_more_than_four_columns_are_refused(self, results: dict[str, Any]) -> None:
        s = _search("c")
        cols = [{"field": f"f{i}", "title": "T", "format": "text"} for i in range(5)]
        panel = _panel(report([{"kind": "list", "search": str(s.pk), "label_field": "a", "columns": cols}]), [s])
        assert context(panel)["state"] == "bad_config"


def _series(values: list[tuple[str, str, float]]) -> list[dict[str, Any]]:
    return [{"at": at, "series": series, "value": v} for at, series, v in values]


class TestTrends:
    LINE = {"label": "Overall", "x_field": "at", "value_field": "value", "series_field": "series", "series": "Overall"}

    def trend(self, s: Entity, **extra: Any) -> dict[str, Any]:
        return {"kind": "trend", "label": "Coverage over time", "lines": [{**self.LINE, "search": str(s.pk)}], **extra}

    @pytest.mark.spec("req-compliance-core-panel-report-8")
    @pytest.mark.spec("req-compliance-core-panel-report-12")
    def test_a_trend_is_inline_svg_with_a_title_end_label_labels_and_a_hidden_table(
        self, results: dict[str, Any]
    ) -> None:
        s = _search("h")
        results["h"] = _series([("2026-10-20T10:00:00Z", "Overall", 40), ("2026-10-21T10:00:00Z", "Overall", 55.5)])
        html = render(_panel(report([self.trend(s)]), [s]))
        assert "<svg" in html and "<title>Coverage over time" in html and "<polyline" in html
        assert "Overall 55.5" in html and "2026-10-20 10:00 UTC" in html and "2026-10-21 10:00 UTC" in html
        assert (
            'class="rpt-sr"' in html
            and "<script" not in html
            and "http" not in html.split("<svg", 1)[1].split("</svg>", 1)[0]
        )

    @pytest.mark.spec("req-compliance-core-panel-report-9")
    def test_the_y_range_is_fixed_not_rescaled_to_the_data(self, results: dict[str, Any]) -> None:
        s = _search("h")
        results["h"] = _series([("2026-10-20T10:00:00Z", "Overall", 50), ("2026-10-21T10:00:00Z", "Overall", 51)])
        lines = layout.build_trend([{**self.LINE, "search": "k"}], {"k": results["h"]}, 0, 100)
        ys = [float(p.split(",")[1]) for p in lines["lines"][0]["points"].split()]
        frame = lines["frame"]
        middle = (frame["top"] + frame["base"]) / 2
        assert (
            abs(ys[0] - middle) < 3 and abs(ys[1] - middle) < 3
        )  # 50 and 51 on a 0 to 100 scale are both near the middle
        tight = layout.build_trend([{**self.LINE, "search": "k"}], {"k": results["h"]}, 50, 51)
        assert [float(p.split(",")[1]) for p in tight["lines"][0]["points"].split()] == [frame["base"], frame["top"]]
        assert s  # keep the fixture used

    @pytest.mark.spec("req-compliance-core-panel-report-10")
    def test_a_series_filter_keeps_only_matching_rows_ordered_by_time(self) -> None:
        rows = _series(
            [
                ("2026-10-22T00:00:00Z", "Overall", 3),
                ("2026-10-20T00:00:00Z", "Overall", 1),
                ("2026-10-21T00:00:00Z", "Other", 99),
                ("2026-10-21T00:00:00Z", "Overall", 2),
            ]
        )
        out = layout.build_trend([{**self.LINE, "search": "k"}], {"k": rows}, 0, 100)
        assert [t["value"] for t in out["lines"][0]["table"]] == ["1", "2", "3"]
        every = layout.build_trend(
            [{"label": "All", "search": "k", "x_field": "at", "value_field": "value"}], {"k": rows}, 0, 100
        )
        assert len(every["lines"][0]["table"]) == 4

    @pytest.mark.spec("req-compliance-core-panel-report-11")
    def test_a_trend_with_no_points_says_no_data_yet(self, results: dict[str, Any]) -> None:
        s = _search("h")
        results["h"] = _series([("2026-10-21T00:00:00Z", "Other", 10)])  # nothing matches the series
        html = render(_panel(report([self.trend(s)]), [s]))
        assert "No data yet" in html and "<svg" not in html

    @pytest.mark.spec("req-compliance-core-panel-report-11")
    def test_non_numeric_values_are_not_points(self) -> None:
        rows = _series([("2026-10-20T00:00:00Z", "Overall", 1)]) + [
            {"at": "2026-10-21T00:00:00Z", "series": "Overall", "value": None}
        ]
        out = layout.build_trend([{**self.LINE, "search": "k"}], {"k": rows}, 0, 100)
        assert len(out["lines"][0]["table"]) == 1 and out["lines"][0]["single"] is not None


class TestFailedTrends:
    LINE = {"label": "Overall", "x_field": "at", "value_field": "value"}

    @pytest.mark.spec("req-compliance-core-panel-report-11")
    @pytest.mark.spec("req-compliance-core-panel-report-6")
    def test_a_failed_trend_search_is_not_observed_not_no_data_yet(self, results: dict[str, Any]) -> None:
        s = _search("boomtrend")
        results["boomtrend"] = RuntimeError("x")
        trend = {"kind": "trend", "label": "T", "lines": [{**self.LINE, "search": str(s.pk)}]}
        html = render(_panel(report([trend]), [s]))
        assert "Not observed" in html and "No data yet" not in html

    @pytest.mark.spec("req-compliance-core-panel-report-6")
    def test_one_failed_line_among_drawn_ones_is_named(self, results: dict[str, Any]) -> None:
        good, bad = _search("goodtrend"), _search("badtrend")
        results["goodtrend"] = [{"at": "2026-10-20T00:00:00Z", "value": 5}, {"at": "2026-10-21T00:00:00Z", "value": 6}]
        results["badtrend"] = RuntimeError("x")
        lines = [{**self.LINE, "search": str(good.pk)}, {**self.LINE, "label": "Responsibility", "search": str(bad.pk)}]
        html = render(_panel(report([{"kind": "trend", "label": "T", "lines": lines}]), [good, bad]))
        assert "<polyline" in html and "Responsibility: Not observed" in html


class TestConfigPairs:
    @pytest.mark.spec("req-compliance-core-panel-report-10")
    @pytest.mark.parametrize("half", [{"series_field": "series"}, {"series": "Overall"}])
    def test_a_series_filter_needs_both_halves(self, half: dict[str, str]) -> None:
        s = _search("p")
        line = {"label": "L", "search": str(s.pk), "x_field": "at", "value_field": "value", **half}
        panel = _panel(report([{"kind": "trend", "label": "T", "lines": [line]}]), [s])
        assert context(panel)["state"] == "bad_config"

    @pytest.mark.spec("req-compliance-core-panel-report-6")
    def test_a_failed_search_logs_its_class_and_never_its_message(
        self, results: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        s = _search("boom")
        results["boom"] = RuntimeError("secret detail")
        context(_panel(report([fig("N", s, "n")]), [s]))
        text = " ".join(r.getMessage() for r in caplog.records) + " ".join(str(r.exc_info) for r in caplog.records)
        assert "RuntimeError" in text and "secret detail" not in text


class TestStyleAndSafety:
    @pytest.mark.spec("req-compliance-core-panel-report-13")
    def test_the_stylesheet_is_plain(self) -> None:
        css = (PACKAGE / "static" / "compliance_core" / "css" / "report.css").read_text(encoding="utf-8")
        for banned in ("box-shadow", "border-radius", "background:", "background-color", "gradient"):
            assert banned not in css, banned
        import re

        colours = set(re.findall(r"#[0-9a-fA-F]{3,6}", css))
        assert colours <= {"#111", "#555", "#f1f5f9", "#cbd5e1"}, colours  # ink and one grey, light and dark; no hue

    @pytest.mark.spec("req-compliance-core-panel-report-13")
    def test_the_ink_and_grey_follow_the_theme_on_screen_and_stay_dark_on_paper(self) -> None:
        """A hard-coded #111 is black on the dark theme's dark page; the colours are tokens the theme overrides."""
        css = (PACKAGE / "static" / "compliance_core" / "css" / "report.css").read_text(encoding="utf-8")
        assert ".tap-panel--report { --rpt-ink: #111; --rpt-muted: #555; }" in css
        assert '@media screen and (prefers-color-scheme: dark)' in css
        assert ':root:not([data-theme="light"]) .tap-panel--report { --rpt-ink: #f1f5f9; --rpt-muted: #cbd5e1; }' in css
        assert ':root[data-theme="dark"] .tap-panel--report { --rpt-ink: #f1f5f9; --rpt-muted: #cbd5e1; }' in css
        assert "@media screen {" in css  # the forced-dark values never reach a print

    @pytest.mark.spec("req-compliance-core-panel-report-14")
    def test_it_has_a_print_block_that_keeps_sections_and_honours_the_break(self) -> None:
        css = (PACKAGE / "static" / "compliance_core" / "css" / "report.css").read_text(encoding="utf-8")
        assert "@media print" in css and "break-inside: avoid" in css and "break-before: page" in css

    @pytest.mark.spec("req-compliance-core-panel-report-14")
    def test_page_break_before_sets_the_class(self, results: dict[str, Any]) -> None:
        panel = _panel(report([{"kind": "rule"}], page_break_before=True), [])
        assert "rpt--break" in render(panel)
        assert "rpt--break" not in render(_panel(report([{"kind": "rule"}]), []))

    @pytest.mark.spec("req-compliance-core-panel-report-15")
    def test_the_cut_line_is_drawn_only_when_set(self) -> None:
        assert 'class="rpt-cut"' in render(_panel(report([{"kind": "rule"}], cut_line="Internal"), []))
        html = render(_panel(report([{"kind": "rule"}]), []))
        assert "rpt-cut" not in html

    @pytest.mark.spec("req-compliance-core-panel-report-16")
    def test_markup_in_config_and_rows_renders_as_text(self, results: dict[str, Any]) -> None:
        s = _search("x")
        results["x"] = [{"n": "<script>alert(1)</script>", "name": "<b>bold</b>"}]
        item = {
            "kind": "list",
            "search": str(s.pk),
            "label_field": "name",
            "columns": [{"field": "n", "title": "<i>T</i>", "format": "text"}],
        }
        panel = _panel(
            {
                "title": "<script>x</script>",
                "sections": [{"heading": "<u>H</u>", "items": [fig("<b>L</b>", s, "n", "text"), item]}],
            },
            [s],
        )
        html = render(panel)
        assert "<script>" not in html and "<b>" not in html and "<u>" not in html and "<i>" not in html
        assert "&lt;script&gt;" in html and "&lt;b&gt;L&lt;/b&gt;" in html

    @pytest.mark.spec("req-compliance-core-panel-report-16")
    def test_only_numbers_reach_the_svg_attributes(self) -> None:
        rows = [{"at": "2026-10-20T00:00:00Z", "value": 1, "series": 'x" onload="evil'}]
        out = layout.build_trend(
            [{"label": 'a" b', "search": "k", "x_field": "at", "value_field": "value"}], {"k": rows}, 0, 100
        )
        assert all(ch in "0123456789., " for ch in out["lines"][0]["points"])
