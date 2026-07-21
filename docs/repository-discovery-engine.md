# Repository Discovery Engine

Phase 5 inventories an application from a validated Phase 4 snapshot. It does not scan the current directory opportunistically.

## Snapshot reading

- Branch, tag, commit, and HEAD snapshots are read directly from Git objects.
- Index snapshots are read from stage-zero index entries.
- Worktree snapshots are read from the filesystem only after an explicit drift check proves that the captured overlay is unchanged.
- No checkout, reset, stash, add, commit, or other Git mutation is performed.

## Outputs

```text
<context-root>/discovery/<DISCOVERY_ID>/
├── application-discovery.yaml
├── validation-report.yaml
└── repositories/
    ├── <repository-id>.yaml
    └── <repository-id>.files.jsonl
```

The inventory distinguishes source, tests, configuration, build files, contracts, migrations, deployment assets, CI, documentation, generated output, vendored content, assets, and unknowns.

Protected, ignored, symlink, and submodule content is never read. Generated, vendored, binary, and oversized files remain visible in the coverage ledger but are excluded from language extraction.

## Honesty boundary

A discovered entry point, API contract, deployment file, or module is a deterministic candidate based on source evidence. Phase 5 does not claim that the runtime actually invokes it.
