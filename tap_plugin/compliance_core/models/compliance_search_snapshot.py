"""Search snapshot — one run of one Search, with the rows it returned held inside."""

from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import models

from tap_grid.models import BaseModel

MAX_ROWS = 1000
MAX_PROPERTIES = 50
MAX_NAME = 128
MAX_STRING = 4096
MAX_INPUTS_TEXT = 65536

_SCALAR = {"type": ["string", "number", "boolean", "null"]}
_ROWS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "maxItems": MAX_ROWS,
    "items": {
        "type": "object",
        "maxProperties": MAX_PROPERTIES,
        "propertyNames": {"maxLength": MAX_NAME},
        "additionalProperties": {**_SCALAR, "maxLength": MAX_STRING},
    },
}
_FIELD_SCHEMAS: dict[str, Any] = {
    "name": {"type": "string", "minLength": 1},
    "source": {"type": "string", "minLength": 1, "maxLength": 64},
    "snapshot_key": {"type": "string", "minLength": 1, "maxLength": 512},
    "search_name": {"type": "string"},
    "observed_at": {"type": "string", "format": "date-time", "pattern": r"^\d{4}-\d{2}-\d{2}T"},
    "row_count": {"type": "integer", "minimum": 0},
    "rows": _ROWS_SCHEMA,
    "truncated": {"type": "boolean"},
    "inputs_text": {"type": "string", "maxLength": MAX_INPUTS_TEXT},
}


class ComplianceSearchSnapshot(BaseModel):
    """One run of one Search at one time, with the rows it returned held inside the node.

    The grid's history records a node's changes only, and a re-observation of an unchanged value is not a
    change, so a figure that sat still for a week would leave nothing to read it back from. A snapshot is
    therefore a node, written once and never updated: a second run is a second node under a new key. The node
    says nothing about what the Search measures, so it lives here beside the other regime-neutral types.

    `rows` holds at most 1000 rows of scalar values (a long string, a list or an object is the collector's to
    convert before it writes); `row_count` is the exact count, so `truncated` makes any loss visible.

    Spec: specs/spec-compliance-core-v0.md (req-compliance-core-search-snapshot).
    """

    ENTITY_TYPE: ClassVar[str] = "compliance_core__compliance_search_snapshot"
    # A snapshot is an observation made once, so there is nothing to re-observe: the key carries the time, and a
    # node sent again under an existing key would replace the row and null whatever it left out (Issue# 1071 - tap).
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("source", "snapshot_key")
    ENTITY_NAME: ClassVar[str] = "Search Snapshot"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "One run of one Search at one time, with the rows it returned held inside the node."
    )
    ENTITY_ICON: ClassVar[str] = "search-snapshot"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "search-snapshot"}

    OUTBOUND_EDGES: ClassVar[list[dict[str, Any]]] = [
        {
            "nodes": [{"type": "search"}],
            "edges": [{"type": "CAPTURES_SEARCH__compliance_core"}],
        },
    ]

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = _FIELD_SCHEMAS
    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        name: {"validation": "jsonschema", "schema": schema} for name, schema in _FIELD_SCHEMAS.items()
    }
    CREATE_REQUIRED: ClassVar[list[str]] = [
        "name",
        "source",
        "snapshot_key",
        "observed_at",
        "row_count",
        "rows",
        "truncated",
        "inputs_text",
    ]

    name = models.CharField(max_length=255, blank=True, default="")
    #: The plugin slug of the collector that wrote it. Half of the identity.
    source = models.CharField(max_length=64, blank=True, default="")
    #: `<search entity id>@<observed_at as UTC ISO 8601 to the microsecond>`. Half of the identity.
    snapshot_key = models.CharField(max_length=512, blank=True, default="")
    #: The Search's name when it ran; the edge names the Search, this keeps the snapshot readable after a rename.
    search_name = models.CharField(max_length=255, blank=True, default="")
    observed_at = models.DateTimeField(db_index=True, help_text="When the Search ran. Never null: a figure with no time is not a series.")
    row_count = models.PositiveIntegerField(help_text="The exact number of rows the Search returned.")
    #: The rows the Search returned at that moment (a named source: the module or ORM Search's result rows).
    rows = models.JSONField(default=list, blank=True, help_text="At most 1000 rows of scalar values; an empty list is a Search that returned none.")
    truncated = models.BooleanField(default=False, help_text="True when rows holds fewer rows than row_count.")
    inputs_text = models.TextField(blank=True, default="", help_text="The Search's inputs for the run, as canonical JSON text.")

    class Meta(BaseModel.Meta):
        db_table = "compliance_core__compliance_search_snapshot"

    def validate(self) -> None:
        """`truncated` must agree with the counts: false needs every row held, true needs fewer rows than the count."""
        held = len(self.rows) if isinstance(self.rows, list) else None
        if held is None:
            return  # the per-field check already refused a non-array
        if not self.truncated and held != self.row_count:
            raise ValidationError({"truncated": [f"truncated is false but rows holds {held} of {self.row_count} rows."]})
        if self.truncated and held >= self.row_count:
            raise ValidationError({"truncated": [f"truncated is true but rows holds {held} of {self.row_count} rows."]})

    def get_name(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.get_name()
