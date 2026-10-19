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

## Plugin Identity

- **Slug:** `compliance_core`
- **Kind:** substrate library plugin — regime-agnostic compliance vocabulary. **No
  collector in v0.**
- **Public surface:**
  - **Models** (see `req-compliance-core-models`): `compliance_artifact`,
    `compliance_context`, `compliance_evidence`, `compliance_finding`,
    `compliance_exception`, `compliance_boundary`; and, added 2026-10-15,
    `compliance_vulnerability`, `compliance_scanner`, `compliance_scan_run`
    (see `req-compliance-core-vulnerability`, `-scanner`, `-scan-run`).
  - **Edge types** (see `req-compliance-core-edges`): `CITES_COMPLIANCE_EVIDENCE`,
    `COVERS_COMPLIANCE_FINDING`, `CARRIES_COMPLIANCE_FINDING`,
    `SCOPED_TO_COMPLIANCE_BOUNDARY`, `CONCERNS_COMPLIANCE_CONTROL`; and, added 2026-10-15,
    `CONCERNS_COMPLIANCE_VULNERABILITY`, `PERFORMS_COMPLIANCE_SCAN_RUN`,
    `REPORTS_COMPLIANCE_FINDING`, `DETECTS_COMPLIANCE_FINDING`, `RUNS_AT_LOCATION`, and, added
    2026-10-15 (Issue# 38 - this repo), `SCANNED_COMPLIANCE_TARGET`
    (see `req-compliance-core-scan-edges`).
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
| req-compliance-core-edges | [Edge Vocabulary](#edge-vocabulary) | Implemented | `CITES_COMPLIANCE_EVIDENCE`, `COVERS_COMPLIANCE_FINDING`, `CARRIES_COMPLIANCE_FINDING`, `SCOPED_TO_COMPLIANCE_BOUNDARY`, `CONCERNS_COMPLIANCE_CONTROL` (wildcard target). |
| req-compliance-core-identity | [Assigned Identity](#assigned-identity) | Implemented | Every model declares `NATURAL_KEY`; the five producer-minted types key on `("source", "source_key")`, `compliance_context` on `("regime",)`. Floor `requires_tap >= 0.2.0`. |
| req-compliance-core-regime-neutral | [Regime On The Instance](#regime-on-the-instance) | Implemented | Model default is a neutral type marker; regime layered per-instance. Fixes the hardcoded `fedramp-20x` default. |
| req-compliance-core-vulnerability | [Vulnerability Modeling](#vulnerability-modeling) | Implemented | `compliance_vulnerability`: a public record (CVE, else GHSA) named once however many tools report it; CVSS, CWE, SSVC and KEV facts live here, not on every finding. |
| req-compliance-core-scanner | [Scanner Modeling](#scanner-modeling) | Implemented | `compliance_scanner`: an installed instance of a detection tool at one place, never a version. |
| req-compliance-core-scan-run | [Scan Run Modeling](#scan-run-modeling) | Implemented | `compliance_scan_run`: one execution of a scanner; carries the tool version, commit, ref, category, time, outcome, result count and the database build it matched against. |
| req-compliance-core-scan-edges | [Scan Edges](#scan-edges) | Implemented | `CONCERNS_COMPLIANCE_VULNERABILITY`, `PERFORMS_COMPLIANCE_SCAN_RUN`, `REPORTS_COMPLIANCE_FINDING`, `DETECTS_COMPLIANCE_FINDING`, `RUNS_AT_LOCATION`, `SCANNED_COMPLIANCE_TARGET`. |
| req-compliance-core-searches | [Vulnerability Cross-Tab Searches](#vulnerability-cross-tab-searches) | Implemented | Two `module` Search runners, `vulnerability-components` and `component-severity`, return table rows by ORM aggregation under the read rules Gryphon applies. |
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
| `compliance_core__compliance_finding` | `fedramp_20x_ksi__finding` | `name`, `summary`, `description`, `status`, `source` + `source_key` (identity) |
| `compliance_core__compliance_exception` | `fedramp_20x_ksi__exception` | `name`, `description`, `status`, `source` + `source_key` (identity) |
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
| `COVERS_COMPLIANCE_FINDING` | `COVERS_FINDING` | `compliance_exception` → `compliance_finding` |
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
