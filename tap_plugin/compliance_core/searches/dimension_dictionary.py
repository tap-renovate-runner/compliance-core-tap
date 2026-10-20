"""The dimension dictionary read, shared by the dimension Search runners.

A dimension key's own ``dimension`` node supplies the key's description; the ``dimension`` nodes named
``<key>.<value>`` supply the declared values and their descriptions (the dotted name carries the axis-to-value
relationship, ``spec-grid-dimension.md``). Read under the read rules Gryphon applies, with the caller's ``db_alias``.
"""

from __future__ import annotations

from tap_grid.gryphon import read_scope
from tap_grid.models import Dimension


def read_dictionary(key: str, *, db_alias: str) -> tuple[str | None, dict[str, str]]:
    """The key's description (None without a node) and ``{value: description}`` from the ``<key>.<value>`` nodes."""
    prefix = f"{key}."
    description: str | None = None
    declared: dict[str, str] = {}
    nodes = read_scope.node_relation(read_scope.DEFAULT_SCOPE, Dimension, db_alias=db_alias)
    for name, text in nodes.filter(name__startswith=key).values_list("name", "description"):
        if name == key:
            description = text
        elif name.startswith(prefix) and "." not in name[len(prefix) :]:
            declared[name[len(prefix) :]] = text
    return description, declared
