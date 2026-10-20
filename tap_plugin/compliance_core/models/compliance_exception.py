"""Exception — a formal acceptance of one or more findings."""

from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import models

from tap_grid.models import BaseModel

_KIND_VALUES = [
    "false-positive",
    "not-affected",
    "mitigated",
    "operational-requirement",
    "accepted-risk",
]
#: The five OpenVEX `not_affected` justification labels, in kebab-case.
_JUSTIFICATION_VALUES = [
    "component-not-present",
    "vulnerable-code-not-present",
    "vulnerable-code-not-in-execute-path",
    "vulnerable-code-cannot-be-controlled-by-adversary",
    "inline-mitigations-already-exist",
]
#: An instant, so a value must carry a time part (a bare date would read as midnight).
INSTANT_SCHEMA: dict[str, Any] = {
    "type": ["string", "null"],
    "format": "date-time",
    "pattern": r"^\d{4}-\d{2}-\d{2}T",
}

_FIELD_SCHEMAS: dict[str, Any] = {
    "source": {"type": "string", "maxLength": 64},
    "source_key": {"type": "string", "maxLength": 512},
    "name": {"type": "string", "minLength": 1},
    "description": {"type": "string"},
    "status": {"type": "string", "enum": ["active", "expired", "revoked"]},
    "kind": {"type": ["string", "null"], "enum": [*_KIND_VALUES, None]},
    "justification": {"type": ["string", "null"], "enum": [*_JUSTIFICATION_VALUES, None]},
    "approver": {"type": ["string", "null"], "maxLength": 200},
    "granted_at": INSTANT_SCHEMA,
    "review_by": INSTANT_SCHEMA,
    "expires_at": INSTANT_SCHEMA,
    "verify_within_hours": {"type": ["integer", "null"], "minimum": 1},
}


class ComplianceException(BaseModel):
    """An exception covers one or more findings, formally accepting the risk they represent.

    The Python class is `ComplianceException` rather than `Exception` to avoid
    shadowing the Python built-in in any module that imports this model. The
    entity-type slug is `compliance_core__compliance_exception` — that's what
    GRIFT, the service layer, and the rest of TAP see externally.

    Regime-agnostic substrate: an exception formally accepts a finding under any
    regime; the regime is layered per-instance, not baked into the model.

    An exception is the rule, not what it covers. It carries the fields a decision needs
    (`kind`, `justification`, `approver`, `granted_at`, `review_by`, `expires_at`,
    `verify_within_hours`), all nullable so every producer that mints one today keeps working.
    What it covers lives on its instances (`compliance_exception_instance`), which it contains.
    By convention the `description` carries the business rationale.

    Identity (`req-compliance-core-identity`): found again by the system of record that
    granted it and that system's own reference — `("source", "source_key")`. A producer that
    writes neither gets a fresh node every run rather than an error, so writing them is the
    data contract a minting plugin owes this one.

    Spec: specs/spec-compliance-core-v0.md (`req-compliance-core-exception`)
    """

    ENTITY_TYPE: ClassVar[str] = "compliance_core__compliance_exception"
    # WHO granted it, and WHAT THEY CALL IT. An exception is a decision recorded in some system
    # of record — a GRC tool, a risk register, a ticket — and that system's own reference is the
    # only stable handle on it; `name` is a label a reviewer rewrites and `status` is the thing
    # that CHANGES (active → expired → revoked), which is exactly what a key must not be
    # (Issue# 8 - tap-plugin-compliance-core). An exception authored by hand inside TAP carries
    # neither field, is created once by an explicit write, and is never re-observed — so nothing
    # is lost there; what would be lost under KEYLESS is the re-import of an exception register.
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("source", "source_key")
    ENTITY_NAME: ClassVar[str] = "Exception"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "A formal acceptance of one or more findings, typically recording "
        "the rationale for not remediating."
    )
    ENTITY_ICON: ClassVar[str] = "exception"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "exception"}

    _STATUS_VALUES = ["active", "expired", "revoked"]

    #: Instances are parts of their exception: deleting it with `cascade="contained"` retires them.
    #: The exception and the finding, vulnerability and anchors an instance points at are not.
    OUTBOUND_EDGES: ClassVar[list[dict[str, Any]]] = [
        {
            "nodes": [{"type": "compliance_core__compliance_exception_instance"}],
            "edges": [{"type": "GRANTS_COMPLIANCE_EXCEPTION_INSTANCE__compliance_core"}],
        },
    ]
    CONTAINMENT_EDGES: ClassVar[tuple[str, ...]] = ("GRANTS_COMPLIANCE_EXCEPTION_INSTANCE__compliance_core",)

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = _FIELD_SCHEMAS
    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        name: {"validation": "jsonschema", "schema": schema} for name, schema in _FIELD_SCHEMAS.items()
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["name"]

    #: The producer that asserted this exception — the slug of the plugin that minted it,
    #: never a display name. Half of the natural key: it namespaces `source_key`, so
    #: two producers can never collide.
    source = models.CharField(max_length=64, blank=True, default="")
    #: What the producing system calls this exception, verbatim ("GRC-1184").
    #: Opaque here: only the producer's namespace gives it meaning, and compliance_core
    #: never parses it.
    source_key = models.CharField(max_length=512, blank=True, default="")
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, blank=True, default="active", db_index=True)
    #: What sort of decision this is. Null = not observed; an exception with no kind covers nothing.
    kind = models.CharField(  # noqa: DJ001  (req-compliance-core-exception: null = unobserved)
        max_length=32,
        null=True,
        blank=True,
        default=None,
        help_text="Sort of decision: false-positive, not-affected, mitigated, operational-requirement, "
        "accepted-risk. Null = not observed.",
    )
    #: Why a `not-affected` claim holds (an OpenVEX label). Refused with any other kind.
    justification = models.CharField(  # noqa: DJ001  (req-compliance-core-exception: null = unobserved)
        max_length=64,
        null=True,
        blank=True,
        default=None,
        help_text="OpenVEX justification label; only with kind not-affected. Null = none given.",
    )
    approver = models.CharField(  # noqa: DJ001  (req-compliance-core-exception: null = unobserved)
        max_length=200,
        null=True,
        blank=True,
        default=None,
        help_text="Person or role that approved the decision. Null = not observed.",
    )
    granted_at = models.DateTimeField(
        null=True, blank=True, default=None, help_text="When the decision was made. Null = not observed."
    )
    review_by = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="When a person is asked to look at it again. Null = no review date set (reported, not 'never').",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Hard ceiling after which the exception covers nothing. Null = no ceiling.",
    )
    verify_within_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=None,
        help_text="How old an instance's last successful check may be before it stops counting. "
        "Null = never fresh (covers nothing until set).",
    )

    class Meta(BaseModel.Meta):
        db_table = "compliance_core__compliance_exception"

    def validate(self) -> None:
        """`justification` is an OpenVEX `not_affected` label, so it is allowed only with that kind."""
        if self.justification and self.kind != "not-affected":
            raise ValidationError(
                {"justification": ["justification is allowed only when kind is 'not-affected'."]}
            )

    def get_name(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.get_name()
