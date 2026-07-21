# Capability Greeting and Artifact-First Documentation

## Purpose

This contract prevents two user-experience failures:

1. a greeting triggering expensive repository analysis;
2. an explicit documentation request being answered as a long chat message without creating files.

## Intent precedence

The private router applies this order:

```text
DOCUMENTATION_GENERATION
CODE_REVIEW
QUESTION_ANSWERING
EXPLANATION
CAPABILITY_DETAILS
HELP
GREETING
```

A substantive task overrides a greeting prefix. Documentation generation wins when a prompt combines repository understanding with an explicit request to write or generate documentation.

## Greeting behavior

Greeting-only messages return at most seven outcome-oriented capabilities and example prompts. The router performs only lightweight workspace detection:

- no workspace;
- new repository;
- known repository.

It does not create `.t-understand/` or run the understanding pipeline.

## Documentation completion contract

A comprehensive documentation task requires at least five documents and these stable artifacts:

```text
.t-understand/output/documentation/latest/
├── index.md
├── architecture/
├── repositories/
├── interfaces/
├── data/
├── operations/
├── business/
├── reference/
└── _meta/
    ├── manifest.yaml
    ├── document-plan.yaml
    ├── information-architecture.yaml
    ├── coverage-ledger.yaml
    ├── sections.jsonl
    ├── traceability.jsonl
    ├── critique.yaml
    ├── validation.yaml
    └── user-view.yaml
```

The view is published only after canonical documentation validation and critique pass. It is replaced atomically while preserving the previous view if publication fails.

## Chat completion contract

The completion response contains only:

- completion status;
- stable output path;
- document count;
- coverage summary;
- important limitations;
- execution status of builds/tests;
- confirmation that application source and Git were not modified.

The full documentation body remains in files unless the human explicitly asks to view a particular document or section.

## Verification claim states

Human-facing claims must distinguish:

```text
VERIFIED_FROM_SOURCE
INFERRED_FROM_IMPLEMENTATION
DECLARED_IN_DOCUMENTATION
DISCOVERED_BUT_NOT_EXECUTED
EXECUTED_AND_PASSED
EXECUTED_AND_FAILED
UNKNOWN
CONFLICT
```

A Makefile target, CI job, or test class proves that a command exists; it does not prove execution success.

## Final-output sanitation

The validator rejects:

- private reasoning or scratchpad content;
- `Thought:` lines;
- internal todos;
- raw internal operation IDs;
- `ContextRoot` or `$TU` instructions;
- documentation bodies dumped into completion chat;
- unexecuted build/test pass claims.
