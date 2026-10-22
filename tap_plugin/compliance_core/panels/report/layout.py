"""The report panel's pure parts: value formats and trend geometry (`req-compliance-core-panel-report`).

Django-free and Search-free: numbers and strings in, display values and plain numbers out. The panel and the template draw
nothing that is not produced here from validated numbers, so no row text ever reaches markup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

NOT_OBSERVED = "Not observed"
FORMATS = ("count", "percent", "date", "datetime", "text")

# Trend frame, in SVG user units (the SVG scales to its container).
WIDTH, HEIGHT = 640, 170
LEFT, RIGHT, TOP, BOTTOM = 38, 120, 12, 28
DASHES = ("", "6 3", "2 3", "8 3 2 3")  # the second line onward are told apart by dash pattern, never by colour


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def format_value(value: Any, kind: str) -> str:
    """The display text of ``value`` in format ``kind``; a value that does not fit is ``Not observed``, never 0 or blank."""
    if value is None:
        return NOT_OBSERVED
    if kind == "count":
        return f"{round(value):,}" if is_number(value) else NOT_OBSERVED
    if kind == "percent":
        return f"{value:.1f}%" if is_number(value) else NOT_OBSERVED
    if kind in ("date", "datetime"):
        moment = parse_time(value)
        if moment is None:
            return NOT_OBSERVED
        moment = moment.astimezone(UTC)
        return moment.strftime("%Y-%m-%d") if kind == "date" else moment.strftime("%Y-%m-%d %H:%M UTC")
    if kind == "text":
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            return NOT_OBSERVED
        text = str(value)
        return text if text else "(empty)"
    return NOT_OBSERVED


def pick_row(rows: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any] | None:
    """The row a figure reads: the first one where ``where.field`` equals ``where.equals``, else the row at ``row`` (default 0)."""
    where = item.get("where")
    if where:
        for row in rows:
            if row.get(where["field"]) == where["equals"]:
                return row
        return None
    index = item.get("row", 0)
    return rows[index] if 0 <= index < len(rows) else None


def _number_text(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))


def build_trend(
    lines: list[dict[str, Any]],
    rows_by_search: dict[str, list[dict[str, Any]] | None],
    y_min: float,
    y_max: float,
) -> dict[str, Any]:
    """The geometry of one trend: ``{"empty": bool, "lines": [...], "x_first", "x_last", "y_min", "y_max", ...}``.

    A line reads one series (``series_field`` equal to ``series``, else every row), ordered by ``x_field``; a point needs a
    numeric ``value_field`` and is otherwise not a point. The y range is fixed by the caller; a value outside it is drawn at
    the edge. x is time when every x parses, else the order of the rows.
    """
    series_points: list[tuple[dict[str, Any], list[tuple[Any, float]]]] = []
    for entry in lines:
        rows = rows_by_search.get(entry["search"]) or []
        wanted = entry.get("series")
        field = entry.get("series_field")
        keep = [r for r in rows if not (field and wanted is not None) or r.get(field) == wanted]
        points = [(r.get(entry["x_field"]), r.get(entry["value_field"])) for r in keep]
        points = [(x, float(v)) for x, v in points if x is not None and is_number(v)]
        series_points.append((entry, points))
    every_x = [x for _, pts in series_points for x, _ in pts]
    if not every_x:
        return {"empty": True, "lines": []}
    times = [parse_time(x) for x in every_x]
    use_time = all(t is not None for t in times)

    def key(x: Any) -> float:
        return parse_time(x).timestamp() if use_time else 0.0  # type: ignore[union-attr]

    if use_time:
        ordered = sorted({key(x) for x in every_x})
    else:
        ordered = []
    lo, hi = (ordered[0], ordered[-1]) if ordered else (0.0, 0.0)
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    span = (y_max - y_min) or 1.0

    def px(index: int, count: int, x: Any) -> float:
        if use_time:
            return LEFT + (plot_w / 2 if hi == lo else (key(x) - lo) / (hi - lo) * plot_w)
        return LEFT + (plot_w / 2 if count <= 1 else index / (count - 1) * plot_w)

    def py(v: float) -> float:
        clamped = min(max(v, y_min), y_max)
        return TOP + plot_h - (clamped - y_min) / span * plot_h

    drawn = []
    for position, (entry, points) in enumerate(series_points):
        pts = sorted(points, key=lambda p: key(p[0])) if use_time else points
        coords = [(round(px(i, len(pts), x), 1), round(py(v), 1), x, v) for i, (x, v) in enumerate(pts)]
        drawn.append(
            {
                "label": entry["label"],
                "dash": DASHES[position % len(DASHES)],
                "points": " ".join(f"{cx},{cy}" for cx, cy, _, _ in coords),
                "single": coords[0][:2] if len(coords) == 1 else None,
                "end_x": round(coords[-1][0] + 6, 1) if coords else None,
                "end_y": round(coords[-1][1] + 3, 1) if coords else None,
                "end_value": _number_text(coords[-1][3]) if coords else None,
                "table": [
                    {"x": format_value(x, "datetime") if use_time else str(x), "value": _number_text(v)}
                    for _, _, x, v in coords
                ],
            }
        )
    first = format_value(min(every_x, key=key), "datetime") if use_time else str(every_x[0])
    last = format_value(max(every_x, key=key), "datetime") if use_time else str(every_x[-1])
    return {
        "empty": False,
        "lines": drawn,
        "x_first": first,
        "x_last": last,
        "y_min": _number_text(y_min),
        "y_max": _number_text(y_max),
        "frame": {
            "width": WIDTH,
            "height": HEIGHT,
            "left": LEFT,
            "right": WIDTH - RIGHT,
            "top": TOP,
            "base": HEIGHT - BOTTOM,
            "label_y": HEIGHT - 8,
        },
    }
