# System and Business Modeling

Phase 10 converts one verified canonical memory version into one immutable model set. The model set is derived, not a replacement for memory.

## Artifact layout

```text
<context-root>/models/
├── current.yaml
└── versions/<model-id>/
    ├── model-manifest.yaml
    ├── application-model.yaml
    ├── architecture-model.yaml
    ├── dependency-model.yaml
    ├── data-model.yaml
    ├── event-model.yaml
    ├── deployment-model.yaml
    ├── security-model.yaml
    ├── business-capabilities.yaml
    ├── business-rules.yaml
    ├── actors.yaml
    ├── state-model.yaml
    ├── flows.yaml
    ├── terminology.yaml
    └── traceability.jsonl
```

## Classification contract

Every model record is explicitly classified as `FACT`, `IMPLEMENTED_BEHAVIOR`, `BUSINESS_INFERENCE`, `HUMAN_CONFIRMED`, `UNKNOWN`, `CONFLICT`, or `LIMITATION`.

`FACT`, `IMPLEMENTED_BEHAVIOR`, and `BUSINESS_INFERENCE` records must resolve to canonical claim and evidence IDs. Business capability names, actors, and intent inferred from technical surfaces remain `BUSINESS_INFERENCE` and include limitations. Missing deployment, security, business-rule, or state-machine evidence results in an `UNKNOWN` record rather than fabricated completeness.

## Quality gates

Model generation is validate-before-publish. A completed model set must pass schema validation, digest and checksum validation, reference closure, duplicate-ID detection, evidence support checks, business-fact promotion checks, conflict preservation, deterministic critique, and deterministic verification.

## Reconciliation

Model record IDs are stable for the same semantic model type and key across model versions. `model-reconcile` builds a candidate version and reports added, removed, changed, and unchanged records without mutating the base version.

```bash
./bin/t-understand --context-root /application-a/t-understand-context \
  model-reconcile --reconciliation-id RECON_001 \
  --base-model-id MODEL_001 --model-id MODEL_002 --memory-id MEMORY_002
```
