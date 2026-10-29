"""Finding — a single instance of non-compliance or risk observed against an asset."""

from typing import Any, ClassVar

from django.db import models

from tap_grid.models import BaseModel

#: A detection time is an instant, so a value must carry a time part. The `pattern` refuses a bare
#: date ("2026-09-25"), which the date-time field would otherwise read as midnight and so invent a
#: precision the producer never gave, shifting a deadline counted from it by up to a day.
_DETECTION_TIME_SCHEMA: dict[str, Any] = {
    "type": ["string", "null"],
    "format": "date-time",
    "pattern": r"^\d{4}-\d{2}-\d{2}T",
}


class ComplianceFinding(BaseModel):
    """A finding is the bridge between an asset in the graph and a compliance requirement.

    v1 shape is deliberately minimal: name, description, status. Lifecycle events
    (being granted an exception, being resolved) are modeled as separate entities
    connected by edges — not as fields on the finding. Exception coverage is a
    graph-relational fact expressed via `COVERS_COMPLIANCE_FINDING` edges and queried
    via traversal; it does not project onto `status`.

    Regime-agnostic substrate: a finding is a finding under any regime (FedRAMP,
    SOC2, CMMC, ISO). The regime is layered per-instance, not baked into the model.

    Identity (`req-compliance-core-identity`): a finding is found again by the producer
    that asserted it and the key that producer uses — `("source", "source_key")`. That is
    the data contract a minting plugin owes this one: a producer that writes neither field
    gets a FRESH node on every run rather than an error, because a search over holes is
    honestly "not found" rather than a match on nothing.

    Detection time (`req-compliance-core-finding-detection`): `first_detected_at` is when the
    producer first detected the finding, null until a source says. It is a fact about the
    finding, not a judgement, and FedRAMP's vulnerability reporting rules count their evaluation
    deadline from it.

    Spec: plugins/compliance_core/specs/spec-compliance-core-v0.md
    """

    ENTITY_TYPE: ClassVar[str] = "compliance_core__compliance_finding"
    # WHO said it, and WHAT THEY CALL IT. Nothing else on this model identifies anything:
    # `name`, `summary`, `description` and `status` all describe the verdict, and two scanners
    # can produce the same words about different places. The facts that make a finding findable
    # again live in the producer's world — `acme/app#code_scanning#7` for github_core — so the
    # model carries them as columns rather than leaving them only inside a producer's id recipe,
    # where the generated search could never filter them (Issue# 8 - tap-plugin-compliance-core,
    # ruled by George 2026-09-20; the same answer as github-core#164/#165 one level up).
    # `source` namespaces `source_key`, so two producers can never collide and neither has to
    # know the other's keying rules. compliance_core never parses `source_key`.
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("source", "source_key")
    ENTITY_NAME: ClassVar[str] = "Finding"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "A single instance of non-compliance or risk observed against an asset, "
        "related to one or more compliance requirements."
    )
    ENTITY_ICON: ClassVar[str] = "finding"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "finding"}

    _STATUS_VALUES = ["open", "resolved"]

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = {
        "source": {"type": "string", "maxLength": 64},
        "source_key": {"type": "string", "maxLength": 512},
        "name": {"type": "string", "minLength": 1},
        "summary": {"type": "string"},
        "description": {"type": "string"},
        "status": {"type": "string", "enum": _STATUS_VALUES},
        "first_detected_at": _DETECTION_TIME_SCHEMA,
    }

    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        "source": {"validation": "jsonschema", "schema": {"type": "string", "maxLength": 64}},
        "source_key": {"validation": "jsonschema", "schema": {"type": "string", "maxLength": 512}},
        "name": {
            "validation": "jsonschema",
            "schema": {"type": "string", "minLength": 1},
        },
        "summary": {"validation": "jsonschema", "schema": {"type": "string"}},
        "description": {"validation": "jsonschema", "schema": {"type": "string"}},
        "status": {
            "validation": "jsonschema",
            "schema": {"type": "string", "enum": _STATUS_VALUES},
        },
        "first_detected_at": {"validation": "jsonschema", "schema": _DETECTION_TIME_SCHEMA},
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["name"]

    #: The producer that asserted this finding — the plugin slug of whoever minted it
    #: ("github_core"). Half of the natural key: it namespaces `source_key`.
    source = models.CharField(max_length=64, blank=True, default="")
    #: What the producing system calls this finding, verbatim ("acme/app#code_scanning#7").
    #: Opaque here: only the producer's namespace gives it meaning, and compliance_core
    #: never parses it.
    source_key = models.CharField(max_length=512, blank=True, default="")
    name = models.CharField(max_length=255, blank=True, default="")
    summary = models.CharField(max_length=500, blank=True, default="")
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, blank=True, default="open", db_index=True)
    #: When the producer first detected this finding, as the producer's own record gives it (a
    #: GitHub alert's `created_at`; the production time of the earliest SBOM that reported it).
    #: `null` is unobserved: no source supplied it, and it is never defaulted to the time this grid
    #: first saw the finding. Not part of the identity. On a core with the keep-absent upsert, a node under
    #: an existing key changes only the fields it carries: omitting this keeps the stored value and an
    #: explicit null clears it; an older core replaces the row
    #: (`req-compliance-core-finding-detection`).
    first_detected_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="When the producer first detected the finding. Null = unobserved.",
    )

    class Meta(BaseModel.Meta):
        db_table = "compliance_core__compliance_finding"

    def get_name(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.get_name()
