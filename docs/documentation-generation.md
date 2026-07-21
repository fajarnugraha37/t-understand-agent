# Documentation Generation

Phase 11 renders a verified model set into immutable canonical Markdown documentation. Canonical documents are source-grounded content; renderer-specific syntax belongs to Phase 12 exports.

## Canonical catalog

The deterministic catalog contains 13 documents covering application overview, system context, dependencies, repositories, interfaces and events, data, deployment and security, business overview, capabilities, actors, business rules, lifecycle and state, and terminology.

Each document section has a structured record in `sections.jsonl` and a matching trace in `traceability.jsonl`. Supported sections contain claim and evidence IDs. Business inference is visibly labeled and carries limitations. Unknown intent and missing evidence remain explicit.

## Artifact layout

```text
<context-root>/documentation/canonical/<docset-id>/
├── documentation-manifest.yaml
├── information-architecture.yaml
├── document-plan.yaml
├── coverage-ledger.yaml
├── sections.jsonl
├── traceability.jsonl
└── docs/
```

## Freshness and invalidation

Canonical docsets are immutable. A memory invalidation report can produce a separate document invalidation report listing affected sections and documents. The base documentation is never silently rewritten or relabeled current.

## Quality gates

Generation requires full catalog coverage, section-level traceability, supported-section evidence, deterministic critique, checksum validation, relative-link validation, and tamper detection. Human publication approval remains a separate lifecycle gate.
