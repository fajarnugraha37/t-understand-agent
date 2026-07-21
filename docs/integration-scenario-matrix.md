# Complete Integration Scenario Matrix

Phase 19 qualifies complete workflows using isolated, individually recorded scenario runs. Each scenario writes its own evidence report so a long aggregate process cannot hide an incomplete case.

## Required scenarios

| Scenario | Scope |
|---|---|
| `single-repo-complete-pipeline` | Snapshot through analysis, graph, memory, model, documentation, export, QnA, static review, and consolidated quality |
| `monorepo-module-coverage` | Deterministic module discovery and coverage for multiple modules in one repository |
| `multi-repo-contract-graph` | Evidence-backed cross-repository event/contract linking |
| `diff-review-matrix` | Immutable comparative review and merge-gate production |
| `freshness-invalidation-refresh` | Source change detection and invalidation propagation |
| `platform-package-install-uninstall` | Package, managed install, doctor, and safe uninstall |
| `cheap-model-contract-qualification` | Provider-neutral profile and contract qualification |

## Execution model

Each scenario is run in a separate process and writes:

```text
reports/integration-scenarios/<scenario-id>.json
```

Only completed scenario reports are aggregated into:

```text
reports/integration-test-report.json
```

The aggregate report passes only when every required scenario exists, validates, and reports `PASS`.

## CLI

```bash
t-understand integration-matrix
t-understand integration-report
```
