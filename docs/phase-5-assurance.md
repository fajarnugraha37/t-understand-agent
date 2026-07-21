# Phase 5 Assurance — Repository Discovery Engine

Phase 5 implements snapshot-bound repository discovery for single repositories, monorepositories, and multi-repository applications.

Implemented controls include deterministic file ordering, protected-content denial, generated/vendor/binary exclusion ledgers, language and build detection, module-root identification, entry-point candidates, contract/deployment/CI/migration discovery, SHA-256 inventory, coverage ledgers, atomic publication, and tamper validation.

Evidence is recorded in `reports/discovery-contract-report.json`, `reports/discovery-test-report.json`, `reports/discovery-cli-report.json`, and `reports/phase-5-summary.json`.

Phase 5 does not claim semantic control flow, call graphs, runtime behavior, or business understanding.
