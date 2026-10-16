"""Scan run — one execution of a scanner."""

from typing import Any, ClassVar

from django.db import models

from tap_grid.models import BaseModel


class ComplianceScanRun(BaseModel):
    """One execution of a scanner: which version ran, against which commit and ref, and what it counted.

    A run sits between the scanner and its findings. A finding is opened by one run, re-confirmed
    by many and closed when a later run stops reporting it, and "the scanner failed" is a fact
    about a run, which is what a detection-health finding attaches to. A scanner with no
    discrete executions (Dependabot, a continuous service) has no runs and reports its findings
    directly with `DETECTS_COMPLIANCE_FINDING`.

    Where the producer has a vendor record of the same execution it lives beside this node as a
    detail twin (`github_core__code_scanning_analysis` for GitHub code scanning), the way a
    detail hangs off a finding. The fields this node repeats from that twin are
    `TAP-KNOWN-DUPE(scan-run-analysis-fields)` sites; see the spec.

    `outcome` is null where the producer did not observe one: a run derived from an alert's
    latest instance cannot say whether it succeeded. `results_count` null is unobserved, `0` is a
    run that reported nothing.

    Regime-agnostic substrate: a scan run exists under any compliance regime.

    Spec: specs/spec-compliance-core-v0.md (req-compliance-core-scan-run).
    """

    ENTITY_TYPE: ClassVar[str] = "compliance_core__compliance_scan_run"
    # WHO said it, and WHAT THEY CALL IT, exactly as `compliance_finding` keys. `run_key` is the
    # producer's key for this execution, opaque here; `source` is the producing plugin's slug and
    # namespaces it (a false merge of two runs is silent and unrecoverable, a false split is
    # visible; ruled by George 2026-10-15, Issue# 32 - this repo). A run IS re-observed (every
    # alert it reported names it again), so KEYLESS would split one run into many nodes. Neither
    # the timestamp nor the commit is in the key: two runs can share a commit, and a timestamp is
    # never identity.
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("source", "run_key")
    ENTITY_NAME: ClassVar[str] = "Scan Run"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "One execution of a scanner: the tool version, the commit and ref it analysed, what it "
        "analysed (category), when, how it ended, and how many results it reported."
    )
    ENTITY_ICON: ClassVar[str] = "scan-run"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "scan-run"}

    OUTBOUND_EDGES: ClassVar[list[dict[str, Any]]] = [
        {
            "nodes": [{"type": "compliance_core__compliance_finding"}],
            "edges": [{"type": "REPORTS_COMPLIANCE_FINDING__compliance_core"}],
        },
        {"edges": [{"type": "RUNS_AT_LOCATION__compliance_core"}]},
        {"edges": [{"type": "SCANNED_COMPLIANCE_TARGET__compliance_core"}]},
    ]
    INBOUND_EDGES: ClassVar[list[dict[str, Any]]] = [
        {
            "nodes": [{"type": "compliance_core__compliance_scanner"}],
            "edges": [{"type": "PERFORMS_COMPLIANCE_SCAN_RUN__compliance_core"}],
        },
    ]

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = {
        "source": {"type": "string", "maxLength": 64},
        "run_key": {"type": "string", "minLength": 1, "maxLength": 512},
        "tool_version": {"type": ["string", "null"]},
        "commit_sha": {"type": ["string", "null"]},
        "ref": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
        "observed_at": {"type": ["string", "null"], "format": "date-time"},
        "outcome": {"type": ["string", "null"]},
        "results_count": {"type": ["integer", "null"], "minimum": 0},
        "data_version": {"type": ["string", "null"], "maxLength": 128},
        "data_built_at": {"type": ["string", "null"], "format": "date-time"},
    }

    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        name: {"validation": "jsonschema", "schema": schema} for name, schema in FIELD_CRUD_SCHEMA.items()
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["run_key"]

    #: The producer that asserted this run: the plugin slug of whoever minted it
    #: ("github_core"). Half of the natural key: it namespaces `run_key`.
    source = models.CharField(max_length=64, blank=True, default="")
    run_key = models.CharField(
        max_length=512,
        blank=True,
        default="",
        db_index=True,
        help_text="The producer's key for this execution, opaque here. Half of the identity.",
    )
    # TAP-KNOWN-DUPE(scan-run-analysis-fields): tool_version, commit_sha, ref, category,
    # observed_at (github_core's created_at) and results_count repeat fields of
    # github_core__code_scanning_analysis, the GitHub detail twin of this neutral run. A neutral
    # type cannot import or read a vendor plugin's model (compliance_core depends on nothing above
    # core), so the facts are held on both sides; the parity test pins the names. Partner:
    # github_core/models/code_scanning_analysis.py (that repo adds its own tag).
    tool_version = models.CharField(  # noqa: DJ001  (req-compliance-core-scan-run-2)
        max_length=64,
        null=True,
        blank=True,
        default=None,
        help_text="The version of the tool that ran. Lives here, never on the scanner.",
    )
    commit_sha = models.CharField(  # noqa: DJ001  (req-compliance-core-scan-run-2)
        max_length=64,
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="The commit analysed.",
    )
    ref = models.CharField(  # noqa: DJ001  (req-compliance-core-scan-run-2)
        max_length=512,
        null=True,
        blank=True,
        default=None,
        help_text="The full ref analysed, as the producer reports it (refs/heads/main).",
    )
    category = models.CharField(  # noqa: DJ001  (req-compliance-core-scan-run-2)
        max_length=255,
        null=True,
        blank=True,
        default=None,
        help_text="What was scanned (an image, a path, a language), as the producer labels it.",
    )
    observed_at = models.DateTimeField(
        null=True, blank=True, default=None, help_text="When the producer observed the run (github_core: created_at)."
    )
    outcome = models.CharField(  # noqa: DJ001  (req-compliance-core-scan-run-2)
        max_length=64,
        null=True,
        blank=True,
        default=None,
        help_text="How the run ended, as the producer says it. Null where not observed.",
    )
    results_count = models.IntegerField(
        null=True,
        blank=True,
        default=None,
        help_text="Results the run reported. 0 = reported nothing; null = unobserved.",
    )
    data_version = models.CharField(  # noqa: DJ001  (req-compliance-core-scan-run-2)
        max_length=128,
        null=True,
        blank=True,
        default=None,
        help_text="The version or build identifier of the vulnerability database the scanner matched against, "
        "as the scanner reports it. Null = unobserved.",
    )
    data_built_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="When that database says it was built, so a run against a stale database is visible.",
    )

    class Meta(BaseModel.Meta):
        db_table = "compliance_core__compliance_scan_run"

    def get_name(self) -> str:
        return self.run_key

    def __str__(self) -> str:
        return self.get_name()
