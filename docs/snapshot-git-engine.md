# Snapshot and Git Target Engine

Phase 4 turns a resolved application workspace into portable, immutable source identities without mutating any source repository.

## Target types

| Target | Meaning | Captured representation |
|---|---|---|
| `branch:<name>` | Exact local or explicitly named remote branch | Resolved commit and tree |
| `tag:<name>` | Exact tag | Peeled commit and tree |
| `commit:<hex>` | Hexadecimal object ID or abbreviation | Full commit and tree |
| `head` | Current HEAD commit | Resolved commit and tree |
| `index` | HEAD plus staged changes | Binary staged patch |
| `worktree` | HEAD plus staged, unstaged, and non-ignored untracked state | Binary patches, status manifest, and copied untracked regular files |

Commit-based snapshots do not archive the complete source tree. Git commit and tree object IDs are their immutable source identity. Index and worktree states cannot be represented by one commit, so their overlays are materialized under the dedicated context repository.

## Application snapshot structure

```text
snapshots/<SNAPSHOT_ID>/
├── application-snapshot.yaml
└── repositories/
    ├── <repository-id>.yaml
    └── <repository-id>/
        ├── staged.patch
        ├── unstaged.patch
        ├── status.porcelain-v1.z
        ├── untracked-manifest.yaml
        └── untracked/
```

Only artifacts relevant to the selected target are present. A `head`, `branch`, `tag`, or `commit` descriptor has no overlay payload.

Durable snapshot descriptors contain repository IDs, normalized repository identities, Git object IDs, relative artifact paths, SHA-256 values, and portable metadata. They never contain source checkout paths.

## Capture consistency

Index and worktree capture uses this sequence:

1. resolve HEAD and its tree;
2. enumerate changed paths and reject protected paths;
3. read staged and applicable unstaged binary patches;
4. read non-ignored untracked regular files;
5. inspect submodule boundaries;
6. calculate a state digest;
7. write payloads into a temporary context directory;
8. repeat source-state inspection;
9. reject the capture if the two state digests differ;
10. validate every descriptor and artifact;
11. atomically rename the completed temporary directory.

No partially captured snapshot receives its requested ID.

## Security boundaries

The engine uses read-only Git commands with terminal prompting and optional locks disabled.

The following fail closed:

- snapshot ID reuse;
- missing or ambiguous refs;
- revision expressions masquerading as commit IDs;
- changed protected paths such as `.env*`, credentials, keys, PEM files, or secret directories;
- untracked symlinks or non-regular files;
- dirty submodule internals in a worktree snapshot;
- patch or untracked payloads beyond configured limits;
- source changes observed during capture;
- absolute or escaping artifact paths;
- integrity mismatch after capture.

Ignored files are excluded. Phase 4 does not implement an approval mechanism to read protected changed files; it rejects them.

## Drift

Drift does not mutate a snapshot. It compares current local bindings to the stored target:

- branch, tag, and HEAD targets are re-resolved;
- commit targets verify the stored full commit and tree directly;
- index and worktree targets recalculate their state digest.

The result is `UNCHANGED`, `DRIFTED`, or `UNAVAILABLE` per repository and for the application snapshot.

## Immutable review targets

Review analysis consumes a separate binding:

```text
reviews/<REVIEW_ID>/review-target.yaml
```

A `STATIC_AUDIT` target binds one validated candidate application snapshot. A `DIFF` target binds validated baseline and candidate snapshots. The record stores each snapshot's relative path, file SHA-256, and content digest. Review target IDs cannot be reused or updated.

Phase 4 creates review targets only. Diff analysis and review findings remain assigned to Phase 14.
