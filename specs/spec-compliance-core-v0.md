# Compliance Core Plugin Specification

> **Status: Phase A + B implemented (2026-07-08).** All six models
> (`compliance_artifact`, `compliance_context`, `compliance_evidence`,
> `compliance_finding`, `compliance_exception`, `compliance_boundary`) and all five edges
> (`CITES_COMPLIANCE_EVIDENCE`, `COVERS_COMPLIANCE_FINDING`, `CARRIES_COMPLIANCE_FINDING`,
> `SCOPED_TO_COMPLIANCE_BOUNDARY`, `CONCERNS_COMPLIANCE_CONTROL`) now live in compliance_core,
> with the regime-neutral type-marker dimension fix on the moved evidence/finding/exception
> nodes. fedramp/samsite retarget onto them. The former fedramp bridge edge
> `RELATED_INDICATOR` (finding → ksi_indicator) was **generalized** into
> `CONCERNS_COMPLIANCE_CONTROL` (finding → wildcard control target) so a finding can concern
> controls across regimes; fedramp's panels supply the `ksi_indicator` target. Migrations `0001`/`0002`
> (compliance_core) + `0004`/`0005` (fedramp deletes) apply clean; all targeted suites +
> mypy ratchet green.
>
> **Assigned identity adopted 2026-09-20** (`req-compliance-core-identity`, Issue# 8 -
> tap-plugin-compliance-core): every model declares `NATURAL_KEY`, the five
> producer-minted types gain neutral `source` / `source_key` columns and key on them,
> `compliance_context` keys on `regime`, and the core floor rises to `>= 0.2.0`.
> Migration `0004` adds the fields and the generated composite search indexes.
>
> **Vulnerability, scanner and scan run added 2026-10-15** (Issue# 32 - this repo, design ruled by
> George): `compliance_vulnerability`, `compliance_scanner`, `compliance_scan_run` and the edges
> `CONCERNS_COMPLIANCE_VULNERABILITY`, `PERFORMS_COMPLIANCE_SCAN_RUN`,
> `REPORTS_COMPLIANCE_FINDING`, `DETECTS_COMPLIANCE_FINDING`, `RUNS_AT_LOCATION`. Vocabulary only;
> no collector emits them. Migration `0005`.
>
> **Exceptions as code proposed 2026-10-19** (design ruled by George in conversation; every requirement
> below marked `Proposed`): `compliance_exception` gains the fields a decision needs, a new node
> `compliance_exception_instance` holds each exception's per-scope, per-check application, and
> `COVERS_COMPLIANCE_FINDING` moves from the exception to the instance
> (`req-compliance-core-exception` .. `-exception-checker`).

## Plugin Identity

- **Slug:** `compliance_core`
- **Kind:** substrate library plugin — regime-agnostic compliance vocabulary. **No
  collector in v0.**
- **Public surface:**
  - **Models** (see `req-compliance-core-models`): `compliance_artifact`,
    `compliance_context`, `compliance_evidence`, `compliance_finding`,
    `compliance_exception`, `compliance_boundary`; and, added 2026-10-15,
    `compliance_vulnerability`, `compliance_scanner`, `compliance_scan_run`
    (see `req-compliance-core-vulnerability`, `-scanner`, `-scan-run`); proposed 2026-10-19,
    `compliance_exception_instance` (see `req-compliance-core-exception-instance`).
  - **Edge types** (see `req-compliance-core-edges`): `CITES_COMPLIANCE_EVIDENCE`,
    `COVERS_COMPLIANCE_FINDING`, `CARRIES_COMPLIANCE_FINDING`,
    `SCOPED_TO_COMPLIANCE_BOUNDARY`, `CONCERNS_COMPLIANCE_CONTROL`; and, added 2026-10-15,
    `CONCERNS_COMPLIANCE_VULNERABILITY`, `PERFORMS_COMPLIANCE_SCAN_RUN`,
    `REPORTS_COMPLIANCE_FINDING`, `DETECTS_COMPLIANCE_FINDING`, `RUNS_AT_LOCATION`, and, added
    2026-10-15 (Issue# 38 - this repo), `SCANNED_COMPLIANCE_TARGET`
    (see `req-compliance-core-scan-edges`); proposed 2026-10-19, `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE`,
    `EXEMPTS_COMPLIANCE_VULNERABILITY`, `SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET`
    (see `req-compliance-core-exception-edges`).
  - **Default dimensions** (see `req-compliance-core-regime-neutral`): a neutral
    per-type marker under the `compliance` key (e.g. `compliance: finding`); the
    **regime** dimension (`fedramp-20x`, `soc2`, …) is layered per-instance by the
    consumer, never baked into the model.

## Philosophy

Compliance vocabulary is regime-agnostic substrate, not FedRAMP payload. Evidence,
findings, exceptions, fetched artifacts, authorization boundaries, and per-regime
posture exist in **every** compliance program — FedRAMP 20x, SOC2, CMMC, ISO 27001.
They live in `fedramp_20x_ksi` today only because it was the first regime plugin, and
the coupling shows: samsite's compliance collector creates `compliance_artifact`s and
~15 grift/panel queries read them, while fedramp barely touches them and roscale (the
OSCAL renderer) references them zero times. "OSCAL shouldn't carry over to FedRAMP."
The fix is the substrate-core extraction doctrine: hoist the generic layer into a
neutral plugin that every regime/renderer/integration depends on **downward**.

Three principles shape the design:

**Regime lives on the instance, not the model.** A generic node must not hardcode a
regime. Today `evidence`/`finding`/`exception` default to `{"compliance":
"fedramp-20x"}` — a regime baked into a model that is supposed to be regime-agnostic.
In compliance_core the model default is a neutral **type marker** (`compliance:
evidence`); a regime dimension, when needed, is applied per-instance by the collector
that mints the node (a future FedRAMP collector would stamp `fedramp-20x`; a SOC2 one
`soc2`). v0 ships no such collector, so today only the neutral marker is set — see
`req-compliance-core-regime-neutral`. The `compliance_context` node is where a Grid's
regime posture is recorded, and it is already regime-generic (its `regime` field
discriminates FedRAMP/SOC2/CMMC/ISO).

**The `compliance_` name prefix disambiguates domain.** Node names carry a
`compliance_` qualifier (`compliance_evidence`, not bare `evidence`) so the vocabulary
is unambiguous system-wide — distinct from a future `crime_scene_evidence` or another
kind of `exception`. Ownership (the `compliance_core` plugin slug) and semantic domain
(the `compliance_` name qualifier) are **distinct axes**; the resulting
`compliance_core__compliance_evidence` entity_type is deliberately explicit. Edge
verbs name their object with the same qualifier (`CITES_COMPLIANCE_EVIDENCE`) so a slug
reads unambiguously and tracks the node type it targets.

**Substrate, depended on downward.** `compliance_core` depends on nothing above core.
`fedramp_20x_ksi` (regime vocabulary), `roscale` (OSCAL renderer), and `samsite`
(deployment integration) depend downward on it. Framework owns the regime-specific
vocabulary; the substrate owns the generic primitives; deployment owns the wiring.

## Roadmap Alignment

Realizes the **substrate-core plugin extraction** doctrine; sibling of the
`identity_core` extraction. Advances cross-plugin decoupling and removes a latent bug
(regime hardcoded into generic model defaults). Pre-eviction work — the `entity_type`
renames are namespace churn that must land before plugins freeze at released tags
(`req-compliance-core-migration`).

**Forward note (captured, not built).** `fedramp_20x_ksi` currently hosts two tenants:
strictly-KSI vocabulary (`ksi_*`) and broader FedRAMP-20x vocabulary (`vdr_finding`,
`vdr_report`). A coming **fedramp_20x** plugin will take the non-`ksi_`-prefixed
vocabulary; the `ksi_` prefix is the mechanical discriminator. `vdr_*` and `ksi_*`
both stay in `fedramp_20x_ksi` for now — compliance_core takes only the regime-agnostic
layer.

## Prior Art

- **OSCAL** (NIST): assessment findings, evidence/observations, system components, the
  authorization boundary / system-security-plan scope — the generic shapes this
  vocabulary mirrors.
- **NIST SP 800-53A / POA&M**: findings + risk acceptances (exceptions) as first-class
  assessment artifacts.
- **The cross-regime pattern**: SOC2, CMMC, ISO 27001 all carry evidence, findings,
  exceptions, and a scoping boundary — the reason the layer is regime-agnostic.
- **How exceptions are implemented elsewhere** (read 2026-10-19 from the tools' own documentation and
  source; the pages were summarised by a fetch tool, so check a citation before relying on it):
  - *DefectDojo* `Risk_Acceptance`: a container with a many-to-many to findings, an owner, `accepted_by`,
    `expiration_date` and flags for what to do on expiry. It writes `active=False` and
    `risk_accepted=True` onto each finding and reverses that in four code paths (expire, reinstate,
    delete, remove); expiry marks the acceptance handled and never deletes it. Borrowed: the
    container-and-members shape and expiry that is recorded, not silent. Rejected: mutating the
    finding's own state, which is why coverage here is computed (`req-compliance-core-exception-coverage`).
  - *Trivy* `.trivyignore.yaml` and *Grype* ignore rules: a rule of vulnerability id plus optional
    paths, package URLs, name, version and location, all of which must match; a free-text statement or
    reason; Trivy adds an optional `expired_at` and, per its documentation, an entry without one is
    valid forever. Both can print the suppressed findings with the rule that suppressed them. Borrowed:
    scope as an AND of anchors, and the record of what was suppressed and why. Rejected: no expiry by
    default.
  - *Kyverno* `PolicyException`: a separate resource naming a policy and rules, with a selector and
    conditions, evaluated on every admission and background scan; each match lands in the policy report
    as a `skip` naming the exception. No expiry field is described. Borrowed: the exception is a rule
    re-evaluated on every pass, and each evaluation is a recorded result. That recorded result is
    `compliance_exception_instance`.
  - *OpenVEX* and *CycloneDX VEX*: one statement per vulnerability and product (identified by package URL
    or hash) with a status and, for `not_affected`, one of five justification labels; later statements
    supersede earlier ones by timestamp. No expiry. Borrowed: the justification labels.
  - *GitHub code scanning*: a dismissal is state on the alert itself (`dismissed_reason` of
    `false positive`, `won't fix`, `used in tests` or `mitigated`, `dismissed_by`, `dismissed_at` and a
    comment capped at 280 characters). Borrowed: the reason vocabulary. Rejected: state on the finding,
    which leaves no history and no scope beyond that one alert.
  - *FedRAMP / OSCAL POA&M*: deviations (false positive, operational requirement, risk adjustment) are
    carried as part of the risk, each with a justification and an approval status. The OSCAL element
    detail was not read. Borrowed: the three deviation ideas, folded into `kind` below without the
    approval workflow.

## Goals

|   |   |   |
| :---: | --- | --- |
| 1. | Compliance Substrate | A neutral home for regime-agnostic compliance vocabulary; six v0 node types. |
| 2. | Library Plugin | No collector in v0. Models + edge types; consumers mint instances via their own collectors. |
| 3. | Regime On The Instance | Generic models carry a neutral type-marker dimension; the regime is layered per-instance, never baked into the model. |
| 4. | Disambiguating Names | `compliance_`-prefixed node names; edge verbs name their object with the same qualifier. |
| 5. | Downward-Only Deps | fedramp_20x_ksi / roscale / samsite depend on compliance_core; it depends on nothing above core. |
| 6. | Faithful Carry-Forward | Fields move unchanged; the only behavior change to samsite is the type/edge rename (and the regime-dimension fix). |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-compliance-core-scope | [Plugin Scope](#plugin-scope) | Implemented | Substrate library; six models + five edges; no collector. |
| req-compliance-core-models | [Model Set](#model-set) | Implemented | `compliance_artifact`, `compliance_context`, `compliance_evidence`, `compliance_finding`, `compliance_exception`, `compliance_boundary`. |
| req-compliance-core-boundary-display | [Boundary Display](#boundary-display) | Implemented | `compliance_boundary` defaults to the FedRAMP authorization-boundary look: transparent box, bold red line, title outside at the top left. |
| req-compliance-core-edges | [Edge Vocabulary](#edge-vocabulary) | Implemented | `CITES_COMPLIANCE_EVIDENCE`, `COVERS_COMPLIANCE_FINDING`, `CARRIES_COMPLIANCE_FINDING`, `SCOPED_TO_COMPLIANCE_BOUNDARY`, `CONCERNS_COMPLIANCE_CONTROL` (wildcard target). |
| req-compliance-core-identity | [Assigned Identity](#assigned-identity) | Implemented | Every model declares `NATURAL_KEY`; the five producer-minted types key on `("source", "source_key")`, `compliance_context` on `("regime",)`. Floor `requires_tap >= 0.2.0`. |
| req-compliance-core-regime-neutral | [Regime On The Instance](#regime-on-the-instance) | Implemented | Model default is a neutral type marker; regime layered per-instance. Fixes the hardcoded `fedramp-20x` default. |
| req-compliance-core-vulnerability | [Vulnerability Modeling](#vulnerability-modeling) | Implemented | `compliance_vulnerability`: a public record (CVE, else GHSA) named once however many tools report it; CVSS, CWE, SSVC and KEV facts live here, not on every finding. |
| req-compliance-core-scanner | [Scanner Modeling](#scanner-modeling) | Implemented | `compliance_scanner`: an installed instance of a detection tool at one place, never a version. |
| req-compliance-core-scan-run | [Scan Run Modeling](#scan-run-modeling) | Implemented | `compliance_scan_run`: one execution of a scanner; carries the tool version, commit, ref, category, time, outcome, result count and the database build it matched against. |
| req-compliance-core-scan-edges | [Scan Edges](#scan-edges) | Implemented | `CONCERNS_COMPLIANCE_VULNERABILITY`, `PERFORMS_COMPLIANCE_SCAN_RUN`, `REPORTS_COMPLIANCE_FINDING`, `DETECTS_COMPLIANCE_FINDING`, `RUNS_AT_LOCATION`, `SCANNED_COMPLIANCE_TARGET`. |
| req-compliance-core-searches | [Vulnerability Cross-Tab Searches](#vulnerability-cross-tab-searches) | Implemented | Two `module` Search runners, `vulnerability-components` and `component-severity`, return table rows by ORM aggregation under the read rules Gryphon applies. |
| req-compliance-core-reach | [Findings Reached Searches](#findings-reached-searches) | Implemented | Two generic `module` Search runners, `findings-reached-count` and `findings-reached-list`, count and list the distinct open findings a root reaches along edge-type chains given as input, which Gryphon cannot sum across paths. |
| req-compliance-core-finding-detection | [Finding Detection Time](#finding-detection-time) | Implemented | `compliance_finding.first_detected_at`: when the producer first detected the finding; null until a source says; not identity. |
| req-compliance-core-exception | [Exception Modeling](#exception-modeling) | Proposed | `compliance_exception` gains `kind`, `justification`, `approver`, `granted_at`, `review_by`, `expires_at` and `verify_within_hours`, and declares its instances as contained. |
| req-compliance-core-exception-instance | [Exception Instance Modeling](#exception-instance-modeling) | Proposed | `compliance_exception_instance`: one exception's application to one vulnerability within one declared scope; carries the last check's `outcome` and `verified_at`. |
| req-compliance-core-exception-edges | [Exception Edges](#exception-edges) | Proposed | `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE` (containment), `EXEMPTS_COMPLIANCE_VULNERABILITY`, `SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET`; `COVERS_COMPLIANCE_FINDING` moves to the instance; `CITES_COMPLIANCE_EVIDENCE` accepts an instance. |
| req-compliance-core-exception-coverage | [Exception Coverage](#exception-coverage) | Proposed | Coverage is computed, never stored: two `module` Search runners, `finding-exception-coverage` and `exceptions-due-review`. Unset or stale means not covered. |
| req-compliance-core-exception-lifecycle | [Exception Lifecycle](#exception-lifecycle) | Proposed | Withdrawal cascades through containment; falsification updates the instance and keeps it; a re-minted finding is a new entity the checker must re-bind. |
| req-compliance-core-exception-checker | [Exception Checker Contract](#exception-checker-contract) | Proposed | What a plugin that checks an exception on a schedule owes the grid; compliance_core ships no checker. |
| req-compliance-core-naming | [Naming Discipline](#naming-discipline) | Implemented | `compliance_` node-name prefix; edge object noun tracks the node type. |
| req-compliance-core-deps | [Dependency Direction](#dependency-direction) | Implemented | Downward-only; declared in consumers' `pyproject.toml` + `depends_on`. |
| req-compliance-core-consumer-retargets | [Consumer Retargets](#consumer-retargets) | Implemented | fedramp/samsite retarget type strings + edges; the fedramp bridge edge `RELATED_INDICATOR` was generalized into `CONCERNS_COMPLIANCE_CONTROL` (compliance_core, wildcard target). |
| req-compliance-core-migration | [Extraction & Migration](#extraction--migration) | Implemented | Rename `fedramp_20x_ksi__*` → `compliance_core__compliance_*`; ids regenerate (collected, not seeded); phased first slice; pre-eviction. |
| req-compliance-core-nongoals | [v0 Non-Goals](#v0-non-goals) | Implemented | `ksi_*` and `vdr_*` stay in fedramp; no collector; no regime logic; generic `component` deferred. |

### Plugin Scope
----
RID: `req-compliance-core-scope`

Status: `Implemented`

`compliance_core` is a **library / substrate** plugin. Its v0 surface is six models and
four edge types plus their dimension defaults. It registers node/edge types and
dimensions at load; it ships **no collector** (`apps.py` is `pass`; no `tap_cares`
registration) and seeds no GRIFT. Consumers import only from `compliance_core.*` and
mint instances through their own collectors. It is the generic layer beneath every
compliance regime plugin.

### Model Set
----
RID: `req-compliance-core-models`

Status: `Implemented`

Six node types (three more, added 2026-10-15, have their own sections: [Vulnerability](#vulnerability-modeling), [Scanner](#scanner-modeling), [Scan Run](#scan-run-modeling)), `entity_type = compliance_core__<name>`, fields carried forward
faithfully from the `fedramp_20x_ksi` originals:

| entity_type | from | key fields |
| --- | --- | --- |
| `compliance_core__compliance_artifact` | `fedramp_20x_ksi__compliance_artifact` | `kind` (oscal_ssp/oscal_poam/iiw), `source_url`, `content` (blob), signature-verification metadata, `source` + `source_key` (identity) |
| `compliance_core__compliance_context` | `fedramp_20x_ksi__compliance_context` | `regime` (discriminator **and identity**), `fedramp_class` (+ future per-regime posture fields) |
| `compliance_core__compliance_evidence` | `fedramp_20x_ksi__evidence` | `name`, `description`, `kind`, `source` + `source_key` (identity) |
| `compliance_core__compliance_finding` | `fedramp_20x_ksi__finding` | `name`, `summary`, `description`, `status`, `first_detected_at` (added 2026-10-19, see `req-compliance-core-finding-detection`), `source` + `source_key` (identity) |
| `compliance_core__compliance_exception` | `fedramp_20x_ksi__exception` | `name`, `description`, `status`, `source` + `source_key` (identity); proposed 2026-10-19: `kind`, `justification`, `approver`, `granted_at`, `review_by`, `expires_at`, `verify_within_hours` (`req-compliance-core-exception`) |
| `compliance_core__compliance_boundary` | `fedramp_20x_ksi__boundary` | `name`, `description`, `source` + `source_key` (identity) |

`compliance_artifact` and `compliance_context` keep their names (already
`compliance_`-prefixed). `boundary` moves here because every compliance regime scopes
to some authorization/system boundary — it is not FedRAMP-specific. Display, icons,
CRUD/validation schemas, and `CREATE_REQUIRED` carry forward from the originals
unchanged except the `entity_type`/`db_table` rename and the dimension fix
(`req-compliance-core-regime-neutral`). The `source` / `source_key` pair added on
2026-09-20 is the one departure from faithful carry-forward: the producer-minted types
had no field that identified anything, so their identity had nowhere to live
(`req-compliance-core-identity`).

### Assigned Identity
----
RID: `req-compliance-core-identity`

Status: `Implemented`

Core assigns entity ids (UUIDv7 at first sight) and finds a row again by the **search
generated from the owning model's `NATURAL_KEY`** (`req-grid-entity-natural-key`). A
producer names a node by a batch-local `ref` and the GRIFT importer resolves it against
that declaration — **the declaration lives on the model, so it is compliance_core's to
make no matter which plugin writes the node.** A type that has not declared is refused
outright: *undeclared is never keyless*. That refusal is why `github_core` held
`compliance_core__compliance_finding` back from the adoption while every other type it
mints moved (`tap-plugin-github-core#162`/`#163`, Issue# 8 - tap-plugin-compliance-core).

**The dependency inverts rather than disappearing.** Under derived ids the producer
decided the key, because somebody had to compute an identifier and only the producer held
the values. Under assigned identity **compliance_core decides the key** and the producer
owes the **values** the declaration names. The ref string itself does not participate:
the importer passes `resolve_identity` the entity type and the node payload, and the ref
is a batch-local label used to wire endpoints inside the document.

| declaration | types | why |
| --- | --- | --- |
| `("source", "source_key")` | `compliance_finding`, `compliance_evidence`, `compliance_exception`, `compliance_artifact`, `compliance_boundary` | Minted by other plugins. Nothing these models already carry identifies anything: `name`/`summary`/`description` describe, and `status` is the thing that changes. `source` is the producer's slug — who is speaking — and `source_key` is what that system calls the object, verbatim and opaque here. A producer's slug namespaces its own keys, so two producers can never collide and neither has to know the other's keying rules; provenance becomes queryable as a side effect. |
| `("regime",)` | `compliance_context` | Keys on a field it already carries. A context is not somebody else's object observed from outside — it is **this Grid's** posture under one regime, and the model's stated cardinality is one context per regime per Grid. The declaration makes that invariant the search. `fedramp_class` stays out of the key: it is the value most likely to be corrected. |

**`KEYLESS` was refused for all six**, deliberately. A keyless ref mints a **new node
every run**, so a re-scan would duplicate every finding rather than re-observe it — worse
than the status quo it replaces. Every one of these types is genuinely re-observed: a
scanner re-runs, an artifact is re-fetched, an exception register is re-imported, a
posture is re-asserted.

**The failure mode this shape is designed against, stated rather than discovered.** A
producer that supplies **none** of the constituting fields gets absent values; the
generated search answers "not found" without querying (a hole is never a match) and a
fresh node is assigned. That is **duplicates, not a hard error** — so the constituting
fields are ones every producer can and will write, which is the argument for neutral
`source` / `source_key` over anything borrowed from one producer's world. Neither field
is in `CREATE_REQUIRED`: a node authored by hand inside TAP carries neither, is created
once by an explicit write, and is never re-observed.

**One-way door.** A natural key cannot be changed once nodes have been assigned ids under
it. It is safe to land here because nothing resolves against it until a producer emits a
ref, and that takes this release plus a pin bump in the consumer.

**Sequencing across repositories.** compliance_core declares → **releases** → `github_core`
bumps its pin and flips `code_scanning_finding_id` from a derived uuid5 to a ref, writing
`source="github_core"` and `source_key="{full_name}#code_scanning#{number}"`. A ref cannot
resolve against a declaration that is not in the pinned version.

| ACID | Title | Status | Description |
| --- | --- | :---: | --- |
| req-compliance-core-identity-1 | Every model declares | Implemented | All six models declare `NATURAL_KEY`; a guard test fails on an undeclared registered type. |
| req-compliance-core-identity-2 | Producer-neutral key | Implemented | `("source", "source_key")` on the five producer-minted types; `source` is the minting plugin's slug, `source_key` is opaque to compliance_core. |
| req-compliance-core-identity-3 | Context keys on its own field | Implemented | `compliance_context` declares `("regime",)`, expressing one-context-per-regime-per-Grid. |
| req-compliance-core-identity-4 | Re-observation is one node | Implemented | Two writes of the same source object under one producer resolve to one entity id (proved through `grift_import`, not asserted from reading). |
| req-compliance-core-identity-5 | Core floor | Implemented | `requires_tap >= 0.2.0` — the release carrying the declaration contract, the generated search and `resolve_identity`. |

### Boundary Display
----
RID: `req-compliance-core-boundary-display`

Status: `Implemented`

An authorization boundary is drawn the way a FedRAMP authorization-boundary diagram draws it: an
empty box with a bold red line around what is in scope, titled outside the box at its top left.
`ComplianceBoundary.DEFAULT_DISPLAY["tap_viz"]` carries that look, so every deployment that shows
a boundary gets it from the type and none restyles it in layout code. The title is the node's
`name`; naming it "Authorization Boundary" (or anything else) is the producing instance's data.

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-boundary-display-1 | Transparent box | Implemented | `fill_opacity` is `0`, so the box is only its line and what is inside it shows through. | `colors.fill` is white only so the renderer applies the border colour; nothing is filled. |
| req-compliance-core-boundary-display-2 | Bold true-red line | Implemented | `colors.border` is `#FF0000` and `border_width` is `4` (px); the label colour is the same red. | Not a pink tint: the previous default was `#D93535` on a `#FBE4E4` fill. |
| req-compliance-core-boundary-display-3 | Title outside at the top left | Implemented | `label` is `{valign: "top", halign: "left", position: "outside"}`. | Needs tap_viz display hints `fill_opacity`, `border_width` and an anchored outside label (`req-viz-system-display-hints-9`, `-10`); an older core ignores them and draws a white box with a red line and a centred title. |

### Edge Vocabulary
----
RID: `req-compliance-core-edges`

Status: `Implemented`

Five edges, renamed so the object noun tracks the (now `compliance_`-prefixed) node
type. Four move directly with their generic endpoints; the fifth
(`CONCERNS_COMPLIANCE_CONTROL`) is the generalized bridge (see Consumer Retargets):

| edge (compliance_core) | from | endpoints |
| --- | --- | --- |
| `CITES_COMPLIANCE_EVIDENCE` | `HAS_EVIDENCE` | `compliance_finding` → `compliance_evidence` |
| `COVERS_COMPLIANCE_FINDING` | `COVERS_FINDING` | `compliance_exception` → `compliance_finding`; proposed 2026-10-19: `compliance_exception_instance` → `compliance_finding` instead (`req-compliance-core-exception-edges`) |
| `CARRIES_COMPLIANCE_FINDING` | `HAS_FINDING` | any asset (wildcard source) → `compliance_finding` |
| `SCOPED_TO_COMPLIANCE_BOUNDARY` | `SCOPED_TO_BOUNDARY` | any component (wildcard source) → `compliance_boundary` |
| `CONCERNS_COMPLIANCE_CONTROL` | `RELATED_INDICATOR` | `compliance_finding` → any control (wildcard target) |

**Renamed 2026-09-10 (Issue# 5 - tap-plugin-compliance-core).** `HAS_COMPLIANCE_EVIDENCE` →
`CITES_COMPLIANCE_EVIDENCE` and `HAS_COMPLIANCE_FINDING` → `CARRIES_COMPLIANCE_FINDING`: both
failed core's edge-naming conformance check (`req-tap-plugin-edge-naming`, rule `modal-prefix` —
a `HAS_` prefix names a state, not the mechanical action). A finding *cites* the evidence that
supports its verdict; an asset *carries* a finding observed against it. Endpoints, property
schemas and default dimensions are unchanged. Migration `0003_retire_renamed_edge_types` deletes
rows of the two retired types on an upgraded grid (their ids derive from the slug, so the next
collection re-emits them under the new names; nodes are untouched). Consumers that read the old
slugs (fedramp_20x_ksi panels and grift) retarget in their own repos.

Wildcard **sources** on `CARRIES_COMPLIANCE_FINDING` and `SCOPED_TO_COMPLIANCE_BOUNDARY` are
deliberate: any asset can carry a finding, any component can be in scope for a boundary,
across regimes. The wildcard **target** on `CONCERNS_COMPLIANCE_CONTROL` is the mirror
image: a finding can concern a control in any regime's catalog — a FedRAMP `ksi_indicator`
today, a SOC2 criterion tomorrow, or several at once. Keeping the target open lets the
edge live in compliance_core (it names no regime type, so no upward dependency) without a
generic `compliance_control` supertype, which is deferred until a second regime justifies
designing it (`req-compliance-core-nongoals`). Until then the source is the only typed end;
consumers constrain the target in their own queries.

### Regime On The Instance
----
RID: `req-compliance-core-regime-neutral`

Status: `Implemented`

Generic models MUST NOT bake a regime into their default dimensions. The model default
is a neutral per-type marker under the `compliance` key: `compliance: artifact`,
`compliance: context`, `compliance: evidence`, `compliance: finding`, `compliance:
exception`, `compliance: boundary`, and, added 2026-10-15, `compliance: vulnerability`,
`compliance: scanner` and `compliance: scan-run` (a knowing extension of the bare
`compliance` key that Issue# 13 asks to namespace: it follows the existing convention rather
than settling it). The **regime** (`fedramp-20x`, `soc2`, …) is a
distinct dimension applied **per-instance** by whatever collector mints the node (a
future compliance collector would stamp `fedramp-20x` / `soc2` on the instances it
produces). This fixes the current `evidence`/`finding`/`exception` models defaulting to
`{"compliance": "fedramp-20x"}` — a regime hardcoded into a regime-agnostic model.

**v0 reality (honest note):** no collector mints `compliance_finding` / `compliance_evidence`
today (`req-compliance-core-nongoals` — no collector in v0), so no regime dimension is
stamped yet and nothing reads one. The guarantee delivered now is the *negative* one —
the model no longer bakes a regime; the neutral type marker is the only default. Positive
per-instance regime stamping lands with the first minting collector.

| ACID | Title | Status | Description |
| --- | --- | :---: | --- |
| req-compliance-core-regime-neutral-1 | Neutral model default | Implemented | Each model defaults to a type marker, not a regime slug. |
| req-compliance-core-regime-neutral-2 | Regime per-instance | Deferred | Regime is an instance-level dimension, not a model default; the mechanism (per-node dimensions) is in place. No v0 collector mints these nodes, so no regime is stamped yet — lands with the first minting collector. |
| req-compliance-core-regime-neutral-3 | No fedramp default remains | Implemented | No compliance_core model carries `fedramp-20x` (or any regime) as its default. |

### Vulnerability Modeling
----
RID: `req-compliance-core-vulnerability`

Status: `Implemented`

A `compliance_vulnerability` is a publicly identified weakness, named once. Without it one CVE reported by Trivy, Grype and Dependabot is three unrelated findings and nothing says they are the same vulnerability; grouping "by vulnerability" becomes a string match on a scanner's `rule_id`, and the CVSS, CWE, SSVC and KEV facts about the CVE have no node to live on and would be copied onto every finding. A finding points at its vulnerability with `CONCERNS_COMPLIANCE_VULNERABILITY`.

#### Implementation

Identity is `NATURAL_KEY = ("vuln_id",)`: the CVE id where the vulnerability has one, else its GHSA id, every other id in `aliases`. It is deliberately not `("source", "source_key")`: a vulnerability is a public record that several producers each cite, and a per-producer key would put the same CVE back into three nodes. All fields other than `vuln_id` are `null` when unobserved and an empty string or list when a source looked and found nothing (the grid's null convention, `req-grid-node-observation`).

| field | meaning |
| --- | --- |
| `vuln_id` | CVE id, else GHSA id. Identity. Required. |
| `aliases` | Every other id for the same vulnerability, as the record lists them (list of strings). |
| `title`, `description`, `published_at` | The record's own words and publication time. |
| `cvss_score`, `cvss_vector`, `cvss_version`, `cvss_source` | The base score (0.0 to 10.0), the vector it came from, the CVSS version, and who assigned it, named so a reader can weigh it. |
| `cwes` | CWE ids from the record's problem types (list of strings). |
| `ssvc_exploitation`, `ssvc_automatable`, `ssvc_technical_impact`, `ssvc_assessed_at` | CISA's SSVC assessment as published. Free strings: the plugin does not close CISA's vocabulary. |
| `kev`, `kev_added`, `kev_catalog_version` | CISA's Known Exploited Vulnerabilities catalog. `kev` is `false` only when the catalog was read and does not list the id, `null` when it was not read; `kev_catalog_version` names the release the answer came from. |
| `kev_due_date`, `kev_required_action`, `kev_ransomware_use` | The rest of what the catalog publishes about an entry: the remediation due date, the required action, and whether it is known to be used in ransomware campaigns (CISA's own string, not closed here). Null when the catalog was not read or does not list the id. |
| `epss_score`, `epss_percentile`, `epss_date` | FIRST's EPSS: the probability of exploitation in the next 30 days and the percentile, both 0.0 to 1.0, and the date of the model run they came from, so a stale score is visible. A published fact about the vulnerability, not this system's evaluation. |
| `record_url`, `record_updated_at` | Where the record was fetched from and when it says it was last modified. |

The SSVC values and the KEV flag are CISA's published facts about a vulnerability, not this system's evaluation; nothing on this node is derived from a judgement made here. The fix that exists is a fact about a vulnerability **in one component**, so `fixed_versions` rides the `CONCERNS_COMPLIANCE_VULNERABILITY` edge and not this node.

Display name is `vuln_id`. Default dimensions are `{"compliance": "vulnerability"}`. The node accepts edges only from findings and draws none (`OUTBOUND_EDGES = []`).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-vulnerability-1 | Keyed By The Public Id | Implemented | `compliance_vulnerability` declares `NATURAL_KEY = ("vuln_id",)`; re-observing one vulnerability, with a corrected score, is one node, and a CVE reported by three tools is one node with three inbound edges. | `tests/test_vulnerability_scanner_scan_run.py::TestIdentity` |
| req-compliance-core-vulnerability-2 | Null Is Unobserved | Implemented | A field no source wrote is `null`, not a sentinel; `""`, `[]` and `false` are stored as observed-empty. | Authorizes the model's `# noqa: DJ001  (req-compliance-core-vulnerability-2)`. `::TestNodes::test_an_unwritten_field_is_unobserved_and_an_empty_one_is_observed_empty` |
| req-compliance-core-vulnerability-3 | Values Are Checked | Implemented | `cvss_score` is within 0 to 10, `aliases` and `cwes` are lists of strings, `kev` is a boolean and `kev_added` an ISO date; anything else is refused. | `::TestNodes::test_vulnerability_schema_rejects`, `::test_a_fully_observed_vulnerability_round_trips` |
| req-compliance-core-vulnerability-4 | Findings Point In, Nothing Leaves | Implemented | The node accepts `CONCERNS_COMPLIANCE_VULNERABILITY` from a finding and no other edge from it. | `::TestEdges::test_the_wrong_way_round_or_wrong_type_is_refused` |
| req-compliance-core-vulnerability-5 | EPSS Carries Its Date | Implemented | `epss_score` and `epss_percentile` are within 0 to 1 and `epss_date` is an ISO date; all are `null` until a source wrote them, and anything else is refused. | `::TestNodes::test_kev_detail_and_epss_round_trip_with_their_dates`, `::test_vulnerability_schema_rejects` |
| req-compliance-core-vulnerability-6 | KEV Detail As Published | Implemented | `kev_due_date` is an ISO date, `kev_required_action` and `kev_ransomware_use` are strings kept as CISA publishes them; a writer leaves all three `null` for a vulnerability the catalog does not list. The node does not enforce that pairing with `kev`, exactly as it does not for `kev_added`; it is the writer's duty. | `::TestNodes::test_kev_detail_and_epss_round_trip_with_their_dates`, `::test_an_unwritten_field_is_unobserved_and_an_empty_one_is_observed_empty` |

### Scanner Modeling
----
RID: `req-compliance-core-scanner`

Status: `Implemented`

A `compliance_scanner` is an **installed instance, not a product**: Trivy as the `scan` job of one workflow, not Trivy in general. The same tool installed in two workflows is two scanners; a platform installed once is one. (Ruled by George 2026-10-15, Issue# 32 - this repo; it supersedes the first design, in which a scanner was a product keyed by name.)

#### Implementation

| field | meaning |
| --- | --- |
| `source` | The producing plugin's slug (`github_core`). Half of the identity: it namespaces `scanner_key`. Optional, as on `compliance_finding`. |
| `scanner_key` | The producer's slug for this install: the product and where it is installed. Other half of the identity (`NATURAL_KEY = ("source", "scanner_key")`), opaque here, never parsed. Required. |
| `name` | The product (`Trivy`, `CodeQL`, `Grype`). Required. Two installs of one product share it. |
| `configuration` | How the install is configured, as a source supplied it (object). `null` until a source supplies it; no source does yet. |
| `locator` | The text the data gave for where it is installed, verbatim (`unified-systems-com/tap/.github/workflows/publish-images.yml:scan`). `null` when unobserved. |

**Keyed with a producer namespace.** `scanner_key` and `run_key` are opaque, so they are namespaced by `source` exactly as `compliance_finding` is. A false merge of two different scanners (two producers minting the same slug) is silent and unrecoverable; a false split is visible and reconcilable. `compliance_vulnerability` is the exception, because a CVE is a public record several producers cite (ruled by George 2026-10-15).

**Never a version.** A version changes under an unchanged install; it is the fact about what executed, so it lives on the scan run (`tool_version`). A test fails if the scanner gains a field with `version` in its name.

Display name is `name`, with `locator` in brackets when there is one, so two installs of one product are told apart on screen. Default dimensions are `{"compliance": "scanner"}`. When the place of the install is itself a node on the grid, `RUNS_AT_LOCATION` draws the edge and `locator` keeps the words. A scanner may carry a finding about itself (a detection-health finding) with the existing `CARRIES_COMPLIANCE_FINDING`; that use is not built here.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-scanner-1 | Keyed By The Install | Implemented | `compliance_scanner` declares `NATURAL_KEY = ("source", "scanner_key")`; re-observing it is one node, and the same `scanner_key` from two sources is two nodes. | `tests/test_vulnerability_scanner_scan_run.py::TestIdentity::test_two_writes_of_one_source_object_are_one_node` |
| req-compliance-core-scanner-2 | Never A Version | Implemented | No `compliance_scanner` field carries `version` in its name; `tool_version` is on the scan run. | `::TestNodes::test_a_scanner_carries_no_version` |
| req-compliance-core-scanner-3 | Configuration And Locator Are Null Until Supplied | Implemented | A scanner written without `configuration` or `locator` stores `null`. | `::TestNodes::test_a_scanner_configuration_is_null_until_a_source_supplies_it` |
| req-compliance-core-scanner-4 | Installs Are Distinguishable | Implemented | Two installs of one product are two nodes with different display names. | `::TestNodes::test_two_installs_of_one_product_are_two_scanners_with_distinguishable_names` |

### Scan Run Modeling
----
RID: `req-compliance-core-scan-run`

Status: `Implemented`

A `compliance_scan_run` is one execution of a scanner. It sits between the scanner and its findings because an alert is opened by one run, re-confirmed by many and closed when a later run stops reporting it, and because "a scanner failed" is a fact about a run, which is what a detection-health finding attaches to. (Ruled by George 2026-10-15, Issue# 32 - this repo.)

#### Implementation

| field | meaning |
| --- | --- |
| `source` | The producing plugin's slug. Half of the identity: it namespaces `run_key`. Optional, as on `compliance_finding`. |
| `run_key` | The producer's key for this execution. Other half of the identity (`NATURAL_KEY = ("source", "run_key")`), opaque here, never parsed. Required. |
| `tool_version` | The version of the tool that ran. |
| `commit_sha`, `ref` | The commit and full ref analysed. |
| `category` | What was scanned, as the producer labels it (an image, a path, a language). |
| `observed_at` | When the producer observed the run. |
| `outcome` | How the run ended, as the producer says it; `null` where not observed. A run derived from an alert's latest instance cannot say. |
| `results_count` | Results reported. `0` is a run that reported nothing; `null` is unobserved. |
| `data_version`, `data_built_at` | The version or build identifier of the vulnerability database the scanner matched against, as the scanner reports it, and when that database says it was built. A run against a stale database is then visible as one. `null` where not observed. |

All fields but `source` and `run_key` are `null` when unobserved. Display name is `run_key`. Default dimensions are `{"compliance": "scan-run"}`.

**The GitHub detail twin and `TAP-KNOWN-DUPE(scan-run-analysis-fields)`.** `github_core__code_scanning_analysis` (natural key `full_name`, `analysis_id`) is the GitHub detail of the neutral run, the way a detail node hangs off a finding. Six scan-run fields repeat a field of that node: `tool_version`, `commit_sha`, `ref`, `category`, `results_count`, and `observed_at` (`created_at` there). A neutral substrate cannot import or read a vendor plugin's model, so the facts are held on both sides; the duplication is tagged `TAP-KNOWN-DUPE(scan-run-analysis-fields)` at the field block of `ComplianceScanRun` and at the parity test, which fails if either side loses a repeated field. The partner site is `models/code_scanning_analysis.py` in `github_core`, which adds its own tag in its own repository.

Where the runs come from is not decided here: real `code_scanning_analysis` nodes where a collector has put them on the grid, otherwise runs derived from each alert's latest instance (which cannot see a run that reported nothing). Whether a continuous service gets a synthetic run is open; until it is ruled, such a tool uses `DETECTS_COMPLIANCE_FINDING`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-scan-run-1 | Keyed By The Run | Implemented | `compliance_scan_run` declares `NATURAL_KEY = ("source", "run_key")`; re-observing a run with a corrected `results_count` is one node, and the same `run_key` from two sources is two nodes. | `tests/test_vulnerability_scanner_scan_run.py::TestIdentity::test_two_writes_of_one_source_object_are_one_node` |
| req-compliance-core-scan-run-2 | Null Is Unobserved, Zero Is A Result | Implemented | A run written without `outcome` stores `null`; `results_count` `0` is stored as `0`. | Authorizes the model's `# noqa: DJ001  (req-compliance-core-scan-run-2)`. `::TestNodes::test_an_unwritten_field_is_unobserved_and_an_empty_one_is_observed_empty` |
| req-compliance-core-scan-run-3 | Values Are Checked | Implemented | A negative or non-integer `results_count`, or a non-string `commit_sha`, is refused. | `::TestNodes::test_scan_run_schema_rejects` |
| req-compliance-core-scan-run-4 | Known-Dupe Parity | Implemented | Each field the run repeats from `github_core__code_scanning_analysis` exists on both sides. | Skips on a stack without `github_core`. `::TestKnownDupe::test_every_repeated_field_exists_on_both_sides` |
| req-compliance-core-scan-run-5 | Names Its Database | Implemented | `data_version` is a string of at most 128 characters and `data_built_at` an ISO datetime; both are `null` until a producer writes them, and a non-string is refused. | `::TestNodes::test_a_scan_run_names_the_database_it_matched_against`, `::test_scan_run_schema_rejects`, `::test_an_unwritten_field_is_unobserved_and_an_empty_one_is_observed_empty` |

### Scan Edges
----
RID: `req-compliance-core-scan-edges`

Status: `Implemented`

Six edges, each its own mechanical relationship, all references (none is containment: retiring a scanner leaves its runs' findings and the shared vulnerability they cite), each declaring the plain identity (type, source, target) so a re-sent edge is the same edge.

| edge (compliance_core) | endpoints | properties |
| --- | --- | --- |
| `CONCERNS_COMPLIANCE_VULNERABILITY` | `compliance_finding` → `compliance_vulnerability` | `fixed_versions`: list of strings, may be empty. |
| `PERFORMS_COMPLIANCE_SCAN_RUN` | `compliance_scanner` → `compliance_scan_run` | none |
| `REPORTS_COMPLIANCE_FINDING` | `compliance_scan_run` → `compliance_finding` | none |
| `DETECTS_COMPLIANCE_FINDING` | `compliance_scanner` → `compliance_finding` | optional `tool_version`, `category`. |
| `RUNS_AT_LOCATION` | `compliance_scanner` or `compliance_scan_run` → any node (wildcard target) | `locator`: the place as the data gave it. |
| `SCANNED_COMPLIANCE_TARGET` | `compliance_scan_run` → any node (wildcard target) | `outcome`: required string, the producer's own word for how the examination ended; optional `reason`. |

**`CONCERNS_COMPLIANCE_VULNERABILITY`** is named after `CONCERNS_COMPLIANCE_CONTROL`. Its `fixed_versions` is the fix in the component the finding is about, because the same vulnerability is fixed at a different version in each component. `[]` means the source looked and named no fix; an absent property means it was not observed.

**`REPORTS_COMPLIANCE_FINDING`** goes from the run to the finding. By convention a finding is reported by the latest run that saw it and earlier runs are history, not edges.

**Counting findings per scanner takes two paths** (scanner to run to finding, and scanner to finding for a tool with no runs). Gryphon has no UNION, so a page combines two Searches in JS or shows two cards (`req-compliance-core-scan-edges-8`).

**Cardinality is the producer's.** A run has one scanner and a finding has one reporting run, but edge definitions carry no cardinality and identity is `(type, source, target)`, so the plugin cannot refuse a second scanner for one run or a second run for one finding; keeping to one is the producer's job (`req-compliance-core-scan-edges-7`).

**`DETECTS_COMPLIANCE_FINDING`** exists only for a tool that has no runs (Dependabot, a continuous service); a tool with runs reports through `PERFORMS_COMPLIANCE_SCAN_RUN` and `REPORTS_COMPLIANCE_FINDING`, so the two paths never both describe one finding. The plugin cannot see whether a tool has runs, so this is a producer's rule and is not enforced here.

**`RUNS_AT_LOCATION`** is the one edge of the five that is not named for a compliance object. Its target is a wildcard on purpose, for the reason `CONCERNS_COMPLIANCE_CONTROL` has one: the place is whatever the producer's world has (today the `github_core__github_platform` node for github.com; later the workflow, job or actions-run node when a collector puts it on the grid), and compliance_core must not name a producer's types. A scanner's location is where it is installed; a run's is where it executed. It passes the edge-naming check (`<ACTION>_<OBJECT>` with a locative preposition inside the slug, not at its end).

**`SCANNED_COMPLIANCE_TARGET`** says that a run examined a target and how that ended for it (`scanned`, `not-scanned`, `failed`: the producer's words, not a closed vocabulary). It exists because a run's `REPORTS_COMPLIANCE_FINDING` edges only say what it found: without this edge a target the run could not examine reads the same as one it examined and found clean. Its target is a wildcard for the reason `RUNS_AT_LOCATION`'s is, since what a scanner examines is whatever the producer's world has. It differs from `RUNS_AT_LOCATION`, which is where a run executed, not what it looked at. Whether a run keeps one such edge per target or only the latest is the producer's, as for `REPORTS_COMPLIANCE_FINDING`.

**Dimensions.** Edge default dimensions follow the target's type marker, as `CARRIES_COMPLIANCE_FINDING` and `CONCERNS_COMPLIANCE_CONTROL` do: `vulnerability`, `scan-run`, `finding`, `finding`. `RUNS_AT_LOCATION` has no typed target, so it takes the source's family, `scanner`; `SCANNED_COMPLIANCE_TARGET` has none either and takes its source's, `scan-run`.

**Wrong ends.** The three new nodes declare their edges (`OUTBOUND_EDGES` / `INBOUND_EDGES`), so a wrong-way or wrong-type edge at one of them is refused. `compliance_finding` declares none and gaining some would change what every consumer may draw to it, so a pair whose only wrong end is a finding used as a source is permitted by the grid's permission union.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-scan-edges-1 | The Sentences Connect | Implemented | Each edge connects its endpoints and carries the dimension above. | `tests/test_vulnerability_scanner_scan_run.py::TestEdges::test_the_sentences_connect_and_take_the_target_type_dimension` |
| req-compliance-core-scan-edges-2 | Fixed Versions Is A List | Implemented | `fixed_versions` accepts a list of strings, including `[]`; a string, a list of numbers or an unknown property is refused. | `::TestEdges::test_fixed_versions_is_a_list_that_may_be_empty`, `::test_fixed_versions_rejects_a_non_list_and_extra_keys` |
| req-compliance-core-scan-edges-3 | Wrong Ends Refused | Implemented | An edge in the wrong direction, or to the wrong type, at a scanner, run or vulnerability is refused. | `::TestEdges::test_the_wrong_way_round_or_wrong_type_is_refused` |
| req-compliance-core-scan-edges-4 | A Location May Be Any Node | Implemented | `RUNS_AT_LOCATION` accepts any node as its target from a scanner. | `::TestEdges::test_a_location_may_be_any_node` |
| req-compliance-core-scan-edges-5 | Plain Identity, References Only | Implemented | Every edge declares `{"discriminators": []}`, a re-sent edge is the same edge, and none is containment. | `::TestEdges::test_every_new_edge_declares_the_plain_identity_and_a_dimension`, `::TestIdentity::test_a_resent_edge_is_the_same_edge`, `::TestEdges::test_none_of_them_is_containment` |
| req-compliance-core-scan-edges-6 | Detects Only Without Runs | Deferred | A tool with runs reports through the run; `DETECTS_COMPLIANCE_FINDING` is for a tool without. | Producer's rule: the plugin cannot see whether a tool has runs. |
| req-compliance-core-scan-edges-7 | Cardinality Is The Producer's | Deferred | One scanner per run and one reporting run per finding. | Not enforced: edge definitions carry no cardinality. A guard would need a core constraint. |
| req-compliance-core-scan-edges-8 | Two Paths To Count A Scanner's Findings | Deferred | A page counting findings per scanner needs both paths, scanner to run to finding and scanner to finding. | Gryphon has no UNION, so that is two Searches combined in JS, or two cards. |
| req-compliance-core-scan-edges-9 | A Run May Scan Any Node | Implemented | `SCANNED_COMPLIANCE_TARGET` accepts any node as its target from a scan run, carries the `scan-run` dimension, and keeps `outcome` and `reason` as written. | `::TestEdges::test_a_run_may_scan_any_node_and_says_how_it_ended` |
| req-compliance-core-scan-edges-10 | Outcome Is Required, Only Runs Scan | Implemented | A `SCANNED_COMPLIANCE_TARGET` without a string `outcome`, with an empty one, or with an unknown property is refused, and a scanner or vulnerability as its source is refused. | `::TestEdges::test_a_scanned_target_edge_requires_a_string_outcome`, `::test_only_a_run_may_scan_a_target` |

### Vulnerability Cross-Tab Searches

RID: `req-compliance-core-searches`

Status: `Implemented`

Two vulnerability tables need a conditional count and a group-concat, which Gryphon does not have. George ruled they are computed with Django ORM aggregation in `module` Search runners (`req-grid-search-module`), declared in the manifest `[searches]` table and implemented in `tap_plugin/compliance_core/searches/cross_tabs.py`. Each returns an envelope with empty `nodes` and `edges`, `info` and `warnings`, and the table in `rows` (a table panel renders envelope `rows` as a projection). Every row value is JSON-serialisable and counts are integers.

The runners register under the runner's module scope, so a stored Search names them `tap_plugin.compliance_core.searches.cross_tabs:vulnerability-components` and `...:component-severity`.

**The shared rule.** A finding counts when its `status` is `open`, it concerns a vulnerability (`CONCERNS_COMPLIANCE_VULNERABILITY`, finding to vulnerability) and a carrier (`CARRIES_COMPLIANCE_FINDING`, carrier to finding) whose `entity_type` is not in the input `exclude_types` carries it. `exclude_types` is an array of strings supplied by the Search (absent means none); no carrier type is named in code.

**Read rules.** Every relation starts from `tap_grid.gryphon.read_scope` (`edge_relation` plus the scoped second hop), so tombstoned nodes and edges, and edges onto tombstones, are excluded; the caller's `db_alias` is used; the compiled query passes `assert_query_scoped` before it runs.

| row field | `vulnerability-components`: one row per vulnerability with at least one counted finding | meaning |
| --- | --- | --- |
| `id`, `title` | `vuln_id`, `title` | |
| `cvss` | `cvss_score` | number or null |
| `kev` | `kev` | bool (null is false) |
| `published` | `published_at` | ISO string or null |
| `components` | distinct carriers | int |
| `component_names` | distinct carrier names, sorted, joined by ", " | string |
| `component_items` | the same carriers as structured items `{id, name, type}`: `id` the carrier's entity id (string), `name`, `type` its entity type; distinct by carrier, sorted by name then id | list of objects |

Order: `cvss` descending with nulls last, then `id`.

| row field | `component-severity`: one row per carrier with at least one counted finding | meaning |
| --- | --- | --- |
| `cid`, `component`, `type` | carrier entity id, name, entity type | |
| `high` | findings whose vulnerability `cvss_score` >= 7 (critical folds into high) | int |
| `medium` | `cvss_score` >= 4 and < 7 | int |
| `low` | `cvss_score` < 4 | int |
| `unscored` | vulnerability has a null `cvss_score`; in none of the three bands | int |
| `kev` | findings whose vulnerability `kev` is true | int |
| `total` | all counted findings | int |

Order: `kev` descending, `high` descending, `total` descending, `component`. Counts are distinct findings, computed with conditional aggregation (`Count(..., filter=Q(...))`) in one query.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-searches-1 | Registered From The Manifest | Implemented | Both runners are declared in `[searches]` and registered in the search runner registry at plugin load. | `tests/test_cross_tab_searches.py::TestRegistration` |
| req-compliance-core-searches-2 | Envelope Shape | Implemented | Each runner's result is accepted by the search service, carries empty `nodes` and `edges` and `info` and `warnings` dicts, and every value in `rows` survives `json.dumps`. | `::TestRegistration::test_a_module_search_runs_through_the_search_service` |
| req-compliance-core-searches-3 | Open Findings Only, Exclusions From Input | Implemented | Closed (`resolved`) findings are not counted; carriers whose type is in `exclude_types` are not counted; no type name is hardcoded. | `::TestVulnerabilityComponents::test_closed_findings_and_excluded_carriers_are_not_counted` |
| req-compliance-core-searches-4 | Read Scope | Implemented | A tombstoned carrier, finding or vulnerability, and a tombstoned edge, contribute nothing. | `::TestReadScope` |
| req-compliance-core-searches-5 | Vulnerability Rows | Implemented | `components` counts distinct carriers (two carriers sharing a vulnerability are 2), `component_names` is sorted and joined by ", ", `cvss` may be null, `kev` is a bool, `published` an ISO string or null; rows order by cvss descending, nulls last, then id. | `::TestVulnerabilityComponents` |
| req-compliance-core-searches-6 | Severity Bands | Implemented | `high` is cvss >= 7, `medium` >= 4 and < 7, `low` < 4; the boundaries 4.0 and 7.0 fall in `medium` and `high`; a null score is counted in `unscored` and in no band; `kev` counts findings on a KEV vulnerability; `total` counts all. | `::TestComponentSeverity::test_boundaries_and_unscored` |
| req-compliance-core-searches-7 | Component Row Order | Implemented | Rows order by `kev` descending, `high` descending, `total` descending, then `component`. | `::TestComponentSeverity::test_order` |
| req-compliance-core-searches-8 | Input Validated | Implemented | An `exclude_types` that is not an array of strings is refused. | `::TestRegistration::test_exclude_types_must_be_strings` |
| req-compliance-core-searches-9 | Component Items | Implemented | Each `vulnerability-components` row carries `component_items`: one `{id, name, type}` per distinct counted carrier, `id` the carrier's entity id as a string, sorted by name then id, the same carriers as `component_names` (which is unchanged); the list survives `json.dumps` and the search service, so a table can link each component. | `::TestVulnerabilityComponents::test_component_items_are_structured_distinct_and_sorted` |

### Findings Reached Searches

RID: `req-compliance-core-reach`

Status: `Implemented`

**Gryphon has no multi-path aggregate / union-sum.** A query with several MATCH clauses is a union of the clauses, but a row projection with aggregates needs exactly one MATCH clause, and variables cannot be shared across clauses, so "the open findings of this system reached by two different routes, counted once" cannot be written in Gryphon. Two `module` Search runners compute it with Django ORM reads under the read rules Gryphon applies (`req-grid-search-module`), in `tap_plugin/compliance_core/searches/reach.py`, registered in the manifest `[searches]` table and stored as `tap_plugin.compliance_core.searches.reach:findings-reached-count` and `...:findings-reached-list`. A Search that uses them should say in its description that Gryphon lacks this capability.

The runners know no other plugin's type names. Their inputs come from the Search's `input_schema` defaults:

| input | meaning |
| --- | --- |
| `root_type` | The `entity_type` of the roots (required string). |
| `paths` | A non-empty array of at most 8 chains; each chain is a non-empty array of at most 8 edge types, followed outward (edge `from` to `to`) from a root. The entities a chain ends on are carriers. |
| `entity_id` | Optional: only this root. |
| `max_results` | `findings-reached-list` only: 1 to 5000, default 1000. |

**The counting rule.** A finding counts for a root when its `status` is `open`, a carrier carries it (`CARRIES_COMPLIANCE_FINDING`, carrier to finding) and it concerns a live vulnerability (`CONCERNS_COMPLIANCE_VULNERABILITY`). A finding reached by two chains or by two carriers counts once for the root. Tombstoned roots, carriers, findings and vulnerabilities, and tombstoned edges, contribute nothing.

| runner | rows |
| --- | --- |
| `findings-reached-count` | One row per root with at least one counted finding: `entity_id` (the root), `count` (int). |
| `findings-reached-list` | One row per counted finding: `entity_id` (the root), `name` (`<id> \| CVSS <score or n/a> \| <title>`), `id` (the vulnerability's `vuln_id`), `cvss`, `title`, `finding_id`, `component` (the display name of the carrier(s) the finding was reached through: distinct names sorted and joined with `, `, at most 3 followed by ` +k more`, `""` when no carrier has a name). A finding that concerns several vulnerabilities is listed once, under its highest-scored one. Order: `cvss` descending (unscored last), `id`, `finding_id`. |

The tap_viz status badge population reads `entity_id` and `count`; its info window reads `entity_id` and `name`, and `id` for a row link (`row_url_template`), plus any further row field a window column names (`component`, for example).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-reach-1 | Registered From The Manifest | Implemented | Both runners are declared in `[searches]` and registered in the search runner registry at plugin load. | `tests/test_reach_searches.py::TestRegistration` |
| req-compliance-core-reach-2 | Envelope Shape | Implemented | Each runner's result passes through the search service with the Search's `input_schema` defaults applied, has empty `nodes` and `edges`, and every value in `rows` survives `json.dumps`. | `::TestRegistration::test_a_module_search_runs_through_the_search_service_with_the_schema_defaults` |
| req-compliance-core-reach-3 | Paths Are Summed Without Double Counting | Implemented | Findings reached by two chains or carried by two carriers count once; each chain alone reaches fewer than their union. | `::TestCount` |
| req-compliance-core-reach-4 | Open, Concerning Findings Only | Implemented | A `resolved` finding, a finding that concerns no vulnerability and a finding whose only carries edge is retired are not counted. | `::TestCount::test_closed_unconcerning_and_retired_edge_findings_are_not_counted` |
| req-compliance-core-reach-5 | Read Scope | Implemented | A tombstoned carrier and a tombstoned edge on a chain contribute nothing. | `::TestCount::test_a_tombstoned_carrier_and_a_retired_path_edge_contribute_nothing` |
| req-compliance-core-reach-6 | One Root | Implemented | `entity_id` restricts both runners to that root. | `::TestCount::test_entity_id_restricts_to_one_root` |
| req-compliance-core-reach-7 | List Rows | Implemented | One row per counted finding, highest `cvss` first, named `<id> \| CVSS <score> \| <title>`; a finding concerning two vulnerabilities is listed once under the higher score; an unscored one reads `n/a` and sorts last. | `::TestList` |
| req-compliance-core-reach-8 | Result Limit | Implemented | `max_results` bounds the rows of `findings-reached-list`. | `::TestList::test_max_results_limits_the_rows` |
| req-compliance-core-reach-9 | Input Validated | Implemented | A missing or non-string `root_type`, missing, empty or malformed `paths`, more than 8 chains, a chain longer than 8 edges, a non-string `entity_id` and an out-of-range `max_results` are refused with a `ValueError` naming the input. | `::TestInputs` |
| req-compliance-core-reach-10 | Component Field | Implemented | Each list row carries `component`, the name of the carrier through which its finding was reached; the finding is still one row, so the row count is unchanged. | `::TestList::test_component_names_the_carrier_and_leaves_the_row_count_alone` |
| req-compliance-core-reach-11 | Component Join, Order And Cap | Implemented | A finding reached through several carriers reads their distinct names sorted and joined with `, `; past 3 names the rest read `+k more`. | `::TestList::test_component_joins_sorted_names_and_caps_with_k_more` |
| req-compliance-core-reach-12 | Unnamed Carrier | Implemented | A carrier with no name contributes nothing to `component`; with no named carrier it is `""`, never `None` or `"None"`. | `::TestList::test_an_unnamed_carrier_gives_an_empty_component_never_none` |

### Finding Detection Time
----
RID: `req-compliance-core-finding-detection`

Status: `Implemented`

A finding records when its producer first detected it. Compliance and vulnerability-response regimes count obligations from detection (FedRAMP's vulnerability reporting rules, for one, ask for the "time and source of the detection" and count the time allowed to evaluate from it), and nothing else on the finding says it: `status` says what the finding is now, and a finding is linked only to the latest scan run that saw it, so the earliest run cannot be reached by traversal. It is a fact about the finding, so it lives here and not on every consumer. (Added 2026-10-19, ruled by George; the issue is Issue# 43 - this repo.)

#### Implementation

`first_detected_at` on `compliance_finding`: a nullable date-time (`format: date-time` in both the create and the validation schema, so Gryphon `MIN` and `MAX` work over it as they do over the other timestamps). It is the producer's own record of when it first detected the finding: a GitHub alert's `created_at`, or the production time of the earliest SBOM that reported the finding. Three rules follow from the grid's conventions:

- `null` is unobserved. It is never defaulted to the time this grid first saw the finding, which is ingestion time and not detection time.
- It is not part of the natural key, which stays `("source", "source_key")`. A corrected time is the same finding.
- A node sent under an existing key replaces the row, so a field the node omits goes back to null. A producer that re-sends a finding must send `first_detected_at` again, carrying the earliest value it knows and never re-stamping it with the time of the latest scan. compliance_core cannot enforce this; it is the producer's duty, and a test pins the platform behaviour it rests on.

Existing findings carry `null` until their producer next writes one. There is no backfill.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-finding-detection-1 | Null Is Unobserved | Implemented | A finding written without `first_detected_at` stores `null`, not a default. | `tests/test_finding_first_detected_at.py::TestFirstDetectedAt::test_an_unwritten_value_is_unobserved` |
| req-compliance-core-finding-detection-2 | Round Trips As A Datetime | Implemented | A written ISO date-time reads back as the same instant. | `::test_a_written_value_round_trips_as_a_datetime` |
| req-compliance-core-finding-detection-3 | Checked As A Date-Time | Implemented | A value that is not an ISO date-time string with a time part (or null) is refused, a bare date included: the date-time field would read it as midnight and invent a precision the producer never gave. | `::test_a_value_that_is_not_a_date_time_is_refused`, `::test_an_explicit_null_is_accepted` |
| req-compliance-core-finding-detection-4 | Not Identity | Implemented | A finding re-sent with a different `first_detected_at` is the same node, with the new value. | `::test_it_is_not_part_of_the_identity` |
| req-compliance-core-finding-detection-6 | A Replaced Value Stays In History | Implemented | After a producer moves or clears `first_detected_at`, every earlier value is still on record in the finding's history. | `::test_a_replaced_value_stays_in_the_findings_history`. The field is mutable by design; this is what makes a bad write recoverable. |
| req-compliance-core-finding-detection-5 | Resend Duty | Implemented | A finding re-sent without the field goes back to `null`; the producer carries the earliest value forward. | `::test_a_resend_without_it_goes_back_to_unobserved`; pins platform behaviour, not enforced here. |

### Exception Modeling
----
RID: `req-compliance-core-exception`

Status: `Proposed`

An exception is a decision that a class of finding is acceptable, and it is only as good as what the decision says and when it was last checked. Today `compliance_exception` carries a `name`, a `description` and a `status` (`active`, `expired`, `revoked`), and its docstring defers expiration, approver and review cadence. This requirement adds them, additively and nullable, so every producer that mints an exception today keeps working. **What an exception covers is not stored here**: it lives on the exception's instances (`req-compliance-core-exception-instance`), because a decision to accept log4j in one place must never read as acceptance of log4j everywhere.

An exception is the rule; it can be one a person wrote down in a risk register, or one a plugin re-proves on a schedule (`req-compliance-core-exception-checker`). Its identity is unchanged: `source` is the producer's slug (the checker plugin, or the system of record) and `source_key` is that producer's rule id.

| field | type | meaning |
| --- | --- | --- |
| `kind` | string, one of `false-positive`, `not-affected`, `mitigated`, `operational-requirement`, `accepted-risk`; null | What sort of decision this is. The first is a claim that the scanner is wrong, the second that the component is present but the vulnerability cannot be exploited as used, the third that something else already prevents it, and the last two that the risk is real and is being lived with. Null means not observed, and an exception with no kind covers nothing. |
| `justification` | string, one of the five OpenVEX labels in kebab-case (`component-not-present`, `vulnerable-code-not-present`, `vulnerable-code-not-in-execute-path`, `vulnerable-code-cannot-be-controlled-by-adversary`, `inline-mitigations-already-exist`); null | Why a `not-affected` claim holds. Refused with any other `kind`. |
| `approver` | string, at most 200 characters; null | The person or role that approved it. For an exception granted by a checker plugin, the reviewer who merged the checker. |
| `granted_at` | datetime; null | When the decision was made. |
| `review_by` | datetime; null | The date a person is asked to look at it again. A null `review_by` is reported, not read as never. |
| `expires_at` | datetime; null | A hard ceiling after which the exception covers nothing whatever its checks say. Null means no ceiling. |
| `verify_within_hours` | integer, at least 1; null | How old the last successful check of an instance may be before it stops counting. Null means never fresh: the exception covers nothing until it is set, so an unset value is the worst case and is visible (the same stance as the VDR factors). |

`description` stays what it was by convention: the business justification and the rationale. `status` keeps its three values, but coverage never trusts a stored `active` alone; it computes expiry from `expires_at` (`req-compliance-core-exception-coverage`).

#### Implementation

- `ComplianceException` in `tap_plugin/compliance_core/models/compliance_exception.py` gains the seven columns, each nullable, in `FIELD_CRUD_SCHEMA` and `FIELD_VALIDATION_SCHEMA` with a description on every field. `justification` validates against the five labels per field; the cross-field rule that it is refused unless `kind` is `not-affected` is a `validate()` override on the model, the whole-record hook that `full_validate()` calls after the per-field checks (`req-grid-entity-validation-9`), raising a `ValidationError` keyed on `justification`. `CREATE_REQUIRED` stays `["name"]`.
- `CONTAINMENT_EDGES = ("GRANTS_COMPLIANCE_EXCEPTION_INSTANCE",)`, a permitted outbound edge of the model (`tap_grid/models.py` refuses a containment declaration naming an edge the model may not emit).
- A schema migration, numbered when built (main's latest is `0007`), adds the columns; it rewrites no row.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-exception-1 | New Fields Are Nullable | Proposed | An exception created with only a `name`, as every current producer does, is accepted and reads back with the seven new fields null. | Backward compatibility with `fedramp_20x_ksi`'s minted exceptions. |
| req-compliance-core-exception-2 | Kind And Justification Are Closed | Proposed | A `kind` outside the five, a `justification` outside the five labels, and a `justification` on any `kind` but `not-affected` are refused. | Vocabulary drawn from GitHub's dismissal reasons, OpenVEX and the FedRAMP deviation types. |
| req-compliance-core-exception-3 | Verify Window Is A Positive Integer | Proposed | `verify_within_hours` accepts an integer of at least 1 or null; zero, negatives and non-integers are refused. | |
| req-compliance-core-exception-4 | Containment Declared | Proposed | `CONTAINMENT_EDGES` names `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE` and that edge is a permitted outbound edge of the model. | The class-creation guard in `tap_grid/models.py`. |
| req-compliance-core-exception-5 | Identity Unchanged | Proposed | The natural key stays `("source", "source_key")`; re-sending an exception under the same key is the same node. | `req-compliance-core-identity`. |
| req-compliance-core-exception-6 | Additive Migration | Proposed | The schema migration adds the columns and changes no existing row. | |

### Exception Instance Modeling
----
RID: `req-compliance-core-exception-instance`

Status: `Proposed`

`compliance_exception_instance` is one exception applied to one vulnerability within one declared scope, together with the result of the last attempt to show that application false. It is the grid's version of the record Kyverno writes into a policy report and Trivy prints for a suppressed finding: not the rule, but "this rule, here, last checked then, held". An exception has many instances and an instance has one exception.

It is a node and not an edge property for three reasons the design settled on. It must be deleted with its exception (the grid already cascades through declared containment, and a pair of edges on two different nodes cannot be deleted together). It must outlive the finding it covers (a tombstone is terminal, so an edge to a finding dies with the finding, but the instance holds the scope and can bind the next finding). And it carries the check result, which belongs to neither endpoint.

| field | type | meaning |
| --- | --- | --- |
| `name` | string, required | A label for reviewers. |
| `source`, `source_key` | strings | Identity (`req-compliance-core-identity`). `source` is the producer's slug; `source_key` is deterministic from the parent exception's `source_key`, the vulnerability id and the anchors, so the same application is found again on every run. compliance_core never parses it. |
| `outcome` | string, `held` or `falsified`; null | The result of the last check. Null means never checked, which is uncovered. |
| `verified_at` | datetime; null | When that check ran. Null means never. |
| `anchor_count` | integer, at least 1, required | How many scope anchors the producer declared for this instance (`req-compliance-core-exception-edges`). Coverage requires that many to be live. |
| `detail` | string; null | What the check saw, in the checker's words. |

The instance has no `status`. Its lifecycle is `outcome` plus retirement. Default dimension: `compliance: exception-instance`.

#### Implementation

- `ComplianceExceptionInstance` in `tap_plugin/compliance_core/models/compliance_exception_instance.py`, entity type `compliance_core__compliance_exception_instance`, `NATURAL_KEY = ("source", "source_key")`, `CREATE_REQUIRED = ["name", "anchor_count"]`, every field described.
- Declared edges (`OUTBOUND_EDGES` / `INBOUND_EDGES`) as in `req-compliance-core-exception-edges`, so a wrong-way or wrong-type edge at an instance is refused.
- A manifest entry, an icon, and a schema migration.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-exception-instance-1 | The Node Exists With A Key And A Dimension | Proposed | The entity type is `compliance_core__compliance_exception_instance`, it keys on `("source", "source_key")`, and a new instance carries `compliance: exception-instance`. | |
| req-compliance-core-exception-instance-2 | Outcome Has Three States | Proposed | `outcome` accepts `held`, `falsified` or null; any other string is refused; null reads back as null, never as an empty string. | Null is unobserved (the grid's null convention). |
| req-compliance-core-exception-instance-3 | Anchor Count Is Required | Proposed | An instance created without `anchor_count`, or with a value below 1, is refused. | A scope of zero anchors would be a blanket approval. |
| req-compliance-core-exception-instance-4 | Same Key Is The Same Node | Proposed | Re-sending an instance with the same `(source, source_key)` updates it; the producer re-sends every field it owns. | A GRIFT node under an existing key replaces the row and nulls omitted fields (Issue# 1071 - tap), so a partial re-send would erase `outcome`. |
| req-compliance-core-exception-instance-5 | Wrong Ends Refused | Proposed | An edge at an instance in the wrong direction or to the wrong type is refused. | |
| req-compliance-core-exception-instance-6 | Recording Check Time Without A New Version Each Run | Backlog | `verified_at` changes on every successful check. The grid treats re-observation as not a change, so the design needs either that rule to admit a check-time field or the freshness to be derived from the latest scan run that scanned the instance. | Open: Issue# 322 - tap and Issue# 323 - tap. v0 stores the field; the derived form is the alternative. |

### Exception Edges
----
RID: `req-compliance-core-exception-edges`

Status: `Proposed`

Three new edges, one retargeted, one widened. Names are proposed and must pass `req-tap-plugin-edge-naming` (a verb and an object noun, no modal prefix, no trailing preposition).

| edge (compliance_core) | endpoints | properties |
| --- | --- | --- |
| `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE` | `compliance_exception` → `compliance_exception_instance` | none. The only containment edge of this set. |
| `EXEMPTS_COMPLIANCE_VULNERABILITY` | `compliance_exception_instance` → `compliance_vulnerability` | none |
| `SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET` | `compliance_exception_instance` → any node (wildcard target) | none |
| `COVERS_COMPLIANCE_FINDING` | `compliance_exception_instance` → `compliance_finding` (was `compliance_exception` → `compliance_finding`) | none |
| `CITES_COMPLIANCE_EVIDENCE` | `compliance_finding` or `compliance_exception_instance` → `compliance_evidence` (sources widened) | none |
| `SCANNED_COMPLIANCE_TARGET` (existing) | `compliance_scan_run` → `compliance_exception_instance` | `outcome` (existing) |

**The scope rule, which is the point of the node.** An instance has exactly one vulnerability (`EXEMPTS_COMPLIANCE_VULNERABILITY`) and at least one scope anchor (`SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET`). A vulnerability alone is never a scope: an instance with no live anchor covers nothing, so "log4j, anywhere" cannot be written down as a decision. What is enforced is that the declared anchors exist and are live; that they actually contain the covered finding is the checker's binding, which compliance_core trusts and does not verify (`req-compliance-core-exception-edges-7`, Backlog). An instance bound to a finding its anchors do not reach would read covered, so a checker must bind only findings inside its own scope. The anchors are ANDed, which gives both ends of the range with no extra mechanism. *General*: one anchor, for example the package node `(ecosystem, name, version)`, which every image carrying that package shares. *Specific*: two or more anchors, for example that package and one image or SBOM document, so the exception holds for that package in that image and nowhere else. The producer declares how many anchors it meant in `anchor_count` and the coverage rule requires them all (`req-compliance-core-exception-coverage`).

**The anchor target is a wildcard**, for the reason `RUNS_AT_LOCATION` and `CONCERNS_COMPLIANCE_CONTROL` have one: what a producer's world offers as a package, an image, a host or an SBOM document is not compliance_core's to name.

**`COVERS_COMPLIANCE_FINDING` moves to the instance.** The instance, not the exception, is what is bound to a specific finding, and the binding is what a checker asserts or lets lapse. Live rows of the old shape (an exception as source) are retired by a data migration, kept apart from the schema migration, as `0003` retired two renamed edges; ids derive from the slug so the next collection re-emits what is still true. Consumers that read the old shape retarget in their own repositories: `fedramp_20x_ksi`'s finding-profile spec describes an exception banner that reads this edge from an exception (`specs/spec-fedramp-20x-ksi-finding-profile.md`, the exception coverage panel line) and its instance-findings spec says the open-findings counter reads it. Code readers were not searched.

**Edges carry no cardinality**, so "one vulnerability, at least one anchor" cannot be refused at write. A producer keeps to it, and coverage treats an instance that breaks it as covering nothing.

**Dimensions.** The edges follow the target's type marker as the existing ones do: `exception-instance`, `vulnerability`, `exception-instance` (the wildcard takes its source's family), `finding`. Every edge declares the plain identity `{"discriminators": []}`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-exception-edges-1 | The Sentences Connect | Proposed | Each edge in the table connects its endpoints and carries the dimension above. | |
| req-compliance-core-exception-edges-2 | Containment Is Only The Grant | Proposed | `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE` is the only edge in `CONTAINMENT_EDGES`; deleting an exception with `cascade="contained"` retires its instances, and deleting an instance leaves the exception, finding, vulnerability and anchors live. | `req-grid-service-delete-cascade`. |
| req-compliance-core-exception-edges-3 | An Anchor May Be Any Node | Proposed | `SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET` accepts any node as its target from an instance, and refuses any other source. | |
| req-compliance-core-exception-edges-4 | Covers Moves To The Instance | Proposed | `COVERS_COMPLIANCE_FINDING` accepts an instance as its source and refuses an exception; `CITES_COMPLIANCE_EVIDENCE` accepts an instance or a finding as its source. | |
| req-compliance-core-exception-edges-5 | Old Covers Rows Retired | Proposed | A data migration, separate from the schema migration, retires live `COVERS_COMPLIANCE_FINDING` rows whose source is an exception and touches no other row. | Precedent: migration `0003`. |
| req-compliance-core-exception-edges-6 | Plain Identity | Proposed | Every new edge declares `{"discriminators": []}` and a re-sent edge is the same edge. | |
| req-compliance-core-exception-edges-7 | Anchors Reach The Finding | Backlog | A check that each anchor actually reaches the covered finding along carries or path edges, as the reach runners follow them. | v0 relies on the checker's binding and on the vulnerability match; the topology of who carries a finding is set by the producers, so the path declarations need a design of their own. |

### Exception Coverage
----
RID: `req-compliance-core-exception-coverage`

Status: `Proposed`

Whether a finding is covered is a question the grid answers when asked, from facts, and never a flag written onto the finding or the exception. Storing it would need undoing in every path that can end it (DefectDojo reverses `active` and `risk_accepted` in four code paths and has to decide whether the clock restarts); computing it ends coverage by the absence of a fact and needs nothing undone.

An instance covers a finding only when **every** one of these holds, tested against `as_of` (default: now):

1. A live `COVERS_COMPLIANCE_FINDING` edge runs from the instance to the finding.
2. The finding's `status` is `open`.
3. The finding concerns the one vulnerability the instance exempts.
4. The instance's `outcome` is `held`.
5. `verified_at` is not null, is not after `as_of`, and is no older than the exception's `verify_within_hours`, which must itself be set. A check time in the future proves nothing yet and would keep the instance fresh past its window, so it counts as unverified.
6. The exception that grants the instance is live, has a `kind`, has `status` `active`, and has no `expires_at` or one after `as_of`.
7. The instance has at least `anchor_count` live scope anchors, so a retired image can never widen a specific scope into a general one.
8. Nothing on the path is tombstoned.

Null or stale anywhere in that list means uncovered. This is the grid's null convention applied the way the VDR rulings apply it: an unset factor is the worst case and the value is visible.

#### Implementation

- Two `module` Search runners, registered from the manifest like `findings-reached-count`, built with the ORM and the standard-library `datetime`, not Gryphon date arithmetic (Issue# 1064 - tap is not required), reading under the read rules Gryphon applies.
- `finding-exception-coverage`: inputs `entity_id` (optional, one finding), `as_of` (optional ISO datetime), `max_results` (1 to 5000, default 1000). One row per open finding with at least one `COVERS_COMPLIANCE_FINDING` edge from an instance: `entity_id` (the finding), `covered` (boolean), `instance_id`, `exception_id`, `reason`. A finding with several instances is covered if any covers; `reason` is `covered`, or the number and name of the first failing condition above for the instance that passes the most. Ties break on instance id.
- `exceptions-due-review`: inputs `as_of`, `max_results`. One row per exception with at least one of the reasons `review-overdue`, `no-review-date`, `expired`, `no-verify-window`: `entity_id` (the exception), `name`, `reasons` (list), `instance_count`.
- Neither runner writes.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-exception-coverage-1 | Registered From The Manifest | Proposed | Both runners are declared in `[searches]` and registered at plugin load, and their results pass through the search service with the schema defaults applied. | As `req-compliance-core-reach-1`. |
| req-compliance-core-exception-coverage-2 | All Eight Conditions Are Required | Proposed | A finding with an instance satisfying all eight reads `covered` true; making any one fail, one at a time, reads false with that condition in `reason`. | One test per condition. |
| req-compliance-core-exception-coverage-3 | Unset Is Uncovered | Proposed | A null `outcome`, null `verified_at`, null `verify_within_hours`, null `kind` and an instance with no vulnerability or no anchor each read uncovered. | |
| req-compliance-core-exception-coverage-4 | Stale Is Uncovered | Proposed | An instance verified longer ago than `verify_within_hours` before `as_of` reads uncovered, and one verified inside the window reads covered. | |
| req-compliance-core-exception-coverage-10 | A Future Check Time Is Unverified | Proposed | An instance whose `verified_at` is after `as_of` reads uncovered, whatever `verify_within_hours` is; one verified a year after `as_of` does not read covered. | Found in review of the draft; a mistaken or hostile future timestamp must not keep coverage fresh. |
| req-compliance-core-exception-coverage-11 | An Unreached Anchor Is Trusted, Not Checked | Proposed | A test records the boundary: an instance whose only live anchor is a node unrelated to the covered finding still reads covered, and the result's `reason` says nothing about the anchor. | The test documents the producer-trust boundary until `req-compliance-core-exception-edges-7` is built; it is not a feature. |
| req-compliance-core-exception-coverage-5 | Expiry Is Computed | Proposed | An exception whose stored `status` is `active` but whose `expires_at` is before `as_of` covers nothing. | |
| req-compliance-core-exception-coverage-6 | A Lost Anchor Never Widens The Scope | Proposed | Retiring one of two anchors makes the instance uncovered; it does not become the general case. | |
| req-compliance-core-exception-coverage-7 | Any Covering Instance Is Enough | Proposed | A finding with one failing and one covering instance reads covered; with two failing instances it reads uncovered with the reason of the closer. | |
| req-compliance-core-exception-coverage-8 | Review Due | Proposed | `exceptions-due-review` lists an exception past `review_by`, one with no `review_by`, one past `expires_at` and one with no `verify_within_hours`, and omits one with none of these. | |
| req-compliance-core-exception-coverage-9 | Read Scope And Input Validation | Proposed | A tombstoned instance, exception, finding or edge contributes nothing; a malformed `as_of`, a non-string `entity_id` or an out-of-range `max_results` is refused with a `ValueError` naming the input. | As `req-compliance-core-reach-5` and `-9`. |

### Exception Lifecycle
----
RID: `req-compliance-core-exception-lifecycle`

Status: `Proposed`

Four things can end or change coverage, each with one defined effect.

**Withdrawal.** Deleting an exception with `cascade="contained"` retires its instances in one transaction and, through the grid's endpoint cascade, every edge touching them. The findings, vulnerabilities, anchors, evidence and scan runs are references, not contained, and stay live. The delete carries a reason from the closed vocabulary of `req-grid-service-delete-reason`: a checker that stops asserting a rule uses `scope_withdrawn`, and `operator` is used only when a human acted, never as a default. The cascade is partial in the grid (preflight and `cascade_force` are Backlog there); this requirement relies on neither.

**Falsification.** A check that fails updates the instance to `outcome` `falsified` with a fresh `verified_at` and a `detail`. The instance is kept, the `COVERS_COMPLIANCE_FINDING` edge is kept, and coverage drops through condition 4. The history of the instance records that it once held. A later check that holds updates the same instance back to `held`.

**A finding that returns.** A tombstone is terminal: the grid has no restore verb, and a finding that becomes observable again is a new observation under the same natural key (`req-grid-reconcile-observation-lifetime`). The edge from the instance to the old finding ended with it. The instance is not retired by that. The checker's next run binds the instance to the new finding by writing a fresh `COVERS_COMPLIANCE_FINDING`, and until it does the new finding is uncovered. The failure direction is always toward uncovered.

**An anchor that goes.** An anchor retired leaves fewer live anchors than `anchor_count`; the instance covers nothing until a producer either restores the scope or declares the narrower scope it now means.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-exception-lifecycle-1 | Withdrawal Cascades | Proposed | Deleting an exception with `cascade="contained"` tombstones its instances and the edges touching them, with the reason carried, and leaves every other node live. | |
| req-compliance-core-exception-lifecycle-2 | Falsification Keeps The Instance | Proposed | A falsified check leaves the instance and its covers edge live with `outcome` `falsified`; coverage reads uncovered; history shows the earlier `held`. | |
| req-compliance-core-exception-lifecycle-3 | A Returning Finding Is Uncovered Until Re-bound | Proposed | After the covered finding is tombstoned and a new one is minted under the same natural key, the new finding reads uncovered until the instance gains a covers edge to it; the instance itself is unchanged. | |
| req-compliance-core-exception-lifecycle-4 | Orphan Instance Covers Nothing | Proposed | An instance whose exception is tombstoned or has no live grant edge covers nothing. | |
| req-compliance-core-exception-lifecycle-5 | Cascade Preflight | Backlog | A read-only plan of what withdrawing an exception would retire, before applying. | The grid's `req-grid-service-delete-cascade-plan`. |

### Exception Checker Contract
----
RID: `req-compliance-core-exception-checker`

Status: `Proposed`

compliance_core ships no checker, only the vocabulary one writes. A **checker** is a plugin, in its own repository, that on a schedule selects candidate findings with a Search, tries to show a stated condition false for each, and records the result. It is the same shape as a scanner that reads the grid (as grype-tap and zizmor-tap are), and it is how an exception becomes code that can be exercised repeatedly against the system it vouches for. The schedule replaces a fixed duration of acceptance; `review_by` remains the date a person is asked to look again.

What a checker owes the grid:

- **Identity.** `source` is its slug. The exception's `source_key` is its rule id; each instance's is deterministic from the rule id, the vulnerability and the anchors.
- **A scanner and a run.** It registers as a `compliance_scanner`; each execution is a `compliance_scan_run` that writes `SCANNED_COMPLIANCE_TARGET` to each instance it examined with an `outcome` in its own words (`scanned`, `failed`, `not-scanned`). A target a run could not examine must not read as one it checked and cleared.
- **The result.** Each run sets `outcome` and `verified_at` on every instance it owns, held or falsified, and re-sends every field it owns (Issue# 1071 - tap).
- **A falsifiable condition.** The condition names what would make it false and what it observed (`detail`, and a `CITES_COMPLIANCE_EVIDENCE` edge to the observation). A condition that cannot fail is not a check.
- **The parent's fields.** It sets `kind`, `approver`, `granted_at`, `review_by` and `verify_within_hours`, and sets `verify_within_hours` no shorter than its own schedule, since a window shorter than the interval between runs makes the exception lapse by design.
- **Scope kept to what it declared.** It binds `COVERS_COMPLIANCE_FINDING` only to findings that concern the instance's vulnerability and sit within its anchors. compliance_core does not verify the anchors (`req-compliance-core-exception-edges-7`).
- **Approval is the merge.** The checker's code review, and its pin in a boot record, are the approval of the decision it encodes; `approver` names the reviewer. This is a process stated here as the design, not something compliance_core enforces.

*Illustrative, not a requirement.* A scanner reported log4j-core 2.14.1 in an image whose SBOM lists no such component. A checker for that disagreement has the condition "the image's SBOM revision contains no component with this package URL", anchors the instance to the package and the SBOM document, uses `kind` `false-positive`, and cites the SBOM digest as evidence. If a later image does contain the component, the condition fails, the instance reads `falsified`, and the finding is uncovered. (The better fix for that particular case is upstream: do not ship the test fixture. An exception is for what remains true after the fix at the source has been considered.)

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-exception-checker-1 | No Checker Ships Here | Proposed | compliance_core contains no collector, scheduler entry or checker. | Consistent with `req-compliance-core-nongoals`. |
| req-compliance-core-exception-checker-2 | The Vocabulary Suffices | Proposed | A checker can be written using only the nodes and edges of this spec and the existing scanner, scan-run and evidence vocabulary; no wildcard or new edge is needed beyond `req-compliance-core-exception-edges`. | Demonstrated by a test plugin or a fixture in the first checker's repository. |
| req-compliance-core-exception-checker-3 | A Run Records What It Could Not Examine | Proposed | A checker whose run could not examine an instance writes `SCANNED_COMPLIANCE_TARGET` with a non-`scanned` outcome and does not refresh `verified_at`. | |
| req-compliance-core-exception-checker-4 | Window Not Shorter Than Schedule | Proposed | A checker never sets `verify_within_hours` below its own run interval. | Producer's rule; compliance_core cannot see the schedule. |
| req-compliance-core-exception-checker-5 | Approval Is Recorded | Proposed | `approver` is set on every exception a checker grants. | Producer's rule. |

### Naming Discipline
----
RID: `req-compliance-core-naming`

Status: `Implemented`

Node names carry the `compliance_` domain qualifier for system-wide disambiguation
(`compliance_evidence` vs a future `crime_scene_evidence`). Edge slugs name their
object with the same qualifier so the verb tracks the node type it targets
(`CITES_COMPLIANCE_EVIDENCE`, not `HAS_EVIDENCE`). This is the "name the specific object"
discipline from the add-edge skill, not redundant endpoint repetition: the object's
actual type name *is* `compliance_evidence`. The doubled `compliance_core__compliance_*`
entity_type is intentional — the plugin slug is ownership, the name qualifier is
semantic domain.

### Dependency Direction
----
RID: `req-compliance-core-deps`

Status: `Implemented`

compliance_core depends on nothing above core (`tap_grid`/`tap`). Consumers depend
**downward**: `fedramp_20x_ksi`, `roscale`, and `samsite` declare
`compliance-core-tap` in `pyproject.toml` and list `compliance_core` in
`depends_on`. The AST import-graph guard (`tap/plugin_deps.py`) enforces that any
`from tap_plugin.compliance_core…` import is declared.

### Consumer Retargets
----
RID: `req-compliance-core-consumer-retargets`

Status: `Implemented`

- **samsite** — the compliance collector, `decompose.py`, the `ksi_scoreboard` panel,
  landing/compliance/iiw grift, and `artifact_manifest` retarget
  `fedramp_20x_ksi__compliance_artifact` → `compliance_core__compliance_artifact` (~15
  string sites), and evidence/finding/exception/boundary type strings + the moved edge
  slugs to their compliance_core forms. (No regime dimension is stamped in v0 — see the
  honest note in `req-compliance-core-regime-neutral`.)
- **fedramp_20x_ksi** — drops the six moved models + their migrations; keeps `ksi_*`
  and `vdr_*`. Any fedramp query/edge referencing the moved types retargets.
- **Bridge edge (generalized)** — the former `RELATED_INDICATOR` (`finding →
  ksi_indicator`) was **not** kept as a fedramp-specific edge: "a finding concerns a
  compliance control" is a cross-regime relationship, so it became
  `CONCERNS_COMPLIANCE_CONTROL` in **compliance_core** with a typed source
  (`compliance_finding`) and a **wildcard target**. A finding can now concern controls in
  any regime's catalog — a FedRAMP `ksi_indicator`, a SOC2 criterion, several at once.
  fedramp's panels/grift still constrain the target to `ksi_indicator` in their queries.
  This also removes a Phase-B awkwardness (fedramp owning an edge sourced from a
  compliance_core node). The generic `compliance_control` supertype that would let the
  target be *constrained* rather than wildcard is deferred to the second regime.
- **roscale** — no change (references the generic concepts by string zero times today).

### Extraction & Migration
----
RID: `req-compliance-core-migration`

Status: `Implemented`

Renames `fedramp_20x_ksi__{compliance_artifact, compliance_context, evidence, finding,
exception, boundary}` → `compliance_core__compliance_*`. The `entity_type` change
shifts the `uuid5`-derived ids, but every one of these nodes is **collected**
(re-produced each run by samsite's compliance collector), not a static seed, so ids
regenerate cleanly on the next collection (contrast the uuid5-hash-token-fallout that
bit a *static* seed).

Phased first slice (bounds blast radius):

1. **Phase A (proven-cheap):** stand up compliance_core with `compliance_artifact` +
   `compliance_context` (artifact is the ~15 samsite swaps; context is already
   regime-generic and moves free). Models + one migration + pyproject + `apps.py=pass`.
2. **Phase B:** add `compliance_evidence` + `compliance_finding` + `compliance_exception`
   + `compliance_boundary` and their four edges; apply the regime-dimension fix. Then
   generalize the fedramp bridge edge `RELATED_INDICATOR` into the fifth compliance_core
   edge `CONCERNS_COMPLIANCE_CONTROL` (wildcard target); retarget consumers.

Ordering: this is namespace churn (new `entity_type`s, new edge owners), so it MUST
land **before eviction** freezes plugins at released tags; otherwise the rename becomes
a coordinated multi-repo re-tag across compliance_core + fedramp + samsite.

### v0 Non-Goals
----
RID: `req-compliance-core-nongoals`

Status: `Implemented`

- **`ksi_*` vocabulary** (signal/theme/indicator/component/validation/violation) stays
  in fedramp_20x_ksi — strictly KSI-framework, KSI-signal-native. `ksi_component` in
  particular is one entry of a KSI signal's `components[]` array (keyed by
  `component_id` that KSI validations join on), not an OSCAL primitive — OSCAL is
  downstream of the signal.
- **`vdr_finding` / `vdr_report`** stay in fedramp_20x_ksi — welded to Sam's
  PAIN/IRV/LEV/KEV/SLA evaluation schema. They may later become a `compliance_finding`
  specialization + VDR eval fields (the coming fedramp_20x split), but not now.
- **Generic `compliance_component`** — deferred; `ksi_component` remains KSI-bound in v0.
- **No collector, no regime logic, no assessment engine.** compliance_core is
  vocabulary only; regimes and deployments own the wiring.
- **Exception checkers, severity ceilings, deviation-type mapping, approval workflow and pages**
  (proposed 2026-10-19) — the checker plugins live in their own repositories
  (`req-compliance-core-exception-checker`); a regime's limits on which `kind` may cover which severity
  (FedRAMP does not approve an operational requirement for a High) belong to that regime's plugin; the
  mapping of `kind` to a regime's deviation types likewise; an exceptions page is a later `add-page`.
  Scanner-side exclusions (a path never scanned, a file never shipped in an image) are not exceptions:
  they act before a finding exists and belong to the scanner's configuration or the build.
