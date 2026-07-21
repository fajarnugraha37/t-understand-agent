# t-understand 1.0.3

`t-understand` 1.0.3 hardens the agent-native conversation contract and makes documentation requests artifact-first.

## Capability greeting

Greeting-only prompts such as `hi`, `hello`, `hai`, or `halo` now produce a concise repository-aware capability card. They do not start discovery, analysis, or memory construction.

A substantive task always overrides the greeting prefix:

```text
hi
→ capability greeting

hi, review my current changes
→ review workflow
```

The canonical capability catalog lives in `orchestrator/capabilities.yaml` and is copied privately into every platform package.

## Artifact-first documentation

Explicit requests to write, generate, create, produce, or document repository documentation now have precedence over explanation and QnA routing.

The private `agent-document` workflow performs:

```text
workspace bootstrap
→ worktree snapshot
→ discovery
→ language/contract extraction
→ analysis
→ graph
→ canonical memory
→ modeling
→ documentation generation
→ critique
→ verification
→ stable user-facing publication
```

Generated documentation is published under:

```text
<workspace>/.t-understand/output/documentation/latest/
```

The stable view includes multiple Markdown documents plus manifest, document plan, coverage ledger, traceability, critique, and validation metadata.

A documentation request cannot complete with chat prose alone. The chat response is limited to a concise completion summary and output location.

## Verification-claim safety

The root agent now distinguishes source verification, implementation inference, repository declarations, discovered-but-not-executed commands, and actually executed results. Build, test, migration, infrastructure, or smoke-test success may not be claimed without captured execution evidence.

Private reasoning, internal todos, `Thought:` lines, internal artifact IDs, `ContextRoot`, and `$TU` are rejected by the final-response validator.

## Regression fixture

The following literal prompt is a permanent regression fixture:

```text
Understand this repository deeply, precisely and write comprehensive, detailed, deep, sensible documentation
```

It must create documentation files and return only a concise chat summary.

## Preserved guarantees

- all canonical skills use the `tu-*` namespace;
- normal use remains conversation-only;
- application source remains read-only;
- `.t-understand/**` remains managed metadata excluded from source evidence;
- Git remains read-only and `gh` remains denied;
- local tools do not fall back to per-operation permission prompts;
- suggested patches remain advisory.
