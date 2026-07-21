# Multi-repository application contract

`t-understand 1.1.0` represents a product/application as one logical application with one or more Git repositories.

## Application root

For multi-repository workspaces, managed state lives at the common application workspace root:

```text
workspace/
├── .t-understand/
├── frontend/
├── order-service/
├── contracts/
└── infrastructure/
```

Child repositories do not receive independent knowledge stores for the same application.

## Discovery

The agent can resolve:

- an existing registered application root;
- one active Git repository;
- sibling repositories when the prompt explicitly asks for all/multiple repositories;
- child repositories when the host opens a non-Git application parent.

Discovery is bounded and excludes VCS metadata, dependencies, generated output, build directories, IDE metadata, and `.t-understand`.

## Identity and binding

Portable repository identity comes from normalized remote identity when available, with deterministic local explicit identity as fallback. Filesystem paths are machine-local bindings. Repository IDs are unique within the application.

## Snapshot consistency

One application snapshot records the worktree or revision of every participating repository. Cross-repository claims, flows, and documentation bind to this application snapshot rather than combining unstated repository versions.

## Documentation

Every registered repository receives a complete documentation subtree. Cross-repository HTTP, event, data, dependency, security, consistency, and end-to-end flow relationships are documented at application level. Ambiguous matches remain unresolved candidates rather than being linked arbitrarily.
