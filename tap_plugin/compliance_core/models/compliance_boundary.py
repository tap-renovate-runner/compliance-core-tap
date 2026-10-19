"""Compliance boundary — an authorization boundary (regime-agnostic)."""

from typing import Any, ClassVar

from django.db import models

from tap_grid.models import BaseModel


class ComplianceBoundary(BaseModel):
    """An authorization boundary — the perimeter of a single authorization.

    A boundary names the set of system components in scope for a single
    compliance authorization (a FedRAMP ATO, a SOC2 audit scope, an ISO
    certification scope, …). Components are linked to their boundary by the
    ``SCOPED_TO_COMPLIANCE_BOUNDARY`` edge (component → boundary). "Identify
    everything inside the boundary" is then a fan-in query over that edge.

    Regime-agnostic substrate: the scoping concept is shared across regimes;
    the regime is layered per-instance, not baked into the model.

    The initial pass carries only name and description; structured metadata
    (impact level, authorization dates, authorizing official) becomes typed
    fields when a consumer needs them rather than a speculative JSON blob now.

    Identity (`req-compliance-core-identity`): found again by the producer that declared it
    and that producer's own key — `("source", "source_key")`. A producer that writes neither
    gets a fresh node every run rather than an error, so writing them is the data contract a
    minting plugin owes this one.

    Spec: plugins/compliance_core/specs/spec-compliance-core-v0.md
    """

    ENTITY_TYPE: ClassVar[str] = "compliance_core__compliance_boundary"
    # WHO declared it, and WHAT THEY CALL IT — the same shape as the other producer-minted
    # types, and for the same reason. A boundary is the perimeter of ONE authorization, and the
    # authorization is an external object (an ATO package, an audit scope) held in someone
    # else's system; that system's reference for it is the stable handle. `name` was considered
    # and refused: a boundary is renamed as programs are renamed, and a key over `name` would
    # fork one boundary into two the first time that happened (Issue# 8 -
    # tap-plugin-compliance-core). KEYLESS was refused for the same reason as the others — an
    # authorization package re-read is a re-observation, not a new boundary.
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("source", "source_key")
    ENTITY_NAME: ClassVar[str] = "Authorization Boundary"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "An authorization boundary — the perimeter of system components in "
        "scope for a single compliance authorization. Components link to it "
        "via the SCOPED_TO_COMPLIANCE_BOUNDARY edge."
    )
    # No type icon: the box itself is how the boundary reads on the graph, and an icon badge added visual noise.
    ENTITY_ICON: ClassVar[str] = ""
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "boundary"}
    # The FedRAMP standard authorization-boundary drawing (`req-compliance-core-boundary-display`): a
    # TRANSPARENT box, a bold true-red line, and the title OUTSIDE the box at its top left. Every deployment gets
    # this look from the type, so no instance restyles the boundary in layout code. `fill` is white only so the
    # renderer applies the border colour (it is opaque nowhere: `fill_opacity` is 0); the title is the node's name.
    # `fill_opacity`, `border_width` and an outside, left-anchored `label` are tap_viz display hints
    # (`req-viz-system-display-hints-9`, `-10`); a core without them draws the box with the white fill and the
    # red line and centres the title, which is why they are hints and not a rule here.
    DEFAULT_DISPLAY: ClassVar[dict[str, Any]] = {
        "tap_viz": {
            "shape": "round-rectangle",
            "colors": {"fill": "#FFFFFF", "border": "#FF0000", "label": "#FF0000"},
            "fill_opacity": 0,
            "border_width": 4,
            "label": {"valign": "top", "halign": "left", "position": "outside"},
        }
    }

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = {
        "source": {"type": "string", "maxLength": 64},
        "source_key": {"type": "string", "maxLength": 512},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
    }

    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        "source": {"validation": "jsonschema", "schema": {"type": "string", "maxLength": 64}},
        "source_key": {"validation": "jsonschema", "schema": {"type": "string", "maxLength": 512}},
        "name": {"validation": "jsonschema", "schema": {"type": "string", "minLength": 1}},
        "description": {"validation": "jsonschema", "schema": {"type": "string"}},
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["name"]

    #: The producer that asserted this boundary — the slug of the plugin that minted it,
    #: never a display name. Half of the natural key: it namespaces `source_key`, so
    #: two producers can never collide.
    source = models.CharField(max_length=64, blank=True, default="")
    #: What the producing system calls this boundary, verbatim ("fedramp/acme-saas-ato").
    #: Opaque here: only the producer's namespace gives it meaning, and compliance_core
    #: never parses it.
    source_key = models.CharField(max_length=512, blank=True, default="")
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "compliance_core__compliance_boundary"

    def get_name(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.get_name()
