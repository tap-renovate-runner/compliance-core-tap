# Changelog

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
