# Agent-Native Workflow

## User contract

The user works entirely through conversation in the host coding agent. A valid request can be as simple as:

```text
Explain this repository.
```

The root coordinator must not respond by asking for a context directory, executable variable, artifact ID, pipeline command, or storage decision.

## Silent bootstrap

For the first substantive request in a Git worktree, the coordinator:

1. resolves the active Git root using read-only Git;
2. creates `<workspace>/.t-understand/` if absent;
3. creates a single-repository application binding automatically;
4. records the current repository identity and optional origin URL;
5. excludes `.t-understand/**` from snapshot and discovery input;
6. generates stable internal IDs;
7. proceeds with the requested workflow.

For monorepo or multi-repo questions, the coordinator discovers likely repository roots and asks only when application membership is genuinely ambiguous. It still does not ask about internal storage.

## Conversational workflows

### Understand

```text
Understand this repository and explain the architecture.
```

Internal flow:

```text
bootstrap → snapshot → discovery → adapters → analysis → graph
→ memory → model → answer
```

### Ask a code question

```text
Where is customer eligibility decided?
```

Internal flow:

```text
freshness → retrieval → direct source verification → answer
→ critic → citation validation
```

### Generate documentation

```text
Generate developer onboarding documentation.
```

Internal flow:

```text
memory → models → document plan → canonical documents
→ traceability → critique → export
```

### Review changes

```text
Review my worktree against HEAD.
```

Internal flow:

```text
baseline/candidate snapshots → changed-file ledger → impact lookup
→ findings → critic → severity → merge gate → response
```

### Refresh after changes

```text
Refresh your understanding after my latest edits.
```

Internal flow:

```text
new snapshot → change detection → selective analysis
→ memory invalidation/rebuild → model reconciliation
→ documentation invalidation
```

## Internal engine

Each platform package contains `t-understand-engine/agent_runtime.py` plus the runtime, schemas, policies, adapters, and templates. The host agent invokes this engine silently. The runtime CLI is a private implementation interface, not the product's user interface.

## ID policy

The coordinator generates IDs from operation type, UTC time, and content identity. IDs are not requested from the human. They are exposed only when useful for audit, diagnostics, or exact reproduction.

## Failure behavior

The coordinator asks a human question only when the answer changes the meaning or scope of the requested analysis. It does not ask questions merely because an internal default can be selected safely.


## Capability greeting

Greeting-only prompts use the canonical capability catalog and perform only lightweight workspace detection. They do not create state or start repository analysis. `hi, <task>` routes directly to the substantive task.

## Artifact-first documentation

Prompts that explicitly request documentation invoke the private `agent-document` workflow. Completion requires generated files, manifest, plan, coverage, traceability, critique, and validation under `.t-understand/output/documentation/latest/`. Chat-only prose cannot satisfy this workflow. The final chat response is a concise summary and is validated for private-reasoning leakage and unsupported execution claims.
