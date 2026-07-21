# Phase 4 Assurance — Snapshot and Git Target Engine

Phase 4 implements portable immutable repository and application snapshots, Git-target resolution, worktree overlay capture, drift detection, and immutable review-target binding.

## Implemented controls

- six Git target types: branch, tag, commit, HEAD, index, and worktree;
- full commit and tree identity resolution;
- binary staged and unstaged patch capture;
- non-ignored untracked regular-file capture;
- deterministic untracked manifest and SHA-256 inventory;
- protected path, symlink, size, and dirty-submodule rejection;
- two-pass worktree race detection;
- temporary-directory construction followed by atomic rename;
- portable descriptors without source absolute paths;
- snapshot integrity validation;
- explicit current-workspace drift detection;
- application snapshots across all registered repositories;
- immutable static-audit and diff review targets.

## Validation evidence

Generated validation results are recorded in:

- `reports/snapshot-contract-report.json`;
- `reports/snapshot-test-report.json`;
- `reports/snapshot-cli-report.json`;
- `reports/phase-4-summary.json`.

Phase 4 tests include positive captures, target combinations, multi-repository ordering, source preservation, index exclusion semantics, worktree overlays, branch drift, tamper detection, protected paths, symlinks, oversized payloads, dirty submodules, invalid refs, immutable IDs, and review-target integrity.

## Honest boundaries

Phase 4 does not perform repository/module discovery, language parsing, canonical memory construction, documentation generation, QnA, diff analysis, or code-review finding synthesis.

A snapshot descriptor proves what immutable Git identity or uncommitted overlay was captured. It does not claim that the code has already been understood.
