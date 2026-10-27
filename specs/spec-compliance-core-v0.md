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
| req-compliance-core-dimension-coverage | [Dimension Coverage Search](#dimension-coverage-search) | Implemented | One generic `module` Search runner, `dimension-coverage`, counts the entities carrying each value of a dimension key, broken down by entity type, which Gryphon cannot group. |
| req-compliance-core-dimension-mapping | [Dimension Mapping Searches](#dimension-mapping-searches) | Implemented | Two generic `module` Search runners, `dimension-mapping-summary` and `dimension-mapping-entities`, compare what entities carry against a mapping held in the Search's inputs and report each live entity of a mapped type as mapped, unmapped or mapped incorrectly. A mapping row may name a group of entity types, a key may accept any present value, and the summary may report one row per value of a grouping dimension (the inventory category). |
| req-compliance-core-dimension-mapping-totals | [Dimension Mapping Totals](#dimension-mapping-totals) | Implemented | `dimension-mapping-totals`: one row of live totals (the plain-average coverage, the pooled counts) for a grouped summary Search, read from that Search's own inputs, so a card shows the figures with no second copy of the mapping. |
| req-compliance-core-dimension-mapping-totals-set | [Dimension Mapping Totals Set](#dimension-mapping-totals-set) | Implemented | `dimension-mapping-totals-set`: one row per summary Search, each carrying its key, a label and the totals, so one stat-card panel shows several coverages side by side from one Search. |
| req-compliance-core-finding-detection | [Finding Detection Time](#finding-detection-time) | Implemented | `compliance_finding.first_detected_at`: when the producer first detected the finding; null until a source says; not identity. |
| req-compliance-core-exception | [Exception Modeling](#exception-modeling) | Implemented | `compliance_exception` gains `kind`, `justification`, `approver`, `granted_at`, `review_by`, `expires_at` and `verify_within_hours`, and declares its instances as contained. |
| req-compliance-core-exception-instance | [Exception Instance Modeling](#exception-instance-modeling) | Implemented | `compliance_exception_instance`: one exception's application to one vulnerability within one declared scope; carries the last check's `outcome` and `verified_at`. |
| req-compliance-core-exception-edges | [Exception Edges](#exception-edges) | In Development | `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE` (containment), `EXEMPTS_COMPLIANCE_VULNERABILITY`, `SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET`; `COVERS_COMPLIANCE_FINDING` moves to the instance; `CITES_COMPLIANCE_EVIDENCE` accepts an instance. |
| req-compliance-core-exception-coverage | [Exception Coverage](#exception-coverage) | Implemented | Coverage is computed, never stored: two `module` Search runners, `finding-exception-coverage` and `exceptions-due-review`. Unset or stale means not covered. |
| req-compliance-core-exception-lifecycle | [Exception Lifecycle](#exception-lifecycle) | Proposed | Withdrawal cascades through containment; falsification updates the instance and keeps it; a re-minted finding is a new entity the checker must re-bind. |
| req-compliance-core-exception-checker | [Exception Checker Contract](#exception-checker-contract) | Proposed | What a plugin that checks an exception on a schedule owes the grid; compliance_core ships no checker. |
| req-compliance-core-naming | [Naming Discipline](#naming-discipline) | Implemented | `compliance_` node-name prefix; edge object noun tracks the node type. |
| req-compliance-core-deps | [Dependency Direction](#dependency-direction) | Implemented | Downward-only; declared in consumers' `pyproject.toml` + `depends_on`. |
| req-compliance-core-consumer-retargets | [Consumer Retargets](#consumer-retargets) | Implemented | fedramp/samsite retarget type strings + edges; the fedramp bridge edge `RELATED_INDICATOR` was generalized into `CONCERNS_COMPLIANCE_CONTROL` (compliance_core, wildcard target). |
| req-compliance-core-migration | [Extraction & Migration](#extraction--migration) | Implemented | Rename `fedramp_20x_ksi__*` → `compliance_core__compliance_*`; ids regenerate (collected, not seeded); phased first slice; pre-eviction. |
| req-compliance-core-nongoals | [v0 Non-Goals](#v0-non-goals) | Implemented | `ksi_*` and `vdr_*` stay in fedramp; no collector; no regime logic; generic `component` deferred. |
| req-compliance-core-search-snapshot | [Search Snapshot Modeling](#search-snapshot-modeling) | Implemented | `compliance_search_snapshot`: one run of one Search, with its result rows held inside the node, keyed by the Search and the run time, and an edge to the Search it ran. |
| req-compliance-core-search-snapshot-collector | [Search Snapshot Collector Base](#search-snapshot-collector-base) | Implemented | `SearchSnapshotCollector`: an abstract collector that runs the Searches a subclass names and writes one snapshot per Search per run. compliance_core registers none. |
| req-compliance-core-search-snapshot-series | [Search Snapshot Series](#search-snapshot-series) | Implemented | The `search-snapshot-series` `module` Search runner: the rows of a Search's snapshots read back as one row per snapshot time and series, with a plain-average aggregate series, for a line chart. |
| req-compliance-core-panel-report | [Report Panel](#report-panel) | Implemented | The `report` panel type: a plain, print-ready report of figures, trend lines and short lists, each read from a Search the panel is linked to, drawn as text and vector lines with no script. |

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
| `compliance_core__compliance_search_snapshot` | new, proposed 2026-10-20 | `name`, `source` + `snapshot_key` (identity), `search_name`, `observed_at`, `row_count`, `rows`, `truncated`, `inputs_text`; see `req-compliance-core-search-snapshot` |

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
| `CAPTURES_SEARCH` | new, proposed 2026-10-20 | `compliance_search_snapshot` → `search` (`req-compliance-core-search-snapshot`) |

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
| `CONCERNS_COMPLIANCE_VULNERABILITY` | `compliance_finding` → `compliance_vulnerability` | `fixed_versions`: list of strings, may be empty. `fix_state`: optional string, one of `fixed`, `not-fixed`, `wont-fix`, `unknown`. |
| `PERFORMS_COMPLIANCE_SCAN_RUN` | `compliance_scanner` → `compliance_scan_run` | none |
| `REPORTS_COMPLIANCE_FINDING` | `compliance_scan_run` → `compliance_finding` | none |
| `DETECTS_COMPLIANCE_FINDING` | `compliance_scanner` → `compliance_finding` | optional `tool_version`, `category`. |
| `RUNS_AT_LOCATION` | `compliance_scanner` or `compliance_scan_run` → any node (wildcard target) | `locator`: the place as the data gave it. |
| `SCANNED_COMPLIANCE_TARGET` | `compliance_scan_run` → any node (wildcard target) | `outcome`: required string, the producer's own word for how the examination ended; optional `reason`. |

**`CONCERNS_COMPLIANCE_VULNERABILITY`** is named after `CONCERNS_COMPLIANCE_CONTROL`. Its `fixed_versions` is the fix in the component the finding is about, because the same vulnerability is fixed at a different version in each component. `[]` means the source looked and named no fix; an absent property means it was not observed.

`fix_state` says why the list is what it is, in the scanner's own four words: `fixed` (a fix exists), `not-fixed` (no fix yet), `wont-fix` (the party that decides, such as a distribution's security team, has declined to fix it) and `unknown` (the scanner could not say). `[]` alone cannot tell "no fix yet" from "will not be fixed", and remediation needs the difference: the first can change, the second means replacing or accepting the component. Like `fixed_versions` it is a fact about the vulnerability in one component, so it rides the edge. An absent `fix_state` means the source carried no state at all; the scanner's `unknown` is a stated answer and is kept. The property does not constrain `fixed_versions` (a source may name versions beside `not-fixed`), and nothing here derives one from the other. "Wont-fix" is the source's declaration, not a TAP judgement and not an upstream maintainer's statement unless the source says so.

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
| req-compliance-core-scan-edges-11 | Fix State Names Why | Implemented | `CONCERNS_COMPLIANCE_VULNERABILITY` accepts an optional `fix_state` that is one of `fixed`, `not-fixed`, `wont-fix` or `unknown` and keeps it as written; an edge without it is valid; any other string, a non-string or an unknown property is refused; the edge definition's description and property schema describe it. | `::TestEdges::test_fix_state_keeps_each_of_the_four_scanner_words_beside_fixed_versions`, `::test_an_edge_without_fix_state_is_valid_and_says_nothing`, `::test_fix_state_refuses_anything_but_the_four_words`. Lets "no fix yet" and "will not be fixed" be told apart; `fixed_versions` is unchanged. |

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

### Dimension Coverage Search
----
RID: `req-compliance-core-dimension-coverage`

Status: `Implemented`

**Gryphon has no labelless aggregate grouped by entity type and by dimension value.** "How many entities carry each value of this dimension, and of what types" is a count over every node regardless of type, grouped by `entity_type` and by the value of one dimension key. Gryphon cannot write it: a MATCH needs a node label, and a count grouped by the entity type itself or by a dimension value taken from a Search input is not supported. A `module` Search runner computes it with Django ORM aggregation under the read rules Gryphon applies (`req-grid-search-module`; George's ruling to build a module runner rather than the Gryphon capability), in `tap_plugin/compliance_core/searches/dimension_coverage.py`, registered in the manifest `[searches]` table and stored as `tap_plugin.compliance_core.searches.dimension_coverage:dimension-coverage`. A Search that uses it should say in its description that Gryphon lacks this capability (a labelless aggregate grouped by entity type and by dimension value).

The runner knows no dimension key, value or entity type. Its inputs come from the Search's `input_schema` defaults:

| input | meaning |
| --- | --- |
| `dimension_key` | The dimension to cover, for example `dataclass.customer` (required, non-empty string). |
| `exclude_types` | Entity types that are not counted, for example the spine rows of edges and batches (array of strings, default none). |

**The dictionary is read from the grid.** The key's own `dimension` node supplies the key's description; the values are the `dimension` nodes named `<key>.<value>` with a single-segment value (the dotted name carries the axis-to-value relationship, `spec-grid-dimension.md`), each with its own description. A value stamped on an entity that has no dictionary node is counted too, with `declared` false and no description, so an undeclared value is visible rather than dropped. A declared value nothing carries is an honest zero.

One row, for the key:

| field | meaning |
| --- | --- |
| `key` | The `dimension_key` input. |
| `description` | The key's `dimension` node description, null when the key has no node. |
| `total` | Entities carrying any value of the key (int). |
| `values` | One item per value, declared values in name order and then undeclared values in name order: `value`, `description` (null when undeclared), `declared` (bool), `count` (int) and `by_type`, a list of `{type, label, count}` ordered by count descending then type. `label` is the entity type's registered name (the model's `verbose_name`), else the type itself. |
| `values_text` | One line per value, `<value>: <description>` (`no description in the dictionary` when undeclared), made from `values` so a card can print it. |
| `breakdown_text` | One line per value, `<value>: none` or `<value>: <n> component(s): <label> <n>, ...`, made from `values`. |

Tombstoned entities and tombstoned dimension nodes contribute nothing (`tap_grid.gryphon.read_scope`); the caller's `db_alias` is used for every query.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-dimension-coverage-1 | Registered From The Manifest | Implemented | The runner is declared in `[searches]` and registered in the search runner registry at plugin load. | `tests/test_dimension_coverage_search.py::TestRegistration` |
| req-compliance-core-dimension-coverage-2 | Envelope Shape | Implemented | The result passes through the search service with the Search's `input_schema` defaults applied, has empty `nodes` and `edges`, and every value in `rows` survives `json.dumps`. | `::TestRegistration::test_a_module_search_runs_through_the_search_service_with_the_schema_defaults` |
| req-compliance-core-dimension-coverage-3 | Counted By Entity Type | Implemented | Each value's count is the number of live entities stamped with it, split by entity type, ordered by count descending then type; the key's total is their sum. | `::TestCounts::test_each_value_is_counted_by_entity_type` |
| req-compliance-core-dimension-coverage-4 | Declared Zero | Implemented | A value with a dictionary node that nothing carries is listed with count 0 and an empty `by_type`. | `::TestCounts::test_a_declared_value_nothing_carries_is_an_honest_zero` |
| req-compliance-core-dimension-coverage-5 | Undeclared Value | Implemented | A stamped value with no dictionary node is counted, marked `declared` false, has a null description and follows the declared values. | `::TestCounts::test_an_undeclared_value_is_counted_and_marked` |
| req-compliance-core-dimension-coverage-6 | Only The Key | Implemented | An entity with no value for the key, and an entity stamped under another key, are not counted; another key's dictionary nodes are not read. | `::TestCounts::test_another_key_and_unstamped_entities_do_not_count` |
| req-compliance-core-dimension-coverage-7 | Read Scope | Implemented | A tombstoned entity contributes nothing. | `::TestCounts::test_a_tombstoned_entity_contributes_nothing` |
| req-compliance-core-dimension-coverage-8 | Exclusions From Input | Implemented | Entity types in `exclude_types` are not counted; with none given nothing is excluded; no type name is hardcoded. | `::TestCounts::test_exclude_types_are_not_counted_and_nothing_is_excluded_by_default` |
| req-compliance-core-dimension-coverage-9 | Key Without A Node | Implemented | A key with no dimension node answers one row with a null description, no values and total 0. | `::TestCounts::test_a_key_with_no_dimension_node_still_answers` |
| req-compliance-core-dimension-coverage-10 | Display Strings | Implemented | `values_text` and `breakdown_text` are derived from `values`, one line per value in the same order. | `::TestText` |
| req-compliance-core-dimension-coverage-11 | Input Validated | Implemented | A missing, blank or non-string `dimension_key` and an `exclude_types` that is not an array of strings are refused with a `ValueError` naming the input. | `::TestInputs` |

### Dimension Mapping Searches
----
RID: `req-compliance-core-dimension-mapping`

Status: `Implemented`

`dimension-coverage` (`req-compliance-core-dimension-coverage`) answers "which entities carry each value of this key". It cannot say which entities *should* carry one, so it cannot count the ones that are missing it, and it cannot say that a value is wrong for the kind of thing that carries it. Coverage work needs both. A mapping says, for an entity type or a group of entity types, which dimension keys it should carry and which values are acceptable; the two runners here compare the grid against that mapping and put every live entity of a mapped type into one of three states.

**The mapping is data in a Search, not a new node type.** A `Search` is already a first-class grid entity with history (`tap_grid/models.py`, `Search(BaseModel)`), a panel points at it with `USES_SEARCH`, and a module runner receives the Search's `input_schema` defaults as its inputs (`req-compliance-core-dimension-coverage`). So the mapping is the `mappings` input of a Search node: it is versioned with the node, it is the thing a page points at, and compliance_core needs no model and no migration for it. A dedicated mapping node can replace the input later without changing the states or the output below.

Like `findings-reached-count` and `findings-reached-list`, the work is two runners over one comparison, because a panel binds one row shape per Search: `dimension-mapping-summary` returns one row per mapping row, and `dimension-mapping-entities` returns one row per entity. Both are `module` Search runners (`req-grid-search-module`), in `tap_plugin/compliance_core/searches/dimension_mapping.py`, registered in the manifest `[searches]` table and under the read rules Gryphon applies (`tap_grid.gryphon.read_scope`: a tombstoned entity contributes nothing; the caller's `db_alias` for every query). Gryphon cannot write the query for the reason `dimension-coverage` records: it needs a count grouped by a dimension value taken from a Search input.

#### Implementation

The runners know no entity type, dimension key or value. Their inputs come from the Search's `input_schema` defaults:

| input | meaning |
| --- | --- |
| `mappings` | Required. A non-empty array of at most 50 mapping rows, below. |
| `status` | `dimension-mapping-entities` only. Optional; one of `mapped`, `unmapped`, `mapped_incorrectly`. When set, only entities in that state are returned. |
| `max_entities` | `dimension-mapping-entities` only. Optional integer, default `1000`, at most `5000`. The most entity rows returned. |
| `group_by` | Optional. A dimension key of at most 128 characters, such as `inventory`. When set, both runners work in grouped mode, below. |
| `exclude_groups` | Optional, grouped mode only. An array of at most 50 group values (strings of at most 128 characters) left out of the result: no row, no count, no warning. For a group the measure does not apply to. |

A mapping row:

| field | meaning |
| --- | --- |
| `entity_type` | The `entity_type` of the entities that should carry the keys (non-empty string). Exactly one of `entity_type` and `entity_types` is given. |
| `entity_types` | A group: a non-empty array of at most 50 entity types, each a non-empty string of at most 128 characters, that share these keys. The entry `*` matches every entity type that no other row names (grouped mode, below). `entity_type: X` is the same as `entity_types: [X]`. Ruled by George, 2026-10-21: a group is a plain list of exact types. |
| `label` | Optional text of at most 128 characters naming the group in the summary row. Default: the registered name of the single type, else the types joined by `, `. |
| `keys` | A non-empty array of at most 20 `{key, allowed}`: `key` is a dimension key such as `dataclass.action`; `allowed` is a non-empty array of at most 100 strings of at most 256 characters, the values this row accepts for it, or is omitted, which accepts any value that is present and not `null` (a key that must merely be set, such as the team that answers for an entity). An `entity_type` and a `key` are at most 128 characters. |
| `match` | Optional, `any` or `all`, default `all`. `any`: carrying one listed key correctly is enough (a flow carries `dataclass.customer` or `dataclass.infra`). `all`: every listed key must be carried correctly. With one key the two are the same. |

The states, for one live entity of the row's `entity_type`, where a key is *present* when the entity's `dimensions` map has it with a value that is not `null` (a `null` value is unobserved and counts as absent) and *correct* when it is present with a value in that key's `allowed` list:

- `mapped`: with `match: any`, at least one listed key is correct; with `match: all`, every listed key is correct.
- `mapped_incorrectly`: the entity is not `mapped` and at least one listed key is present with a value that is not allowed.
- `unmapped`: neither of the above. With `any`, no listed key is present; with `all`, at least one listed key is absent and none holds a disallowed value.

The denominator of a row is every live entity of its `entity_type`. A value is compared exactly: no case folding, no prefix, no dotted-path rule. A stored value that is neither a string nor `null` is never allowed. An entity that matches two rows is counted in each, and is listed once per row by the entities runner with the row's `mapping` index; rows do not interact. `null` is unobserved and, like an absent key, is unmapped, as everywhere on the grid; a value that says "this does nothing with data" is a real value in the dictionary (for example `dataclass.action = none`) and an allowed value like any other.

`dimension-mapping-summary` returns one row per mapping row, in input order: `entity_type`, `label` (the type's registered name, else the type, as in `dimension-coverage`), `keys_text` (`<key>: <allowed values joined by ", ">` per key, one line each), `match`, `denominator`, `mapped`, `unmapped`, `mapped_incorrectly` and `percent_mapped` (`mapped` over `denominator` as a number from 0 to 100 with one decimal, `null` when the denominator is 0). The three counts add up to the denominator.

`dimension-mapping-entities` returns one row per entity **per mapping row**: `mapping` (the zero-based index of the mapping row in input order), `entity_id`, `entity_type`, `label`, `name`, `status`, `found` (an object of the listed keys the entity carries and their values), `found_text` (`<key> = <value>` per line, `not set` for none) and `allowed_text` (the row's `keys_text`). Order: `mapped_incorrectly`, then `unmapped`, then `mapped`; within a state by entity type, then name, then `entity_id`, then `mapping`. The `status` filter applies to each row's own state, so an entity that is `mapped` under one mapping row and `unmapped` under another appears once in each result. When more entities match than `max_entities`, the first `max_entities` in that order are returned and `warnings` says how many were left out; the summary is never truncated.

An allowed value with no dimension node `<key>.<value>`, and a key with no dimension node, are reported in `warnings` by key and value; they do not fail the run and do not change any state. The dictionary is read the way `dimension-coverage` reads it, and the two share that read.

**Grouped mode.** Without `group_by` everything above holds unchanged. With `group_by` set to a dimension key, the population is every live entity that carries that key with a value that is not `null`, whatever its type, and each entity falls into the group named by its value (for the `inventory` key, its inventory category). An entity is judged by exactly one mapping row: the first row, in input order, whose `entity_type` or `entity_types` names its type exactly, else the first row that names `*`. An entity of a type no row names has no rule, and it is `unmapped` and counted in `no_rule` as well: a type nobody wrote a rule for is a gap to show, not an entity to leave out. (Ruled by George, 2026-10-21: never evaluate an unmarked thing as fine.)

In grouped mode `dimension-mapping-summary` returns one row per value of the `group_by` key, not one per mapping row: first the values the dimension dictionary declares (`<key>.<value>` nodes, as `dimension-coverage` reads them) in name order, then any other value found, in name order. A declared value with no entities is listed with `denominator` 0 and a `null` `percent_mapped`. Each row has `group` (the value), `label` (the value's dictionary description up to its first colon, with a trailing full stop removed, so a description that begins with the display name gives that name; else the value), `denominator`, `mapped`, `unmapped`, `mapped_incorrectly`, `no_rule` (the part of `unmapped` that had no rule) and `percent_mapped`. `warnings` lists the entity types that had no rule, with their counts. `dimension-mapping-entities` in grouped mode returns one row per entity (not per mapping row), with `group`, `mapping` (the index of the judging row, `null` for no rule), `entity_id`, `entity_type`, `label`, `name`, `status`, `found`, `found_text` and `allowed_text` (`no rule` when there is none), ordered as before.

#### Development

The state names are the three the owner asked for ("mapped, unmapped, mapped incorrectly"). `mapped_incorrectly` is kept apart from `unmapped` because they are different problems: a missing tag is work not done, a wrong tag is work done wrongly, and an auditor asks about each. The mapping is not a count of what exists, so a type with nothing on the grid reports a zero denominator and a null percentage, not 100%.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-dimension-mapping-1 | Registered From The Manifest | Implemented | Both runners are declared in `[searches]` and registered in the search runner registry at plugin load. | |
| req-compliance-core-dimension-mapping-2 | Envelope Shape | Implemented | Each result passes through the search service with the Search's `input_schema` defaults applied, has empty `nodes` and `edges`, and every value in `rows` survives `json.dumps`. | |
| req-compliance-core-dimension-mapping-3 | Mapping Comes From The Input | Implemented | No entity type, dimension key or value is named in the runner code; the mapping is read from `mappings` alone. | |
| req-compliance-core-dimension-mapping-4 | Mapping Validated | Implemented | A missing or empty `mappings`, a row with neither `entity_type` nor `entity_types` or with both, an `entity_types` that is empty, over 50 entries or holds a non-string, a `label` over 128 characters, a `group_by` that is not a non-empty string of at most 128 characters, a row with no `keys`, a key without `key` or with an `allowed` that is present and empty, a `match` other than `any` or `all`, more than 50 mapping rows, more than 20 keys in a row or more than 100 allowed values for a key, an entity type or key over 128 characters or an allowed value over 256, a `status` other than the three states, and a `max_entities` that is not an integer from 1 to 5000 are refused with a `ValueError` naming the input. | |
| req-compliance-core-dimension-mapping-5 | Denominator Is Live Entities Of The Type | Implemented | Without `group_by`, a row's denominator is the count of live entities whose `entity_type` is one the row names; a tombstoned entity contributes nothing and an entity of another type is not counted. | |
| req-compliance-core-dimension-mapping-6 | Match All | Implemented | With `match: all`, an entity is `mapped` only when every listed key is present with an allowed value, `mapped_incorrectly` when it is not mapped and some listed key holds a disallowed value, and `unmapped` otherwise. | |
| req-compliance-core-dimension-mapping-7 | Match Any | Implemented | With `match: any`, an entity is `mapped` when at least one listed key holds an allowed value, `mapped_incorrectly` when it is not mapped and some listed key holds a disallowed value, and `unmapped` when no listed key is present. | |
| req-compliance-core-dimension-mapping-8 | Exact Match, Strings Only | Implemented | A value is allowed only when it equals an `allowed` string exactly; a prefix, a different case and a stored value that is not a string are not allowed; a `null` value is absent, so it reads unmapped and never mapped incorrectly. | |
| req-compliance-core-dimension-mapping-9 | Counts Add Up | Implemented | For every summary row, `mapped + unmapped + mapped_incorrectly` equals `denominator`, and `percent_mapped` is `mapped` over `denominator` as a number from 0 to 100 with one decimal. | |
| req-compliance-core-dimension-mapping-10 | Empty Type Is Honest | Implemented | A row whose type has no live entities is listed with `denominator` 0, all three counts 0 and a `null` `percent_mapped`. | |
| req-compliance-core-dimension-mapping-11 | Rows Are Independent | Implemented | Two mapping rows for the same type, or two rows naming the same key, are counted separately and an entity can be in both; the entities runner lists it once per row with that row's `mapping` index. | |
| req-compliance-core-dimension-mapping-12 | Entity Rows | Implemented | `dimension-mapping-entities` returns one row per entity of a mapped type per mapping row, with `mapping`, `entity_id`, `entity_type`, `label`, `name`, `status`, `found`, `found_text` and `allowed_text`, ordered `mapped_incorrectly`, `unmapped`, `mapped`, then type, name, `entity_id` and `mapping`. | Overlapping rows are listed once each, so no row is ambiguous (review of this PR). |
| req-compliance-core-dimension-mapping-13 | Status Filter | Implemented | With the `status` input set, only entities in that state are returned; with it unset all three states are. | One Search per state gives a page its three tables. |
| req-compliance-core-dimension-mapping-14 | Bounded Entity Rows | Implemented | No more than `max_entities` rows are returned, the omitted number is in `warnings`, and the summary counts are unaffected. | |
| req-compliance-core-dimension-mapping-15 | Undeclared Names Warn | Implemented | An allowed value with no `<key>.<value>` dimension node and a key with no dimension node are listed in `warnings` and do not fail the run or change a state. | |
| req-compliance-core-dimension-mapping-16 | A Group Is A List Of Types | Implemented | A row with `entity_types` judges every live entity whose type is in the list under that row's keys, and its summary row (without `group_by`) counts them together with the row's `label`. | Ruled by George, 2026-10-21. |
| req-compliance-core-dimension-mapping-17 | Any Present Value | Implemented | A key with no `allowed` is correct when the entity's value for it is present and not `null`; it is never `mapped_incorrectly`, because no value is disallowed. | For "has a responsible team" the allowed values are team ids, which cannot be listed. |
| req-compliance-core-dimension-mapping-18 | Grouped Population | Implemented | With `group_by`, the population is every live entity carrying that key with a non-null value, of any type, grouped by the value; a tombstoned entity contributes nothing. | |
| req-compliance-core-dimension-mapping-19 | One Judging Row | Implemented | In grouped mode an entity is judged by the first row naming its type exactly, else the first row naming `*`, and by no other row; it is counted once. | |
| req-compliance-core-dimension-mapping-20 | No Rule Is A Gap | Implemented | In grouped mode an entity of a type no row names is `unmapped` and counted in `no_rule`; `warnings` lists those types with their counts. | |
| req-compliance-core-dimension-mapping-21 | Every Declared Group Is Listed | Implemented | The grouped summary lists every value the dimension dictionary declares for the key, in name order, then other values found in name order; a group with no entities has `denominator` 0 and `percent_mapped` `null`. | The nine inventory categories always appear. |
| req-compliance-core-dimension-mapping-22 | Grouped Counts Add Up | Implemented | For every grouped summary row, `mapped + unmapped + mapped_incorrectly` equals `denominator`, `no_rule` is at most `unmapped`, and `percent_mapped` is `mapped` over `denominator` with one decimal. | |
| req-compliance-core-dimension-mapping-23 | Grouped Entity Rows | Implemented | `dimension-mapping-entities` with `group_by` returns one row per entity with `group` and `mapping` (`null` for no rule), honours `status` and `max_entities`, and reports the omitted number in `warnings`. | |
| req-compliance-core-dimension-mapping-24 | Excluded Groups Are Left Out | Implemented | A group value named in `exclude_groups` has no summary row, no entity row and no count anywhere in the result; an `exclude_groups` that is not an array of at most 50 strings of at most 128 characters, or that is set without `group_by`, is refused with a `ValueError` naming the input. | The Search's description says which group it leaves out and why, so the omission is visible. |

#### Future

- **Stored reports over time.** The summary is snapshotted by `SearchSnapshotCollector` (`req-compliance-core-search-snapshot-collector`) and read back as a series by `search-snapshot-series` (`req-compliance-core-search-snapshot-series`).
- **Exemptions.** Removing an entity from a denominator by an approved exception follows the exception model (`req-compliance-core-exception`); it is not specified here.
- **A dedicated mapping node.** If mappings need their own identity, review or rows that other things point at, a node can replace the `mappings` input.
- **A "does nothing" value on other axes.** `dataclass.action = none` is defined with its vocabulary; whether the customer and infra axes get one is open.



### Dimension Mapping Totals
----
RID: `req-compliance-core-dimension-mapping-totals`

Status: `Implemented`

A coverage card shows a few figures about a whole grouped summary: how covered the categories are on average, and how many entries are mapped, unmapped and mapped incorrectly. A card reads one row of one Search, and the grouped summary returns one row per group, so the figures need a row of their own. They are also wanted in more than one place (a card on a page, a card on the overview, a consolidated coverage panel that gathers them), so the calculation lives here once and any panel or runner reuses it. Ruled by George, 2026-10-21: the cards are live, plain-average, standalone and pluggable anywhere.

#### Implementation

**The calculation.** A Django-free module `tap_plugin/compliance_core/coverage.py` holds two pure functions. `plain_mean(values)` returns the unweighted mean of the numbers in `values` to one decimal, ignoring `None` and non-numbers, and `None` when none remain: it is the one place a coverage average is computed, and `search-snapshot-series` (`req-compliance-core-search-snapshot-series`) uses it for its `Overall` line, so a card and the chart always agree. `totals_from_rows(rows)` takes the rows of a grouped summary (`req-compliance-core-dimension-mapping`) and returns the totals below. Both are importable by any other runner or panel.

**The runner.** `dimension-mapping-totals` is a `module` Search runner in `tap_plugin/compliance_core/searches/dimension_mapping_totals.py`, registered in the manifest `[searches]` table, under the read rules Gryphon applies (`tap_grid.gryphon.read_scope`). It writes nothing. It runs the grouped summary live, every time it is called: no snapshot is read. Input:

| input | meaning |
| --- | --- |
| `summary_search_id` | Required. The entity id of a `search` node whose runner is `dimension-mapping-summary`. The runner reads that Search's `input_schema` defaults (`mappings`, `group_by`, `exclude_groups`) and runs the summary with them, so the mapping is stated once, in the summary Search, and the totals can never differ from it. |

It returns exactly one row:

| field | meaning |
| --- | --- |
| `groups` | The number of groups that have a `percent_mapped` (a group with no entities has none). |
| `percent_overall` | `plain_mean` of the groups' `percent_mapped`, one decimal; `null` when no group has one. |
| `denominator`, `mapped`, `unmapped`, `mapped_incorrectly`, `no_rule` | The sums over every group. |
| `percent_pooled` | `mapped` over `denominator`, one decimal; `null` when `denominator` is 0. |

`percent_overall` is the plain average the chart's `Overall` line shows (George, 2026-10-21); `percent_pooled` is given beside it and is not the headline, because a category with many entries (the 180 packages) would dominate it. A card for "entries without a team" shows `unmapped`; "with a team" shows `mapped`; "entries" shows `denominator`.

An id that is not a `search` node, or whose runner is not `dimension-mapping-summary`, or a Search whose defaults are invalid, is refused with a `ValueError` naming the input. A summary Search that excludes groups gives totals over the groups it returns.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-dimension-mapping-totals-1 | Registered From The Manifest | Implemented | The runner is declared in `[searches]` and registered in the search runner registry at plugin load. | |
| req-compliance-core-dimension-mapping-totals-2 | One Row | Implemented | The runner returns exactly one row with `groups`, `percent_overall`, `denominator`, `mapped`, `unmapped`, `mapped_incorrectly`, `no_rule` and `percent_pooled`, and every value survives `json.dumps`. | |
| req-compliance-core-dimension-mapping-totals-3 | Plain Average | Implemented | `percent_overall` equals the unweighted mean of the groups' `percent_mapped` to one decimal; a group with a `null` percent is not in the mean and not in `groups`. | |
| req-compliance-core-dimension-mapping-totals-4 | Sums Add Up | Implemented | `mapped + unmapped + mapped_incorrectly` equals `denominator`, `no_rule` is at most `unmapped`, and `percent_pooled` is `mapped` over `denominator` with one decimal, `null` at 0. | |
| req-compliance-core-dimension-mapping-totals-5 | Mapping Stated Once | Implemented | The runner takes its `mappings`, `group_by` and `exclude_groups` from the named summary Search's `input_schema` defaults and holds none of its own; changing the summary Search changes the totals with no other edit. | |
| req-compliance-core-dimension-mapping-totals-6 | One Mean | Implemented | `plain_mean` is the only place a coverage average is computed: `search-snapshot-series` and this runner both call it, and a test fails if either rounds a mean itself. | A card and the chart's `Overall` always agree. |
| req-compliance-core-dimension-mapping-totals-7 | Reusable And Django-Free | Implemented | `coverage.py` imports no Django module and its two functions are importable by another runner or panel. | Import-blocked test. |
| req-compliance-core-dimension-mapping-totals-8 | Live, Never A Snapshot | Implemented | A run reads the grid at call time and reads no `compliance_search_snapshot`. | |
| req-compliance-core-dimension-mapping-totals-9 | Bad Input Refused | Implemented | A missing or non-string `summary_search_id`, an id that is not a `search`, and a Search whose runner is not `dimension-mapping-summary` are refused with a `ValueError` naming the input. | |

### Dimension Mapping Totals Set
----
RID: `req-compliance-core-dimension-mapping-totals-set`

Status: `Implemented`

A stat-card panel binds one Search and draws one card per row, so a panel showing two coverages side by side (for example Responsibility and Data Classification) needs one row per coverage. `dimension-mapping-totals-set` returns those rows. It adds no arithmetic: each summary's figures are exactly what `dimension-mapping-totals` returns for it (`coverage.totals_from_rows`).

#### Implementation

`dimension-mapping-totals-set` is a `module` Search runner in `tap_plugin/compliance_core/searches/dimension_mapping_totals.py`, registered in the manifest `[searches]` table, under the same read rules and caller `db_alias` as `dimension-mapping-totals`. It writes nothing. Input:

| input | meaning |
| --- | --- |
| `summaries` | Required. A non-empty array of `{key, label, summary_search_id}`. `key` matches `^[a-z][a-z0-9_]*$` and is unique in the array; `label` is optional, a non-empty string defaulting to `key`; `summary_search_id` is as for `dimension-mapping-totals`. |

It returns one row per summary, in array order: `key`, `label`, `groups`, `percent_overall`, `denominator`, `mapped`, `unmapped`, `mapped_incorrectly`, `no_rule`, `percent_pooled` and `percent_text` (`percent_overall` to one decimal with a `%`, null when there is none), and no other field. `warnings` is the summaries' own warnings, concatenated in array order. An empty or non-array `summaries`, a bad or repeated `key`, a bad `label`, and any `summary_search_id` refused by `dimension-mapping-totals` are refused with a `ValueError` naming the input.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-dimension-mapping-totals-set-1 | Registered From The Manifest | Implemented | The runner is declared in `[searches]` and registered in the search runner registry at plugin load. | |
| req-compliance-core-dimension-mapping-totals-set-2 | One Row Per Summary | Implemented | The runner returns one row per summary in array order, each with `key`, `label` (default the key), the eight totals fields and `percent_text` (`percent_overall` to one decimal with a `%`, null when there is none), and the totals fields equal what `dimension-mapping-totals` returns for that summary. | |
| req-compliance-core-dimension-mapping-totals-set-3 | Warnings Merged | Implemented | `warnings` is each summary's own warnings, concatenated in array order. | |
| req-compliance-core-dimension-mapping-totals-set-4 | Bad Input Refused | Implemented | An empty or non-array `summaries`, a `key` not matching `^[a-z][a-z0-9_]*$`, a repeated `key`, a `label` that is not a non-empty string, and a `summary_search_id` that is not a dimension-mapping-summary search are refused with a `ValueError`. | |

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

Status: `Implemented`

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
| req-compliance-core-exception-1 | New Fields Are Nullable | Implemented | An exception created with only a `name`, as every current producer does, is accepted and reads back with the seven new fields null. | Backward compatibility with `fedramp_20x_ksi`'s minted exceptions. |
| req-compliance-core-exception-2 | Kind And Justification Are Closed | Implemented | A `kind` outside the five, a `justification` outside the five labels, and a `justification` on any `kind` but `not-affected` are refused. | Vocabulary drawn from GitHub's dismissal reasons, OpenVEX and the FedRAMP deviation types. |
| req-compliance-core-exception-3 | Verify Window Is A Positive Integer | Implemented | `verify_within_hours` accepts an integer of at least 1 or null; zero, negatives and non-integers are refused. | |
| req-compliance-core-exception-4 | Containment Declared | Implemented | `CONTAINMENT_EDGES` names `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE` and that edge is a permitted outbound edge of the model. | The class-creation guard in `tap_grid/models.py`. |
| req-compliance-core-exception-5 | Identity Unchanged | Implemented | The natural key stays `("source", "source_key")`; re-sending an exception under the same key is the same node. | `req-compliance-core-identity`. |
| req-compliance-core-exception-6 | Additive Migration | Implemented | The schema migration adds the columns and changes no existing row. | |

### Exception Instance Modeling
----
RID: `req-compliance-core-exception-instance`

Status: `Implemented`

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
| req-compliance-core-exception-instance-1 | The Node Exists With A Key And A Dimension | Implemented | The entity type is `compliance_core__compliance_exception_instance`, it keys on `("source", "source_key")`, and a new instance carries `compliance: exception-instance`. | |
| req-compliance-core-exception-instance-2 | Outcome Has Three States | Implemented | `outcome` accepts `held`, `falsified` or null; any other string is refused; null reads back as null, never as an empty string. | Null is unobserved (the grid's null convention). |
| req-compliance-core-exception-instance-3 | Anchor Count Is Required | Implemented | An instance created without `anchor_count`, or with a value below 1, is refused. | A scope of zero anchors would be a blanket approval. |
| req-compliance-core-exception-instance-4 | Same Key Is The Same Node | Implemented | Re-sending an instance with the same `(source, source_key)` updates it; the producer re-sends every field it owns. | A GRIFT node under an existing key replaces the row and nulls omitted fields (Issue# 1071 - tap), so a partial re-send would erase `outcome`. |
| req-compliance-core-exception-instance-5 | Wrong Ends Refused | Implemented | An edge at an instance in the wrong direction or to the wrong type is refused wherever a closed end forbids it. | Edge validation is a permission union (`tap_grid/constraints.py`): an end whose type declares no edges allows everything, so an edge from or to such a type (a finding or evidence node) is not refused by the instance's declaration alone. Found building PR A. |
| req-compliance-core-exception-instance-6 | Recording Check Time Without A New Version Each Run | Backlog | `verified_at` changes on every successful check. The grid treats re-observation as not a change, so the design needs either that rule to admit a check-time field or the freshness to be derived from the latest scan run that scanned the instance. | Open: Issue# 322 - tap and Issue# 323 - tap. v0 stores the field; the derived form is the alternative. |

### Exception Edges
----
RID: `req-compliance-core-exception-edges`

Status: `In Development`

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

**`COVERS_COMPLIANCE_FINDING` moves to the instance.** The instance, not the exception, is what is bound to a specific finding, and the binding is what a checker asserts or lets lapse. Live rows of the old shape (an exception as source) are retired by a data migration, kept apart from the schema migration, as `0003` retired two renamed edges; ids derive from the slug so the next collection re-emits what is still true. Consumers that read the old shape retarget in their own repositories: `fedramp_20x_ksi`'s finding-profile spec describes an exception banner that reads this edge from an exception (`specs/spec-fedramp-20x-ksi-finding-profile.md`, the exception coverage panel line) and its instance-findings spec says the open-findings counter reads it. A search on 2026-10-20 of the local plugin checkouts (`fedramp_20x_ksi`, `rampart_20x`, `rampart_20x_playground`, `github_core`, `computing_core`, `aws_core`) for `COVERS_COMPLIANCE_FINDING` found it in three `fedramp_20x_ksi` specs and in no Python, JSON or HTML there, so no runtime reader turned up in those checkouts; other repositories (`samsite`, for one) were not searched, and the checkouts may be older than their remotes. **Release gate:** the data migration that retires the old rows is not released until the consumers named here are retargeted or shown to have no reader, so existing coverage data is never lost to ordering. Status 2026-10-21: the two `fedramp_20x_ksi` spec lines are retargeted to the instance and the coverage Search (`fedramp-20x-ksi-tap#30`), and a GitHub code search of the `unified-systems-com` and `CriticalSecLLC` organisations found the edge name in no runtime code outside this plugin (`samsite-tap` mentions it in a wishlist document only); the search index can lag, so this is a search result and not a proof.

**Edges carry no cardinality**, so "one vulnerability, at least one anchor" cannot be refused at write. A producer keeps to it, and coverage treats an instance that breaks it as covering nothing.

**Dimensions.** The edges follow the target's type marker as the existing ones do: `exception-instance`, `vulnerability`, `exception-instance` (the wildcard takes its source's family), `finding`. Every edge declares the plain identity `{"discriminators": []}`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-exception-edges-1 | The Sentences Connect | Implemented | Each edge in the table connects its endpoints and carries the dimension above. | |
| req-compliance-core-exception-edges-2 | Containment Is Only The Grant | Implemented | `GRANTS_COMPLIANCE_EXCEPTION_INSTANCE` is the only edge in `CONTAINMENT_EDGES`; deleting an exception with `cascade="contained"` retires its instances, and deleting an instance leaves the exception, finding, vulnerability and anchors live. | `req-grid-service-delete-cascade`. |
| req-compliance-core-exception-edges-3 | An Anchor May Be Any Node | Implemented | `SCOPED_TO_COMPLIANCE_EXCEPTION_TARGET` accepts any node as its target from an instance, and refuses a source whose own type forbids it (an exception, a vulnerability). | A source type that declares no outbound edges (a finding) is not refused: the same permission union. A producer keeps to instances as the source. |
| req-compliance-core-exception-edges-4 | Covers Moves To The Instance | Implemented | `COVERS_COMPLIANCE_FINDING` accepts an instance as its source and refuses an exception; `CITES_COMPLIANCE_EVIDENCE` accepts an instance or a finding as its source. | |
| req-compliance-core-exception-edges-5 | Old Covers Rows Retired | Implemented | A data migration, separate from the schema migration, retires live `COVERS_COMPLIANCE_FINDING` rows whose source is an exception and touches no other row. | Migration `0011_retire_exception_covers_rows`; precedent `0003`. Released only after the consumers were retargeted or shown to have no reader (see above). |
| req-compliance-core-exception-edges-6 | Plain Identity | Implemented | Every new edge declares `{"discriminators": []}`, so a re-sent edge is the same edge. | Tested as the declaration; edges carry no natural key through the service layer today (ids are assigned), so re-sending through `create_edge` makes a second edge, and the same-edge guarantee is the importer's (Issue# 458 - tap). |
| req-compliance-core-exception-edges-7 | Anchors Reach The Finding | Backlog | A check that each anchor actually reaches the covered finding along carries or path edges, as the reach runners follow them. | v0 relies on the checker's binding and on the vulnerability match; the topology of who carries a finding is set by the producers, so the path declarations need a design of their own. |

### Exception Coverage
----
RID: `req-compliance-core-exception-coverage`

Status: `Implemented`

Whether a finding is covered is a question the grid answers when asked, from facts, and never a flag written onto the finding or the exception. Storing it would need undoing in every path that can end it (DefectDojo reverses `active` and `risk_accepted` in four code paths and has to decide whether the clock restarts); computing it ends coverage by the absence of a fact and needs nothing undone.

An instance covers a finding only when **every** one of these holds, tested against `as_of` (default: now):

1. A live `COVERS_COMPLIANCE_FINDING` edge runs from the instance to the finding.
2. The finding's `status` is `open`.
3. The finding concerns the one vulnerability the instance exempts.
4. The instance's `outcome` is `held`.
5. `verified_at` is not null, is not after `as_of`, and is no older than the exception's `verify_within_hours`, which must itself be set. A check time in the future proves nothing yet and would keep the instance fresh past its window, so it counts as unverified.
6. The exception that grants the instance is live, has a `kind`, has `status` `active`, has a `granted_at` that is not after `as_of`, and has no `expires_at` or one after `as_of`. A null or future grant time means the decision has not yet been made, so nothing is covered by it.
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
| req-compliance-core-exception-coverage-1 | Registered From The Manifest | Implemented | Both runners are declared in `[searches]` and registered at plugin load, and their results pass through the search service with the schema defaults applied. | As `req-compliance-core-reach-1`. |
| req-compliance-core-exception-coverage-2 | All Eight Conditions Are Required | Implemented | A finding with an instance satisfying all eight reads `covered` true; making any one fail, one at a time, reads false with that condition in `reason`. | One test per condition. |
| req-compliance-core-exception-coverage-3 | Unset Is Uncovered | Implemented | A null `outcome`, null `verified_at`, null `verify_within_hours`, null `kind` and an instance with no vulnerability or no anchor each read uncovered. | |
| req-compliance-core-exception-coverage-4 | Stale Is Uncovered | Implemented | An instance verified longer ago than `verify_within_hours` before `as_of` reads uncovered, and one verified inside the window reads covered. | |
| req-compliance-core-exception-coverage-10 | A Future Check Time Is Unverified | Implemented | An instance whose `verified_at` is after `as_of` reads uncovered, whatever `verify_within_hours` is; one verified a year after `as_of` does not read covered. | Found in review of the draft; a mistaken or hostile future timestamp must not keep coverage fresh. |
| req-compliance-core-exception-coverage-11 | Anchor Reachability Is A Trust Boundary | Backlog | Coverage does not check that a live anchor reaches the covered finding; the checker's binding is trusted. Building that check is `req-compliance-core-exception-edges-7`. | Recorded so no one reads the anchor rule as stronger than it is. No test asserts the unreached case reads covered: that would pin a fail-open as expected. Open for the maintainer: make reachability a coverage condition in v0 instead. |
| req-compliance-core-exception-coverage-12 | Coverage Does Not Begin Before The Grant | Implemented | An exception whose `granted_at` is null, or after `as_of`, covers nothing; one granted at or before `as_of`, with every other condition met, can cover. | Found in review: a null or future grant time must not let an exception cover a current finding. |
| req-compliance-core-exception-coverage-5 | Expiry Is Computed | Implemented | An exception whose stored `status` is `active` but whose `expires_at` is before `as_of` covers nothing. | |
| req-compliance-core-exception-coverage-6 | A Lost Anchor Never Widens The Scope | Implemented | Retiring one of two anchors makes the instance uncovered; it does not become the general case. | |
| req-compliance-core-exception-coverage-7 | Any Covering Instance Is Enough | Implemented | A finding with one failing and one covering instance reads covered; with two failing instances it reads uncovered with the reason of the closer. | |
| req-compliance-core-exception-coverage-8 | Review Due | Implemented | `exceptions-due-review` lists an exception past `review_by`, one with no `review_by`, one past `expires_at` and one with no `verify_within_hours`, and omits one with none of these. | |
| req-compliance-core-exception-coverage-9 | Read Scope And Input Validation | Implemented | A tombstoned instance, exception, finding or edge contributes nothing; a malformed `as_of`, a non-string `entity_id` or an out-of-range `max_results` is refused with a `ValueError` naming the input. | As `req-compliance-core-reach-5` and `-9`. |

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

### Search Snapshot Modeling
----
RID: `req-compliance-core-search-snapshot`

Status: `Implemented`

Coverage and compliance questions ("how much of the inventory is classified?") have an answer today and a different answer next week, and the trend is the evidence. The grid's history records a node's changes only, and a re-observation of an unchanged value is not a change (tap#322), so a figure that sat still for a week would leave no entries to read it back from, and an edge cannot point at a history row. A snapshot is therefore a node: a run of one Search, with the rows it returned held inside, written once and never updated. (Ruled by George 2026-10-20: results inside the node; the node and its edge are named `compliance_search_snapshot` and `CAPTURES_SEARCH`.)

The node says nothing about what the Search measures. A coverage Search, a count by severity and an inventory total are all snapshotted the same way, so the node lives here beside the other regime-neutral compliance types.

#### Implementation

`compliance_core__compliance_search_snapshot`, a `BaseModel` modelled on `compliance_scan_run`.

| field | type | meaning |
| --- | --- | --- |
| `name` | string, required | Display text: `<search_name> @ <observed_at>`. |
| `source` | string, at most 64 | The plugin slug of the collector that wrote it. Half the identity. |
| `snapshot_key` | string, 1 to 512 | `<search entity id>@<observed_at as UTC ISO 8601 to the microsecond>`. Half the identity. |
| `search_name` | string | The Search's name when it ran. The edge names the Search; the name here keeps the snapshot readable after a rename. |
| `observed_at` | date-time, required, never null | When the Search ran. A figure with no time is not a time series. |
| `row_count` | integer, at least 0, required | The number of rows the Search returned, exact. |
| `rows` | array, required | The rows, at most 1000: each a JSON object of at most 50 properties, with names of at most 128 characters, whose values are strings of at most 4096 characters, numbers, booleans or null. Empty when the Search returned none. |
| `truncated` | boolean, required | True when `rows` holds fewer rows than `row_count`. |
| `inputs_text` | string, at most 65536, required | The Search's inputs for the run as canonical JSON text (keys sorted, no spaces), so a later reader can see what mapping or filter produced the rows even after the Search is edited. |

`NATURAL_KEY` is `("source", "snapshot_key")`. A snapshot is an observation made once, so there is nothing to re-observe: a second run is a second node with a new key, and a node sent again under an existing key would replace the row and null whatever it left out (tap#1071). A collector never reuses a key.

`rows` declares its item schema (an object with scalar-valued properties) rather than a bare `object`, so the content is described and Gryphon's type checks can reach into it as the grid's JSON schemas mature. Gryphon cannot filter inside an array (`req-grid-traversal-lang-filters-jsonpath` is tracked separately), so a report over time reads `rows` through a `module` Search, in the way `dimension-coverage` reads dimensions.

The whole-record check (`BaseModel.validate()`, `req-grid-entity-validation-9`) refuses a node whose `truncated` disagrees with its counts: false requires `len(rows) == row_count`, true requires `len(rows) < row_count`.

`CAPTURES_SEARCH__compliance_core`: `compliance_search_snapshot` → `search`, no properties, default dimension `{"compliance": "search-snapshot"}`. The slug is an action on a noun, so it passes `req-tap-plugin-edge-naming`.

The node carries the default dimension `{"compliance": "search-snapshot"}`. Migrations are numbered when built: one schema migration adds the table; there is no data migration.

#### Development

`rows` is a copy of what the Search returned at one moment, so it is bounded: a thousand rows is a coverage summary or a short list, not an inventory dump. A Search that returns more is truncated, and `row_count` keeps the true size so the loss is visible. Entity-level lists belong to a Search run on demand, not to the snapshot.

**Who can read a snapshot.** A snapshot copies what a Search returned to the collector's actor (`grid.read`) into a node that anyone who can read compliance nodes can read. This spec adds no label propagation, redaction or eligibility check, and the grid's per-node authorization is not verified here, so the audience of a snapshot is the audience of the node, not of the Search it copied. The rule for now is on the subclass author: name only Searches whose rows are suitable for that audience, and put no secret in a Search's input defaults, because `inputs_text` records them. Whether the grid can carry a Search's read restriction onto its snapshots is open (Future).

Snapshots grow without bound at one per Search per run. Retention is deliberately not specified here: at hourly cadence it is 24 nodes per Search per day, which no demo or first deployment will feel, and pruning needs a ruling on what an auditor must be able to read back.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-search-snapshot-1 | Node Declared | Implemented | `compliance_core__compliance_search_snapshot` is a registered `BaseModel` with the fields above, a `FIELD_CRUD_SCHEMA` and a `FIELD_VALIDATION_SCHEMA` for each. | |
| req-compliance-core-search-snapshot-2 | Identity | Implemented | `NATURAL_KEY` is `("source", "snapshot_key")`; two snapshots of one Search at different times coexist and a repeated key is the same node. | |
| req-compliance-core-search-snapshot-3 | Required Fields | Implemented | `source`, `snapshot_key`, `observed_at`, `row_count`, `rows`, `truncated` and `inputs_text` are required; a null `observed_at` is refused. | |
| req-compliance-core-search-snapshot-4 | Rows Are Scalar Objects | Implemented | `rows` accepts at most 1000 items, each an object of at most 50 properties with names of at most 128 characters, whose values are strings of at most 4096 characters, numbers, booleans or null; a list or object value, a longer string, a 51st property, a longer name or a 1001st item, is refused. | Row count, property count and name and value length together bound a node to tens of megabytes at the limits (review of this PR). |
| req-compliance-core-search-snapshot-5 | Truncation Agrees With Counts | Implemented | A node with `truncated` false and `len(rows)` unequal to `row_count`, or with `truncated` true and `len(rows)` not less than `row_count`, is refused by `validate()`. | |
| req-compliance-core-search-snapshot-6 | Edge Declared | Implemented | `CAPTURES_SEARCH__compliance_core` exists from `compliance_search_snapshot` to `search`, with no properties and the `compliance: search-snapshot` dimension, and a snapshot can be linked to a Search node with it. | The test links a real `search` node, because the core `search` type declares no inbound edges of its own. |
| req-compliance-core-search-snapshot-7 | Edge Passes Naming | Implemented | `validate_plugin` accepts the slug under `req-tap-plugin-edge-naming`. | |
| req-compliance-core-search-snapshot-8 | Never Updated Here | Implemented | compliance_core contains no code that patches or replaces an existing snapshot. | |
| req-compliance-core-search-snapshot-9 | Migration Numbered When Built | Implemented | The schema migration takes the next free number at build time; this spec fixes none. | The exceptions spec hard-coded `0006` and was wrong by the time it merged. |

#### Future

A read restriction carried from the Search onto its snapshots, or a check that a Search is eligible to be snapshotted, if the grid offers one. Retention and pruning. A figure derived across snapshots (a trend line, a percent change) is a Search over snapshots, not a field here. Entity-level rows, if an auditor needs to see which entities were uncovered at the time, would be a second node type edged from the snapshot.


### Search Snapshot Series
----
RID: `req-compliance-core-search-snapshot-series`

Status: `Implemented`

A snapshot holds one run of a Search. A line chart needs the opposite shape: one row per point, with a time, a line it belongs to and a value. `search-snapshot-series` is the `module` Search runner that reads the snapshots of one Search back in that shape. It exists because Gryphon cannot filter inside a snapshot's `rows` array (`req-compliance-core-search-snapshot`), and it is generic: it knows no Search, field or metric. Ruled by George, 2026-10-21: this reader lives in `compliance_core`.

#### Implementation

A `module` Search runner, `search-snapshot-series`, in `tap_plugin/compliance_core/searches/snapshot_series.py`, registered in the manifest `[searches]` table, under the read rules Gryphon applies (`tap_grid.gryphon.read_scope`: the caller's `db_alias` for every query). It writes nothing. Inputs, from the Search's `input_schema` defaults:

| input | meaning |
| --- | --- |
| `search_id` | Required. The entity id of the Search whose snapshots are read, the Search a `CAPTURES_SEARCH` edge points at. |
| `series_field` | Required. The name of the row field whose value names the line (for the mapping summary, `group`). |
| `value_field` | Required. The name of the row field that is the point's number (for the mapping summary, `percent_mapped`). |
| `aggregate_label` | Optional string, default `Overall`. The name of the aggregate line. An empty string omits the aggregate. |
| `since` | Optional ISO 8601 date-time. Only snapshots observed at or after it are read. |
| `max_snapshots` | Optional integer, default `720` (thirty days hourly), at most `5000`. The most recent snapshots read. |

One output row per snapshot per series: `observed_at` (UTC ISO 8601 with `Z`, whole seconds), `series` (the string value of `series_field`), `value` (the number in `value_field`) and `aggregate` (false). When `aggregate_label` is set, one more row per snapshot: `series` is the label, `value` is the plain mean of that snapshot's series values, rounded to one decimal, and `aggregate` is true. The aggregate is a plain average of the lines, not weighted by how many entities each line holds (ruled by George, 2026-10-21). Rows are ordered by `observed_at` ascending, then the aggregate last, then `series` by name, so a chart draws the aggregate on top.

A row whose `value_field` is `null` or not a number is not a point and is not part of the mean; a snapshot with no usable value for the aggregate has no aggregate row. A gap is stated and not drawn as 0: `warnings` counts the rows skipped for a missing or non-numeric value, the snapshots that were `truncated`, and, when more snapshots exist than `max_snapshots`, how many older ones were left out.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-search-snapshot-series-1 | Registered From The Manifest | Implemented | The runner is declared in `[searches]` and registered in the search runner registry at plugin load. | |
| req-compliance-core-search-snapshot-series-2 | Names Nothing | Implemented | No Search id, field name or metric is named in the runner code. | |
| req-compliance-core-search-snapshot-series-3 | Inputs Validated | Implemented | A missing or non-string `search_id`, `series_field` or `value_field`, a non-string `aggregate_label`, a `since` that is not an ISO 8601 date-time and a `max_snapshots` that is not an integer from 1 to 5000 are refused with a `ValueError` naming the input. | |
| req-compliance-core-search-snapshot-series-4 | One Row Per Snapshot And Series | Implemented | Each snapshot of the Search yields one row per distinct `series_field` value in its `rows`, with `observed_at`, `series`, `value` and `aggregate` false. | |
| req-compliance-core-search-snapshot-series-5 | Aggregate Is A Plain Mean | Implemented | With a non-empty `aggregate_label`, each snapshot also yields one row whose value is the unweighted mean of that snapshot's series values to one decimal, with `aggregate` true; an empty label yields none. | |
| req-compliance-core-search-snapshot-series-6 | Gaps Are Not Zeros | Implemented | A row with a `null` or non-numeric value yields no point and is left out of the mean, and `warnings` counts the skipped rows. | |
| req-compliance-core-search-snapshot-series-7 | Order Puts The Aggregate On Top | Implemented | Rows are ordered by `observed_at`, then non-aggregate before aggregate, then `series`. | |
| req-compliance-core-search-snapshot-series-8 | Most Recent Snapshots | Implemented | At most `max_snapshots` of the most recent snapshots (after `since`) are read and the number of older ones left out is in `warnings`. | |
| req-compliance-core-search-snapshot-series-9 | Truncated Snapshots Are Flagged | Implemented | A snapshot whose `truncated` is true is read from the rows it holds and counted in `warnings`. | |
| req-compliance-core-search-snapshot-series-10 | Read Only | Implemented | The runner writes no node or edge and contains no code that patches or replaces a snapshot. | |

### Search Snapshot Collector Base
----
RID: `req-compliance-core-search-snapshot-collector`

Status: `Implemented`

An abstract collector class, `SearchSnapshotCollector`, in `tap_plugin/compliance_core/collectors/search_snapshot/collector.py`. A plugin that wants a Search recorded on a schedule writes a subclass of a few lines, registers it, and seeds a `Schedule` for it (`spec-tap-cares-scheduler.md`). The base class does the work: read each Search, run it, build the snapshot, submit one GRIFT batch.

compliance_core registers no collector itself, and the base class is not registered. The class imports `tap_cares.collectors.CollectorBase`; `tap_cares` is core, so this is no dependency above core (`req-compliance-core-deps`). The carve-out from `req-compliance-core-nongoals` is recorded there.

**Why a base class and a subclass, not one configurable collector.** `CollectorConfig` is two ids and nothing else, with no parameters and no scheduler overrides (`req-tap-cares-collector-config-6`), each registry key has one `Collector` node (`req-tap-cares-collector-model-7`), and the registry takes classes, never factories (`req-tap-cares-collector-module-class-1`). So the Searches to run have to be named by the class. The subclass names them by entity id: Searches are keyless and have no unique name, so a name could match two. (Ruled by George 2026-10-20: for the demo the Search is hard-coded in the subclass, in the plugin that owns the report.)

#### Implementation

A subclass declares two class attributes and nothing else is required:

| attribute | meaning |
| --- | --- |
| `SOURCE` | The plugin slug, 1 to 64 characters; written to every snapshot's `source`. |
| `SEARCH_ENTITY_IDS` | A non-empty tuple of Search entity ids (UUID strings). |

`MAX_ROWS` (default 1000, never above the model's limit) may be lowered by a subclass.

`run()`:

1. `declare_no_surfaces()`: the run reads the grid, not a listing surface in a source system, so it claims no completeness, as `vdr_max` does.
2. Resolve every id with the service-layer read `tap_grid.services.get_node`. If an id is not found, or the node is not a `search`, record an error naming the id and raise before any Search runs; nothing is submitted.
3. Run each Search with `tap_grid.search.execute_search(search)`, so the Search's `input_schema` defaults apply. The collector runs as the shared `tap_cares.collector` program actor, whose bundle holds `grid.read` (`tap_auth.roles.json`), so the read is authorized. A Search that raises fails the run (the exception propagates, `req-tap-cares-collector-failure-mode`); nothing is submitted.
4. Take the result's `rows`. A result with no `rows` key and empty `nodes` and `edges` is zero rows; a result with no `rows` and any node or edge is a graph-shaped Search that v0 cannot snapshot, and fails the run with an error naming it.
5. Build one node per Search: `observed_at` is taken once at the start of the run and shared; `snapshot_key` is `<search id>@<observed_at>`; `rows` is the first `MAX_ROWS` rows; `row_count` is the exact count; `truncated` follows; `search_name` is the Search's name; `inputs_text` is the canonical JSON text of the `default` of each property in the Search's `input_schema` that declares one.
6. A value in a row that is a list or an object is replaced by its canonical JSON text, a string longer than 4096 characters is cut to 4096, and one warning per run says how many values were converted or cut. A Search should flatten its own columns; the collector does not drop the row.
7. Submit one GRIFT batch with `submit_grift`: the snapshot nodes, and for each an edge `CAPTURES_SEARCH__compliance_core` from the snapshot (by `from_ref`) to the Search (by `to_entity_id`). The batch `name` and `description` identify the collector and the Searches (`req-tap-cares-collector-grift-import`). The collector writes nothing else and never touches `CollectionJob`.
8. Set `summary` (for example `Snapshot 1 search: 6 rows, none truncated.`) and record an info entry.

#### Development

A snapshot is cheap to take and is never merged with another, so the collector does not read earlier snapshots and has no state between runs. If the grid is unchanged an hourly run writes an identical figure at a new time, which is correct: the flat stretch is the point of the series. Reading earlier snapshots to skip an unchanged one would give back the history gap this design avoids.

A subclass belongs in the plugin that owns the report, because the Search ids it names come from that plugin's or its project's seed. If the ids are missing the run fails with a clear error and writes nothing, rather than writing a partial set.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-search-snapshot-collector-1 | Abstract Base, No Registration | Implemented | `SearchSnapshotCollector` subclasses `CollectorBase`, is importable from the path above, and compliance_core registers no collector. | |
| req-compliance-core-search-snapshot-collector-2 | Subclass Contract | Implemented | A subclass without a non-empty `SOURCE` of at most 64 characters, or without a non-empty `SEARCH_ENTITY_IDS` tuple of UUID strings, is refused at class definition. | |
| req-compliance-core-search-snapshot-collector-3 | Resolve Before Running | Implemented | An id that is not found, or that names a node other than a `search`, fails the run with an error naming the id before any Search runs; nothing is submitted. | |
| req-compliance-core-search-snapshot-collector-4 | Runs Through The Search Service | Implemented | Each Search runs through `execute_search` with the Search's input defaults applied, and a Search that raises fails the run with nothing submitted. | |
| req-compliance-core-search-snapshot-collector-5 | Rows Only | Implemented | A result with `rows` is snapshotted; one with no `rows` and empty `nodes` and `edges` is zero rows; one with no `rows` and any node or edge fails the run. | |
| req-compliance-core-search-snapshot-collector-6 | Bounded And Honest | Implemented | At most `MAX_ROWS` rows are kept; `row_count` is the exact count of the Search's rows and `truncated` says whether any were dropped. | |
| req-compliance-core-search-snapshot-collector-7 | Scalar Rows | Implemented | A list or object value is replaced by its canonical JSON text, a string longer than 4096 characters is cut to 4096, and one warning per run counts the conversions and cuts; the row is kept. | |
| req-compliance-core-search-snapshot-collector-8 | Inputs Recorded | Implemented | `inputs_text` is the canonical JSON text (sorted keys, no spaces) of the defaults the run used. | |
| req-compliance-core-search-snapshot-collector-9 | Fresh Key Every Run | Implemented | `snapshot_key` is `<search id>@<observed_at as UTC ISO 8601 to the microsecond>`, `observed_at` is taken once per run, and a key is never reused; two runs write two nodes. | |
| req-compliance-core-search-snapshot-collector-10 | One Batch, Named | Implemented | One run submits one GRIFT batch with a collector-set name and description, holding the snapshot nodes and a `CAPTURES_SEARCH` edge from each to its Search by `to_entity_id`; nothing else is written. | |
| req-compliance-core-search-snapshot-collector-11 | Zero Rows Is A Snapshot | Implemented | A Search that returns no rows still produces a snapshot with `row_count` 0, `rows` empty and `truncated` false. | A coverage of nothing is a data point. |
| req-compliance-core-search-snapshot-collector-12 | No State Between Runs | Implemented | The collector reads no earlier snapshot and skips nothing because the figure is unchanged. | |

#### Future

A data-driven way to name the Searches (a dimension stamp on the Search, or an edge from the Collector node) replaces the hard-coded ids once collectors can carry per-instance configuration.


### Report Panel
----
RID: `req-compliance-core-panel-report`

Status: `Implemented`

A coverage or compliance report is read by leadership and sent to agencies, and it has to look like a report: a title, sections, lines of label and figure, a few trend lines, and nothing that reads as a web page. The standard panels bind one Search and draw cards or tables, which is the wrong shape. The `report` panel type draws a whole report from several Searches, as plain text and vector lines that print as they appear and paste into a presentation as they are. It ships in this plugin because the figures it reports (coverage, totals, snapshots) are this plugin's, and it names no regime: what a report says is the instance's data. Ruled by George, 2026-10-21: a panel with its own logic, in `compliance_core`, with the trend charts drawn inside it.

#### Implementation

`tap_plugin/compliance_core/panels/report/` defines `ReportPanelType` (slug `report`, view `compliance_core/panels/report.html`, css `compliance_core/css/report.css`, no JavaScript), registered in `apps.py` `ready()` on `tap_web.registry.panel_type_registry`, as `vuln_mosaic` registers its panel. An instance is a `panel` node whose `view` is that template and whose `config` is the object below.

**Searches.** A report line names a Search by entity id. The panel runs only Searches the panel node has a `USES_SEARCH` edge to: a line that names any other id is a configuration error, so a report cannot read a Search it is not linked to and the graph shows what a report depends on. Each Search is run once per render through `tap_grid.search.execute_search` and its rows are shared by every line that names it.

**Config** (`REPORT_PANEL_CONFIG_SCHEMA`, every property described, unknown keys refused):

| key | meaning |
| --- | --- |
| `title` | The report's title, shown once at the top. Optional. |
| `show_as_of` | Boolean, default true: show `As Of <render time, UTC>` under the title. |
| `page_break_before` | Boolean, default false: start a new printed page before this report. |
| `cut_line` | Optional string. When set, the report begins with a dashed hairline carrying this word (for example `Internal`), the mark below which a report is not for sending out. |
| `sections` | A non-empty array of sections: `{heading, items}`. |

An item is one of:

| `kind` | fields | draws |
| --- | --- | --- |
| `figure` | `label`, `search`, `field`, `format`, optional `row` (index, default 0) or `where` (`{field, equals}`), optional `of` (a second field shown as `of <n>`) | One line: the label at the left, the figure at the right, a hairline leader between. |
| `list` | `search`, `label_field`, `columns` (up to 4 of `{field, title, format}`), optional `limit` (default 20) | Rows of aligned text under a hairline header, one row per Search row, no cell borders. |
| `trend` | `label`, `lines` (an array of `{label, search, x_field, value_field, series_field?, series?}`), optional `y_min`, `y_max` (default 0 and 100) | A small vector line chart with one line per entry of `lines`. |
| `rule` | none | A hairline. |

`format` is one of `count` (an integer with thousands separators), `percent` (one decimal and a `%`), `date` (`YYYY-MM-DD`), `datetime` (UTC, minutes) or `text`. A figure is the field's value from the named row, or the first row where the field equals the value.

**Three states, never two.** A figure whose Search failed, returned no row or returned `null` for the field is shown as `Not observed`, never as `0` and never blank; a failed Search is also named in a footnote line (`Search unavailable`, without the error text). A trend with no points is shown as `No data yet`, not an empty frame. A `percent` over `null` is not drawn as 0.

**Trend drawing.** The panel draws each trend as inline SVG built from numbers only: a baseline, one thin line per entry of `lines`, the first and last time labels, and a direct label at the end of each line instead of a legend. A `lines` entry reads one series: with `series_field` and `series` it keeps only the rows whose field equals the value (for example `Overall`), otherwise all rows. Points are ordered by `x_field`. The y range is fixed by `y_min` and `y_max` so a trend never exaggerates a small move. The SVG carries a `<title>` and a visually hidden data table of its points, so the figures reach assistive technology and a copy-paste.

**Style.** Black text and one muted grey, a system font with tabular numerals, hairline rules, no backgrounds, no borders around items, no shadows, no rounded boxes, no colour-coded status and no icons. Meaning never rests on colour alone. A `@media print` block fits the report to a portrait page at its natural size, keeps each section together across a page break, and honours `page_break_before`; the screen layout is the print layout.

**Safety.** Every string, from config and from rows, is escaped; config holds no HTML. The SVG is built from validated numbers and escaped labels, never from row text as markup. The panel writes nothing and reads only the Searches it is linked to.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-compliance-core-panel-report-1 | Registered | Implemented | The `report` panel type is on the panel registry under `report`, declares its stylesheet and no script, and its config schema describes every property and refuses unknown keys. | As `req-vuln-mosaic-panel-cve-1`. |
| req-compliance-core-panel-report-2 | Only Linked Searches | Implemented | A line naming a Search the panel has no `USES_SEARCH` edge to renders a configuration error and runs no Search for it. | |
| req-compliance-core-panel-report-3 | One Run Per Search | Implemented | A Search named by several lines is run once per render. | |
| req-compliance-core-panel-report-4 | Figure Lines | Implemented | A `figure` shows its label, its formatted value and an optional `of <n>`, taking the value from the named row or the first row where `where` matches. | |
| req-compliance-core-panel-report-5 | Formats | Implemented | `count`, `percent`, `date`, `datetime` and `text` format as stated; a value that does not fit its format is shown as `Not observed`. | |
| req-compliance-core-panel-report-6 | Not Observed Is Not Zero | Implemented | A failed Search, a missing row and a `null` field each render `Not observed`, never `0` or blank, and a failed Search is named in a footnote without its error text. | |
| req-compliance-core-panel-report-7 | Lists | Implemented | A `list` renders one row per Search row, up to `limit`, with at most four columns and no cell borders, and says how many rows were left out. | |
| req-compliance-core-panel-report-8 | Trends Drawn In The Panel | Implemented | A `trend` renders inline SVG with one line per `lines` entry, direct end labels, a baseline and the first and last time labels, using no JavaScript and no external asset. | |
| req-compliance-core-panel-report-9 | Fixed Y Range | Implemented | The trend's y range is `y_min` to `y_max` (default 0 to 100) and does not rescale to the data. | |
| req-compliance-core-panel-report-10 | Series Filter | Implemented | A `lines` entry with `series_field` and `series` keeps only rows whose field equals the value, ordered by `x_field`; with none, all rows. | For the `Overall` line of a coverage history. |
| req-compliance-core-panel-report-11 | Empty Trend Is Stated | Implemented | A trend with no points renders `No data yet`, not an empty frame or a zero line. | |
| req-compliance-core-panel-report-12 | Accessible Data | Implemented | Each trend SVG has a `<title>` and a visually hidden table of its points. | As the chart panel. |
| req-compliance-core-panel-report-13 | Plain Style | Implemented | The stylesheet sets no background, border, shadow or radius on items, uses at most one grey besides the text colour, and encodes no meaning in colour alone. | |
| req-compliance-core-panel-report-14 | Prints As Shown | In Development | A `@media print` block fits the report to a portrait page, keeps each section unbroken, and honours `page_break_before`. | Checked in a browser print preview. |
| req-compliance-core-panel-report-15 | Cut Line | Implemented | A report with `cut_line` begins with a dashed hairline carrying that word, and a report without it draws none. | The agency report carries none; the internal one carries `Internal`. |
| req-compliance-core-panel-report-16 | Escaped | Implemented | Config and row strings are escaped, config holds no HTML, and a row value containing markup renders as text. | |
| req-compliance-core-panel-report-17 | Reads Only | Implemented | The panel writes no node or edge and runs only Searches it is linked to. | |

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
  vocabulary only; regimes and deployments own the wiring. One carve-out, proposed 2026-10-20:
  compliance_core ships the abstract `SearchSnapshotCollector` base class
  (`req-compliance-core-search-snapshot-collector`), because the snapshot is a compliance_core
  node and every plugin that snapshots a Search would otherwise copy the same code. The plugin
  registers no collector of its own: a subclass registers in the plugin that owns the Search.
- **Exception checkers, severity ceilings, deviation-type mapping, approval workflow and pages**
  (proposed 2026-10-19) — the checker plugins live in their own repositories
  (`req-compliance-core-exception-checker`); a regime's limits on which `kind` may cover which severity
  (FedRAMP does not approve an operational requirement for a High) belong to that regime's plugin; the
  mapping of `kind` to a regime's deviation types likewise; an exceptions page is a later `add-page`.
  Scanner-side exclusions (a path never scanned, a file never shipped in an image) are not exceptions:
  they act before a finding exists and belong to the scanner's configuration or the build.
