"""The report panel type: a whole plain report drawn from several Searches (`req-compliance-core-panel-report`).

A report is read by leadership and sent to agencies, so it is drawn as text and vector lines that print as they appear: a
title, sections, label-and-figure lines, short lists and small trend lines, with no script and no colour that carries meaning.
The panel runs only the Searches it has a ``USES_SEARCH`` edge to, each once per render through ``execute_search``, and
writes nothing. A figure it cannot read is ``Not observed``, never 0 and never blank.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

import jsonschema

from .layout import FORMATS, NOT_OBSERVED, build_trend, format_value, pick_row

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tap_web.models import Panel

logger = logging.getLogger(__name__)

_STR: dict[str, Any] = {"type": "string", "minLength": 1, "maxLength": 200}
_FORMAT: dict[str, Any] = {"type": "string", "enum": list(FORMATS)}

REPORT_PANEL_CONFIG_SCHEMA: dict[str, Any] = {
    "description": (
        "Config of a report panel: a title and sections of figure, list, trend and rule items, each reading a Search "
        "the panel is linked to by a USES_SEARCH edge. Config holds text only, never HTML."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["sections"],
    "properties": {
        "title": {"description": "The report's title, shown once at the top.", **_STR},
        "show_as_of": {
            "description": "Show 'As Of <render time, UTC>' under the title. Default true.",
            "type": "boolean",
        },
        "page_break_before": {
            "description": "Start a new printed page before this report. Default false.",
            "type": "boolean",
        },
        "cut_line": {
            "description": "A word (for example Internal) carried by a dashed hairline at the top: the mark below which a report is not for sending out.",
            **_STR,
        },
        "hide_header": {"description": "True hides the panel header bar.", "type": "boolean"},
        "sections": {
            "description": "The report's sections, in order.",
            "type": "array",
            "minItems": 1,
            "maxItems": 40,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["heading", "items"],
                "properties": {
                    "heading": {"description": "The section's heading.", **_STR},
                    "items": {
                        "description": "The section's items, in order.",
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 60,
                        "items": {
                            "oneOf": [
                                {"$ref": "#/$defs/figure"},
                                {"$ref": "#/$defs/list"},
                                {"$ref": "#/$defs/trend"},
                                {"$ref": "#/$defs/rule"},
                            ]
                        },
                    },
                },
            },
        },
    },
    "$defs": {
        "figure": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "label", "search", "field", "format"],
            "properties": {
                "kind": {"description": "A label at the left and a figure at the right.", "const": "figure"},
                "label": {"description": "The line's label.", **_STR},
                "search": {"description": "Entity id of a linked Search.", **_STR},
                "field": {"description": "The row field holding the figure.", **_STR},
                "format": {
                    "description": "How the figure is shown: count, percent, date, datetime or text.",
                    **_FORMAT,
                },
                "row": {"description": "Index of the row to read. Default 0.", "type": "integer", "minimum": 0},
                "where": {
                    "description": "Read the first row where this field equals this value, instead of a row index.",
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["field", "equals"],
                    "properties": {
                        "field": {"description": "The row field to test.", **_STR},
                        "equals": {
                            "description": "The value the field must equal.",
                            "type": ["string", "number", "boolean"],
                        },
                    },
                },
                "of": {"description": "A second field of the same row, shown as 'of <n>' (a count).", **_STR},
            },
        },
        "list": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "search", "label_field", "columns"],
            "properties": {
                "kind": {"description": "Rows of aligned text under a hairline header.", "const": "list"},
                "search": {"description": "Entity id of a linked Search.", **_STR},
                "label_field": {"description": "The row field shown first, as the row's label.", **_STR},
                "columns": {
                    "description": "Up to four further columns.",
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["field", "title", "format"],
                        "properties": {
                            "field": {"description": "The row field shown in this column.", **_STR},
                            "title": {"description": "The column's header.", **_STR},
                            "format": {"description": "How the value is shown.", **_FORMAT},
                        },
                    },
                },
                "title": {"description": "Header of the label column.", **_STR},
                "limit": {
                    "description": "Most rows shown; the rest are counted. Default 20.",
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                },
            },
        },
        "trend": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "label", "lines"],
            "properties": {
                "kind": {"description": "A small vector line chart, one line per entry.", "const": "trend"},
                "label": {"description": "The chart's title.", **_STR},
                "lines": {
                    "description": "The lines, at most six.",
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["label", "search", "x_field", "value_field"],
                        "dependentRequired": {"series_field": ["series"], "series": ["series_field"]},
                        "properties": {
                            "label": {"description": "The line's name, written at its end.", **_STR},
                            "search": {"description": "Entity id of a linked Search.", **_STR},
                            "x_field": {"description": "The row field holding the time.", **_STR},
                            "value_field": {"description": "The row field holding the number.", **_STR},
                            "series_field": {"description": "Keep only rows whose field equals series.", **_STR},
                            "series": {"description": "The value series_field must equal.", **_STR},
                        },
                    },
                },
                "y_min": {"description": "Bottom of the fixed y range. Default 0.", "type": "number"},
                "y_max": {"description": "Top of the fixed y range. Default 100.", "type": "number"},
            },
        },
        "rule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind"],
            "properties": {"kind": {"description": "A hairline.", "const": "rule"}},
        },
    },
}


def _search_ids(config: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for section in config.get("sections", []):
        for item in section["items"]:
            if item["kind"] in ("figure", "list"):
                ids.add(item["search"])
            elif item["kind"] == "trend":
                ids.update(line["search"] for line in item["lines"])
    return ids


def _linked_searches(panel: Panel) -> dict[str, Any]:
    """The Searches the panel has a USES_SEARCH edge to, by entity id."""
    from tap_grid.models import Edge, Search

    targets = [
        str(t)
        for t in Edge.objects.filter(from_entity=panel.entity, edge_type="USES_SEARCH").values_list(
            "to_entity_id", flat=True
        )
    ]
    return {str(s.entity_id): s for s in Search.objects.filter(entity_id__in=targets)} if targets else {}


def _run(search: Any, request: HttpRequest | None) -> list[dict[str, Any]] | None:
    """The rows of one Search, or None when it failed; the error text is logged, never shown."""
    try:
        from tap_grid.search import execute_search, inputs_from_query

        inputs = inputs_from_query(search, request.GET) if request is not None else {}
        result = execute_search(search, inputs or None, layer="extended")
    except Exception as exc:  # noqa: BLE001
        # The error text may carry query fragments or credentials, so only the Search id and the exception class are logged.
        logger.error("[7d1c] report panel search %s failed (%s)", getattr(search, "entity_id", "?"), type(exc).__name__)
        return None
    envelope = result["results"] if "results" in result else result
    return [r for r in (envelope.get("rows") or []) if isinstance(r, dict)]


class ReportPanelType:
    """compliance_core's report panel type (`req-compliance-core-panel-report-1`)."""

    slug: ClassVar[str] = "report"
    label: ClassVar[str] = "Report"
    view: ClassVar[str] = "compliance_core/panels/report.html"
    css: ClassVar[list[str]] = ["compliance_core/css/report.css"]
    js: ClassVar[list[str]] = []
    editor_view: ClassVar[str] = ""
    config_defaults: ClassVar[dict[str, Any]] = {}
    form_class: ClassVar[Any] = None

    @classmethod
    def get_view_context(cls, panel: Panel, request: HttpRequest) -> dict[str, Any]:
        config = dict(getattr(panel, "config", None) or {})
        try:
            jsonschema.validate(config, REPORT_PANEL_CONFIG_SCHEMA)
        except jsonschema.ValidationError as exc:
            return {"state": "bad_config", "detail": exc.message}
        linked = _linked_searches(panel)
        rows: dict[str, list[dict[str, Any]] | None] = {}
        for search_id in sorted(_search_ids(config) & set(linked)):  # one run per Search, and only a linked one
            rows[search_id] = _run(linked[search_id], request)
        failed = sorted({linked[i].name for i, r in rows.items() if r is None})
        sections = [
            {"heading": s["heading"], "items": [cls._item(i, rows, linked) for i in s["items"]]}
            for s in config["sections"]
        ]
        return {
            "state": "ok",
            "title": config.get("title"),
            "as_of": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC") if config.get("show_as_of", True) else None,
            "page_break_before": bool(config.get("page_break_before")),
            "cut_line": config.get("cut_line"),
            "sections": sections,
            "failed": failed,
            "not_observed": NOT_OBSERVED,
        }

    @staticmethod
    def _item(
        item: dict[str, Any], rows: dict[str, list[dict[str, Any]] | None], linked: dict[str, Any]
    ) -> dict[str, Any]:
        kind = item["kind"]
        if kind == "rule":
            return {"kind": "rule"}
        searches = [item["search"]] if kind in ("figure", "list") else [line["search"] for line in item["lines"]]
        if any(s not in linked for s in searches):
            return {
                "kind": "error",
                "text": "Configuration error: this line names a Search the panel is not linked to.",
            }
        if kind == "figure":
            data = rows.get(item["search"])
            row = pick_row(data, item) if data is not None else None
            value = row.get(item["field"]) if row else None
            of = None
            if row and item.get("of"):
                of = format_value(row.get(item["of"]), "count")
            return {"kind": "figure", "label": item["label"], "value": format_value(value, item["format"]), "of": of}
        if kind == "list":
            data = rows.get(item["search"]) or []
            limit = item.get("limit", 20)
            shown = data[:limit]
            return {
                "kind": "list",
                "title": item.get("title", ""),
                "columns": [c["title"] for c in item["columns"]],
                "rows": [
                    {
                        "label": format_value(r.get(item["label_field"]), "text"),
                        "cells": [format_value(r.get(c["field"]), c["format"]) for c in item["columns"]],
                    }
                    for r in shown
                ],
                "omitted": max(0, len(data) - len(shown)),
                "unavailable": rows.get(item["search"]) is None,
            }
        trend = build_trend(item["lines"], rows, float(item.get("y_min", 0)), float(item.get("y_max", 100)))
        return {"kind": "trend", "label": item["label"], "trend": trend}
