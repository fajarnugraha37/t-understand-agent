# Consolidated Quality Plane

Phase 16 adds a single fail-closed verification entry point over immutable artifacts produced by Phases 9–15.

## Supported targets

```text
memory
model
documentation
export
qna
review
review-export
```

A quality run accepts explicit `KIND:ID` targets. It validates every artifact with its owning manager and invokes a separate critique pass where the artifact family supports critique. A report passes only when every requested target passes all applicable checks.

## Output

```text
<context-root>/quality/reports/<QLTY-ID>/
├── quality-report.yaml
└── quality-manifest.yaml
```

The report and manifest are immutable, schema-validated, content-digested, and published atomically. Invalid or failed targets remain visible in the report; the quality plane never rewrites the target artifacts.

## Safety properties

- duplicate targets are rejected;
- unsupported target families are rejected;
- target validation is delegated to the canonical owning runtime;
- memory, model, documentation, and QnA critique is required;
- result status is derived from target results rather than supplied by a model;
- tampered reports fail validation;
- failed publication is rolled back;
- source repositories remain read-only.

## CLI

```bash
t-understand --context-root /path/to/context \
  quality-run --quality-id QLTY-RELEASE \
  --profile release \
  --target memory:MEMORY_001 \
  --target model:MODEL_001 \
  --target documentation:DOCS_001 \
  --target qna:QNA_001 \
  --target review:REVIEW_001
```

Additional commands are `quality-show`, `quality-list`, and `quality-validate`.
