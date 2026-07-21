# Application and Workspace Management

Phase 3 separates portable application identity from machine-local checkout paths.

## Portable application manifest

`application.yaml` is suitable for version control. It contains:

- application ID and name;
- workspace model: `single-repo`, `monorepo`, or `multi-repo`;
- stable repository IDs;
- repository roles;
- normalized remote identity or explicit stable identity;
- optional credential-free remote hints;
- the locked `READ_ONLY` source-access declaration.

It must never contain an absolute local path.

## Local workspace map

`workspace.local.yaml` binds repository IDs to absolute checkout paths for one machine. It is generated in the context root and included in `.gitignore`.

A different machine creates its own map without changing `application.yaml`.

## Repository identity

HTTPS, SSH, and SCP-like Git remotes normalize to:

```text
lowercase-host/repository/path
```

These remotes are equivalent:

```text
https://github.com/acme/order.git
git@github.com:acme/order.git
ssh://git@github.com/acme/order.git
```

Credential-bearing HTTPS URLs, URL query strings, fragments, local-file remotes, and malformed paths are rejected.

A repository without a portable remote may use an explicit stable identity supplied by the human.

## Resolution gates

`workspace-resolve` succeeds only when:

1. the repository count matches the declared workspace model;
2. every registered repository is bound;
3. no unknown binding exists;
4. every mapped directory is a Git worktree root;
5. remote identities match when remote identity is used;
6. Git roots are unique and non-nested;
7. the context root is outside every source repository;
8. every source repository is outside the context root.

The resulting `runtime/workspace-resolution.yaml` is local and rebuildable. It is not an immutable source snapshot; Phase 4 owns snapshot capture.

## Context structure created by Phase 3

```text
t-understand-context/
├── application.yaml
├── workspace.local.yaml       # ignored
├── .gitignore
├── snapshots/
├── evidence/
├── memory/
├── models/flows/
├── documentation/
│   ├── canonical/
│   ├── mintlify/
│   └── traceability/
├── qna/
├── reviews/
├── approvals/
├── reports/
└── runtime/                   # ignored
```

Empty directories are preparation points for later phases and do not imply their capabilities are implemented.
