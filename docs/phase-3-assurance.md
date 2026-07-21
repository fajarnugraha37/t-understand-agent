# Phase 3 Assurance — Application and Workspace Management

## Implemented

- portable `application.yaml` contract;
- local-only `workspace.local.yaml` contract;
- application context initializer;
- repository registration and removal;
- remote identity normalization;
- explicit identity support for repositories without a remote;
- machine-local repository binding and unbinding;
- single-repository resolution;
- monorepository resolution;
- multi-repository resolution;
- context/source boundary enforcement;
- credential-bearing remote rejection;
- workspace resolution artifact generation;
- application validation and CLI commands;
- lifecycle work-state application ID binding.

## Security and integrity properties

- Application initialization checks whether the destination is inside an existing Git worktree before creating files.
- Source repositories are inspected using read-only Git commands with optional locking disabled.
- A mapped path must equal the Git top-level directory.
- Duplicate and nested source roots are rejected.
- Remote identity mismatch fails closed.
- Portable manifests contain no local absolute paths.
- The local workspace map is ignored by default.
- Resolution output is written only in the dedicated context root.

## Validation

The generated report `reports/phase-3-summary.json` records contract, functional, negative, resolution, and CLI checks.

Phase 1 governance and Phase 2 lifecycle runtime are rerun as regressions before release packaging.

## Explicit boundary

Phase 3 resolves where repositories are and verifies their stable identity. It does not freeze commits, staged changes, unstaged changes, or untracked-file digests. Those immutable snapshot semantics belong to Phase 4.
