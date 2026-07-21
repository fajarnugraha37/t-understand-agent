# Architecture Overview

Phases 1–6 now implement the governed control plane and the deterministic source-intake foundation:

1. governance and lifecycle control;
2. portable application/workspace registration;
3. immutable Git snapshots and review-target binding;
4. repository discovery and source inventory;
5. language and contract surface adapters.

The next architecture layers remain:

1. structural and behavioral analysis;
2. cross-repository application graph;
3. canonical memory, invalidation, and models;
4. documentation, QnA, and review capability workflows;
5. independent critique, verification, exporters, and platform installation.

All source access is read-only. Durable context belongs to a separate application context repository. Canonical records use portable repository IDs, immutable snapshot IDs, relative paths, and digests rather than local absolute paths.

```text
application/workspace
        ↓
immutable snapshot
        ↓
repository discovery
        ↓
language/contract surface extraction
        ↓
Phase 7 semantic analysis
```

Discovery and adapters are deterministic preprocessing. They reduce the evidence supplied to AI agents and therefore improve consistency on economical models without claiming semantic understanding prematurely.
