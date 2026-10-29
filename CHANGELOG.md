# Changelog

## [0.8.11](https://github.com/unified-systems-com/compliance-core-tap/compare/v0.8.10...v0.8.11) (2026-10-29)


### Features

* **search:** dimension-mapping-totals-set, several summaries' totals in one row ([#81](https://github.com/unified-systems-com/compliance-core-tap/issues/81)) ([dba77a8](https://github.com/unified-systems-com/compliance-core-tap/commit/dba77a872cc17a78a7c13bb89769807ca1ccf834))


### Bug Fixes

* **report:** the report panel follows the dark theme ([#80](https://github.com/unified-systems-com/compliance-core-tap/issues/80)) ([d4c514f](https://github.com/unified-systems-com/compliance-core-tap/commit/d4c514f1de107d7a2f9ecded8a2c10dd33d6d233))

## [0.8.10](https://github.com/unified-systems-com/compliance-core-tap/compare/v0.8.9...v0.8.10) (2026-10-22)


### Features

* **compliance_core:** the report panel type ([521b834](https://github.com/unified-systems-com/compliance-core-tap/commit/521b834a511d26570d8d11c5d7648a617b029470))
* **compliance_core:** the report panel type ([55b80b9](https://github.com/unified-systems-com/compliance-core-tap/commit/55b80b95fddcb2741ea087dd11b7017dd97051b3))


### Bug Fixes

* **compliance_core:** a failed trend Search reads Not observed, not No data yet ([3ee510c](https://github.com/unified-systems-com/compliance-core-tap/commit/3ee510cd480684364335d630b4c91b20665b5015))
* **compliance_core:** report panel review fixes ([530be4e](https://github.com/unified-systems-com/compliance-core-tap/commit/530be4e8648b4a588e8cb8f363d8929511d22767))


### Documentation

* **spec:** the report panel type ([b3985f2](https://github.com/unified-systems-com/compliance-core-tap/commit/b3985f236720c838e6703082711dee3a477c864c))
* **spec:** the report panel, a plain print-ready report drawn from Searches ([89f0d5a](https://github.com/unified-systems-com/compliance-core-tap/commit/89f0d5aa9388e9f34f1f323b1caac4162827a76a))

## [0.8.9](https://github.com/unified-systems-com/compliance-core-tap/compare/v0.8.8...v0.8.9) (2026-10-21)


### Features

* **compliance_core:** dimension-mapping-totals and the shared coverage calculation ([00abe64](https://github.com/unified-systems-com/compliance-core-tap/commit/00abe64cebfacd87c5c3cef2c2c4707091612069))
* **compliance_core:** dimension-mapping-totals and the shared coverage calculation ([3e34238](https://github.com/unified-systems-com/compliance-core-tap/commit/3e3423891699d8e632b8dad67105be3f9eb1f365))


### Bug Fixes

* **compliance_core:** keep the except tuple parenthesized in the totals runner ([5c8a8dd](https://github.com/unified-systems-com/compliance-core-tap/commit/5c8a8dd69b32a57610ed37245ac021913d06209f))
* **compliance_core:** pass layer to the summary; check coverage.py's imports statically ([39fd736](https://github.com/unified-systems-com/compliance-core-tap/commit/39fd73627d3003523cd11caa9780c4c6160c1819))


### Documentation

* **spec:** dimension-mapping-totals, the live coverage totals a card reads ([aa13c61](https://github.com/unified-systems-com/compliance-core-tap/commit/aa13c6127fc88d6269868e2937ad98992e341967))

## [0.8.8](https://github.com/unified-systems-com/compliance-core-tap/compare/v0.8.7...v0.8.8) (2026-10-21)


### Features

* **compliance_core:** grouped dimension mapping and the search-snapshot-series runner ([301af3d](https://github.com/unified-systems-com/compliance-core-tap/commit/301af3d7a4ea348e125ba0e56a95471130cbc1b9))
* **compliance_core:** grouped dimension mapping and the search-snapshot-series runner ([bf5ebd4](https://github.com/unified-systems-com/compliance-core-tap/commit/bf5ebd44009e3b7a700dc5078cd30128688a1e7b))
* **compliance_core:** retire COVERS_COMPLIANCE_FINDING rows whose source is an exception ([accb2f6](https://github.com/unified-systems-com/compliance-core-tap/commit/accb2f665660e80c386b73b3bd5b72c1b6ac4be3))
* **compliance_core:** retire COVERS_COMPLIANCE_FINDING rows whose source is an exception ([1cde87c](https://github.com/unified-systems-com/compliance-core-tap/commit/1cde87c2693f7ff97f656a8d13fc9ced6910115f))
* fix_state on CONCERNS_COMPLIANCE_VULNERABILITY ([758a5f1](https://github.com/unified-systems-com/compliance-core-tap/commit/758a5f1bd4cb9d6e781bf08171cac1102b4d0e71))
* fix_state on CONCERNS_COMPLIANCE_VULNERABILITY [via grype-tap] ([3505790](https://github.com/unified-systems-com/compliance-core-tap/commit/3505790f22445f32d12dfd60c18a73664fada0ef))


### Bug Fixes

* **compliance_core:** group by an exact JSON key; the entities runner warns of types with no rule ([8b2c2d9](https://github.com/unified-systems-com/compliance-core-tap/commit/8b2c2d98e79236af26193a03927976b9a1169fc6))
* **compliance_core:** tighten grouped mapping and the snapshot series reader ([fef384a](https://github.com/unified-systems-com/compliance-core-tap/commit/fef384a32e47b9fe7c6357e4c94708d45bc0a504))


### Documentation

* **spec:** fix_state on CONCERNS_COMPLIANCE_VULNERABILITY ([a441c61](https://github.com/unified-systems-com/compliance-core-tap/commit/a441c61981fa62295ffcf2be6b6123a75867cc28))
* **spec:** grouped dimension mapping and the snapshot series reader ([fe772b5](https://github.com/unified-systems-com/compliance-core-tap/commit/fe772b52bb496abd79fed6ca2bd23abc4fcfb3ce))
* **spec:** grouped dimension mapping and the snapshot series reader ([f7444d0](https://github.com/unified-systems-com/compliance-core-tap/commit/f7444d03e8737100b29e39378f54c8c083f3624d))

## [0.8.7](https://github.com/unified-systems-com/compliance-core-tap/compare/v0.8.6...v0.8.7) (2026-10-20)


### Features

* **compliance_core:** compliance_search_snapshot, CAPTURES_SEARCH and the SearchSnapshotCollector base ([562a9ec](https://github.com/unified-systems-com/compliance-core-tap/commit/562a9ecace96bb3b471079fe5cd22a424c196aa2))
* **compliance_core:** compliance_search_snapshot, CAPTURES_SEARCH and the SearchSnapshotCollector base ([a9c447d](https://github.com/unified-systems-com/compliance-core-tap/commit/a9c447d79bc9734d2c061b4507ff2da2f55f7b00))
* **compliance_core:** dimension-mapping-summary and dimension-mapping-entities Search runners ([1064d09](https://github.com/unified-systems-com/compliance-core-tap/commit/1064d0918d3b1afc16cdf2f797db0a3183c63b58))
* **compliance_core:** dimension-mapping-summary and dimension-mapping-entities Search runners ([b9be7fb](https://github.com/unified-systems-com/compliance-core-tap/commit/b9be7fb8041e87214478af79e6b68cba8e927f39))


### Bug Fixes

* **compliance_core:** bound the mapping entities runner's memory by max_entities ([54124b7](https://github.com/unified-systems-com/compliance-core-tap/commit/54124b7ec03bf41ca5c6cb66c70999766506574b))
* **compliance_core:** bound the mapping's string lengths; build allowed_text once per row ([5b05c1b](https://github.com/unified-systems-com/compliance-core-tap/commit/5b05c1b55aa5c1cacf52f7da4992015ddc09ca66))
* **compliance_core:** refuse a Search named twice; keep a snapshot's display name within 255 ([2b52c14](https://github.com/unified-systems-com/compliance-core-tap/commit/2b52c148513e09258471a3e6d97091919ca8c9da))


### Documentation

* **spec:** compliance_search_snapshot and the SearchSnapshotCollector base class ([9d9d533](https://github.com/unified-systems-com/compliance-core-tap/commit/9d9d5333241614518e0ea81e93c9985011b2daf1))

## [0.8.6](https://github.com/unified-systems-com/compliance-core-tap/compare/v0.8.5...v0.8.6) (2026-10-20)


### Features

* **compliance_core:** finding-exception-coverage and exceptions-due-review Search runners (PR B) ([db57d45](https://github.com/unified-systems-com/compliance-core-tap/commit/db57d45dc3cfd913b174db79c887f39183a5810a))
* **compliance_core:** finding-exception-coverage and exceptions-due-review Search runners (PR B) ([a277799](https://github.com/unified-systems-com/compliance-core-tap/commit/a2777990c8307a0da32a84808273055fe1610353))


### Bug Fixes

* **compliance_core:** build the test cases in a loop, not as a bare tuple expression ([123d060](https://github.com/unified-systems-com/compliance-core-tap/commit/123d0606dd2a60a0747d88610f988f79aaf66046))
* **compliance_core:** coverage needs at least one anchor whatever anchor_count says; drop assert ([ac5c086](https://github.com/unified-systems-com/compliance-core-tap/commit/ac5c086469974ad3c33f93d2553452046356cb1a))
* **release:** set the release-please manifest to the released version, 0.8.5 ([ad9072f](https://github.com/unified-systems-com/compliance-core-tap/commit/ad9072fcad61cb29f3a2962915dd0b9ed275c0f4))
* **release:** set the release-please manifest to the released version, 0.8.5 ([43cdae8](https://github.com/unified-systems-com/compliance-core-tap/commit/43cdae83041a535b0f136fb229cdcdf1e29f4908))
