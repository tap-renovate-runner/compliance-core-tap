"""Exception instance — one exception applied to one vulnerability within one declared scope."""

from typing import Any, ClassVar

from django.db import models
from tap_plugin.compliance_core.models.compliance_exception import INSTANT_SCHEMA

from tap_grid.models import BaseModel

_OUTCOME_VALUES = ["held", "falsified"]

_FIELD_SCHEMAS: dict[str, Any] = {
    "source": {"type": "string", "maxLength": 64},
    "source_key": {"type": "string", "maxLength": 512},
    "name": {"type": "string", "minLength": 1},
    "outcome": {"type": ["string", "null"], "enum": [*_OUTCOME_VALUES, None]},
    "verified_at": INSTANT_SCHEMA,
    "anchor_count": {"type": "integer", "minimum": 1},
    "detail": {"type": ["string", "null"]},
}


class ComplianceExceptionInstance(BaseModel):
    """One exception applied to one vulnerability in one scope, with the last check's result.

    The exception is the rule; this is "this rule, here, last checked then, held". Which
    vulnerability and which scope anchors it applies to are edges (`EXEMPTS_COMPLIANCE_VULNERABILITY`,
    `SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET`); which findings it covers is `COVERS_COMPLIANCE_FINDING`.
    Whether a finding is covered is computed when asked and never stored here.

    It is a node because it is deleted with its exception, outlives the finding it covers, and carries
    a check result that belongs to neither endpoint. It has no `status`: its lifecycle is `outcome`
    plus retirement.

    Spec: specs/spec-compliance-core-v0.md (`req-compliance-core-exception-instance`)
    """

    ENTITY_TYPE: ClassVar[str] = "compliance_core__compliance_exception_instance"
    # Deterministic from the parent exception's key, the vulnerability id and the anchors, so the
    # same application is found again on every run. compliance_core never parses `source_key`.
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("source", "source_key")
    ENTITY_NAME: ClassVar[str] = "Exception Instance"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "One exception applied to one vulnerability within one declared scope, with the result of "
        "the last check that tried to show the application false."
    )
    ENTITY_ICON: ClassVar[str] = "exception-instance"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "exception-instance"}

    OUTBOUND_EDGES: ClassVar[list[dict[str, Any]]] = [
        {
            "nodes": [{"type": "compliance_core__compliance_vulnerability"}],
            "edges": [{"type": "EXEMPTS_COMPLIANCE_VULNERABILITY__compliance_core"}],
        },
        # No "nodes" key: an anchor is whatever the producer's world offers (a package, an image,
        # an SBOM document), and compliance_core must not name a producer's types.
        {"edges": [{"type": "SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET__compliance_core"}]},
        {
            "nodes": [{"type": "compliance_core__compliance_finding"}],
            "edges": [{"type": "COVERS_COMPLIANCE_FINDING__compliance_core"}],
        },
        {
            "nodes": [{"type": "compliance_core__compliance_evidence"}],
            "edges": [{"type": "CITES_COMPLIANCE_EVIDENCE__compliance_core"}],
        },
    ]
    INBOUND_EDGES: ClassVar[list[dict[str, Any]]] = [
        {
            "nodes": [{"type": "compliance_core__compliance_exception"}],
            "edges": [{"type": "GRANTS_COMPLIANCE_EXCEPTION_INSTANCE__compliance_core"}],
        },
        {
            "nodes": [{"type": "compliance_core__compliance_scan_run"}],
            "edges": [{"type": "SCANNED_COMPLIANCE_TARGET__compliance_core"}],
        },
    ]

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = _FIELD_SCHEMAS
    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        name: {"validation": "jsonschema", "schema": schema} for name, schema in _FIELD_SCHEMAS.items()
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["name", "anchor_count"]

    #: The producer that asserted this instance (the checker plugin's slug). Half of the natural key.
    source = models.CharField(max_length=64, blank=True, default="")
    #: What the producer calls this application, verbatim. Opaque here.
    source_key = models.CharField(max_length=512, blank=True, default="")
    name = models.CharField(max_length=255, blank=True, default="")
    #: Result of the last check: held or falsified. Null = never checked, which is uncovered.
    outcome = models.CharField(  # noqa: DJ001  (req-compliance-core-exception-instance: null = unobserved)
        max_length=16,
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="Result of the last check: held or falsified. Null = never checked.",
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="When the last check ran. Null = never.",
    )
    anchor_count = models.PositiveIntegerField(
        help_text="How many scope anchors the producer declared; coverage requires that many live."
    )
    detail = models.TextField(  # noqa: DJ001  (req-compliance-core-exception-instance: null = unobserved)
        null=True, blank=True, default=None, help_text="What the check saw, in the checker's words."
    )

    class Meta(BaseModel.Meta):
        db_table = "compliance_core__compliance_exception_instance"

    def get_name(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.get_name()
