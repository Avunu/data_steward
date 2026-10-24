# Changelog

## [16.0.1](https://github.com/Avunu/data_steward/compare/v16.0.0...v16.0.1) (2026-10-24)


### Bug Fixes

* **clearance:** only change clearance dates on submitted entries ([#36](https://github.com/Avunu/data_steward/issues/36)) ([64db075](https://github.com/Avunu/data_steward/commit/64db075447ca27f8d5ea1c2f2eb1c296d129cfd8))
* **clearance:** refuse a clearance date before the cheque date ([#41](https://github.com/Avunu/data_steward/issues/41)) ([cecdbe8](https://github.com/Avunu/data_steward/commit/cecdbe820753f8d21da9b89c90cc15b30718ebcc))
* **merge:** only offer Merge Selected where it can merge, and show its log ([#35](https://github.com/Avunu/data_steward/issues/35)) ([7120010](https://github.com/Avunu/data_steward/commit/712001002f7ec9e7680e3f11ab035ea934ee480f))

## [16.0.0](https://github.com/Avunu/data_steward/compare/v0.0.1...v16.0.0) (2026-10-20)


### Features

* gate jailbreak capabilities ([404782c](https://github.com/Avunu/data_steward/commit/404782cf02f9c186d4f03ec1f4ebda8fbad09f52))
* implement capability-based accounting jailbreaks for ERPNext doctypes ([062474c](https://github.com/Avunu/data_steward/commit/062474c6fea3a0b3ce4fea3d2f44a275dcfd99c4))
* implement capability-based UI for accounting jailbreaks ([c318b61](https://github.com/Avunu/data_steward/commit/c318b61b0e4a5d0d5e4899ce49cd1f662ba4bff9))
* Initialize App ([5f7bbf0](https://github.com/Avunu/data_steward/commit/5f7bbf052efe36b2d28e44fd0f464089e308b52b))


### Bug Fixes

* don't throw errors on js capabilities checks ([46f2db9](https://github.com/Avunu/data_steward/commit/46f2db92a630b9bb308d7f22fc8fbf9f9af6c046))
* make js bundle app-specific ([d2c7b2d](https://github.com/Avunu/data_steward/commit/d2c7b2d1d3483ba5bd5e7a947d973e1916d67dad))
* reorder script imports ([2ff22ef](https://github.com/Avunu/data_steward/commit/2ff22ef820f496dad419c5959ab9a340af0f8599))
* **security:** require roles on jailbreak endpoints and drop unsafe features ([#11](https://github.com/Avunu/data_steward/issues/11)) ([91c7cc2](https://github.com/Avunu/data_steward/commit/91c7cc24e1b52d04aa8e5367bd93f7fbf67da692))
* version restore script ([ea862a1](https://github.com/Avunu/data_steward/commit/ea862a129b811399a3cc7db10b954040d1c9cb1b))


### Continuous Integration

* adopt the shared CI gates ([62a62d5](https://github.com/Avunu/data_steward/commit/62a62d5a2776a10ebbc4815b7161bc30debb6e4e))
