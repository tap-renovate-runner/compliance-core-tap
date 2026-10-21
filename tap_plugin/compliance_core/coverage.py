"""The coverage calculations, pure and shared (`req-compliance-core-dimension-mapping-totals`).

Django-free on purpose: any runner or panel can import these two functions, so a figure shown on a card and the same figure
drawn on a chart are computed in one place and always agree.

    plain_mean(values)      the unweighted mean of the numbers in ``values`` to one decimal; ``None`` and non-numbers (and a
                            bool, which is not a measurement) are ignored; ``None`` when none remain
    totals_from_rows(rows)  the totals of a (grouped) mapping summary: the plain-average coverage and the pooled counts
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def plain_mean(values: Iterable[Any]) -> float | None:
    """The unweighted mean of the numbers in ``values``, rounded to one decimal; ``None`` when there is none."""
    numbers = [v for v in values if _is_number(v)]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)


def _count(row: dict[str, Any], key: str) -> int:
    value = row.get(key)
    return int(value) if _is_number(value) else 0


def totals_from_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """One dict of totals from the rows of a mapping summary.

    ``groups`` counts the rows that have a ``percent_mapped`` (a row with no entities has none); ``percent_overall`` is the
    plain mean of those percents; ``denominator``, ``mapped``, ``unmapped``, ``mapped_incorrectly`` and ``no_rule`` are sums
    over every row; ``percent_pooled`` is ``mapped`` over ``denominator`` to one decimal, ``None`` at a zero denominator.
    """
    listed = list(rows)
    percents = [r.get("percent_mapped") for r in listed]
    totals = {
        key: sum(_count(r, key) for r in listed)
        for key in ("denominator", "mapped", "unmapped", "mapped_incorrectly", "no_rule")
    }
    return {
        "groups": sum(1 for p in percents if _is_number(p)),
        "percent_overall": plain_mean(percents),
        **totals,
        "percent_pooled": round(100 * totals["mapped"] / totals["denominator"], 1) if totals["denominator"] else None,
    }
