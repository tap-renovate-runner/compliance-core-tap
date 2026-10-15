"""Scanner — one installed instance of a detection tool, at one place."""

from typing import Any, ClassVar

from django.db import models

from tap_grid.models import BaseModel


class ComplianceScanner(BaseModel):
    """A scanner is an INSTALLED INSTANCE, not a product: Trivy as the `scan` job of one workflow,
    not Trivy in general. The same tool installed in two workflows is two scanners; a platform
    (Wiz, a SIEM) installed once is one.

    **Never a version.** A version changes under an unchanged install; it lives on the scan run
    (`compliance_scan_run.tool_version`), which is what executed. Where the install is, as the
    data says it, is `locator`; when the place is itself a node on the grid, `RUNS_AT_LOCATION`
    draws the edge and `locator` keeps the words.

    `configuration` is null until a source supplies it. No source does yet; the field exists so
    the rules a scanner runs under (a workflow step's inputs, a platform's policy) have somewhere
    to land without a migration, and it is added now because a one-time migration was the
    cheaper moment (the type is new), not because anything fills it.

    Regime-agnostic substrate: a scanner exists under any compliance regime.

    Spec: specs/spec-compliance-core-v0.md (req-compliance-core-scanner).
    """

    ENTITY_TYPE: ClassVar[str] = "compliance_core__compliance_scanner"
    # WHO said it, and WHAT THEY CALL IT, exactly as `compliance_finding` keys. `scanner_key` is
    # the producer's slug for this install (product plus where it is installed), opaque here;
    # `source` is the producing plugin's slug and namespaces it. Rejected: `scanner_key` alone.
    # Two producers that mint the same slug would merge into one scanner silently and
    # unrecoverably, where a false split is visible and reconcilable (ruled by George 2026-10-15,
    # Issue# 32 - this repo). compliance_core never parses either half.
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("source", "scanner_key")
    ENTITY_NAME: ClassVar[str] = "Scanner"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "A detection tool installed at one place (Trivy as the scan job of one workflow), not the "
        "product in general. Never carries a version; each execution is a scan run."
    )
    ENTITY_ICON: ClassVar[str] = "scanner"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "scanner"}

    OUTBOUND_EDGES: ClassVar[list[dict[str, Any]]] = [
        {
            "nodes": [{"type": "compliance_core__compliance_scan_run"}],
            "edges": [{"type": "PERFORMS_COMPLIANCE_SCAN_RUN__compliance_core"}],
        },
        {
            "nodes": [{"type": "compliance_core__compliance_finding"}],
            "edges": [{"type": "DETECTS_COMPLIANCE_FINDING__compliance_core"}],
        },
        # No "nodes" key: the place is whatever the producer's world has (see the edge's description).
        {"edges": [{"type": "RUNS_AT_LOCATION__compliance_core"}]},
    ]

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = {
        "source": {"type": "string", "maxLength": 64},
        "scanner_key": {"type": "string", "minLength": 1, "maxLength": 512},
        "name": {"type": "string", "minLength": 1},
        "configuration": {"type": ["object", "null"]},
        "locator": {"type": ["string", "null"]},
    }

    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        name: {"validation": "jsonschema", "schema": schema} for name, schema in FIELD_CRUD_SCHEMA.items()
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["scanner_key", "name"]

    #: The producer that asserted this scanner: the plugin slug of whoever minted it
    #: ("github_core"). Half of the natural key: it namespaces `scanner_key`.
    source = models.CharField(max_length=64, blank=True, default="")
    scanner_key = models.CharField(
        max_length=512,
        blank=True,
        default="",
        db_index=True,
        help_text="Slug of this install: the product and where it is installed. Opaque here. Half of the identity.",
    )
    name = models.CharField(max_length=255, blank=True, default="", help_text="The product (Trivy, CodeQL, Grype).")
    configuration = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text="How this install is configured, as a source supplied it. Null = unobserved (no source does yet).",
    )
    locator = models.TextField(  # noqa: DJ001  (req-compliance-core-scanner-3)
        null=True,
        blank=True,
        default=None,
        help_text="The text the data gave for where it is installed, verbatim "
        "(unified-systems-com/tap/.github/workflows/publish-images.yml:scan). Null = unobserved.",
    )

    class Meta(BaseModel.Meta):
        db_table = "compliance_core__compliance_scanner"

    def get_name(self) -> str:
        # Two installs of one product share `name`; the locator is what tells them apart on screen.
        if self.locator:
            return f"{self.name} ({self.locator})"
        return self.name or self.scanner_key

    def __str__(self) -> str:
        return self.get_name()
