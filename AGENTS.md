# AGENTS.md — t-understand

## Purpose

This file is the portable continuity contract for developing `t-understand` itself. A fresh human or coding agent must be able to continue from the repository without relying on prior conversation history.

## Start every session

1. Read `README.md`, `PHASE-STATUS.md`, and this file.
2. Read `orchestrator/product-constitution.md`, `orchestrator/t-understand-core.md`, `orchestrator/runtime-policy.yaml`, `orchestrator/application-management-policy.yaml`, `orchestrator/snapshot-policy.yaml`, `orchestrator/discovery-policy.yaml`, and `orchestrator/language-adapter-policy.yaml`.
3. Inspect the agent, authority, artifact, workflow, lifecycle, skill, model-profile, workspace, and application registries/policies.
4. Run `make verify` before editing.
5. Inspect the working tree and preserve unrelated changes.
6. Classify the requested change as governance, lifecycle runtime, application/workspace, schema, authority, or a later implementation phase.

## Source-of-truth order

1. JSON Schemas and deterministic semantic validators.
2. Product constitution and canonical policies.
3. Agent, authority, artifact, workflow, lifecycle, skill, and model registries.
4. Runtime implementation and role instructions.
5. Templates and examples.
6. Prose documentation.

A contradiction is a defect. Never silently choose a lower-precedence source.

## Locked governance invariants

- Source repositories remain read-only for every role.
- `t-understand` is the only human-facing orchestrator.
- Workers are terminal; delegation depth is one.
- Only `tu-memory-curator` writes canonical memory.
- Candidate evidence does not become canonical truth without curation and validation.
- Technical and business writers write only their own documentation domains.
- `tu-reviewer` may emit suggested fixes but cannot apply them.
- `tu-critic` and `tu-verifier` are independent fresh invocations.
- Facts and high-confidence inferences require source evidence.
- Human-confirmed claims require recorded human confirmation.
- Stale or conflicted claims cannot be silently promoted to current fact.
- The economy profile remains sequential, schema-driven, model-inherited, and flagship-independent.

## Locked lifecycle runtime invariants

- State transitions come only from the canonical workflow registry.
- Exactly one active worker invocation is allowed per work item.
- Delegation packets always originate from `t-understand` at depth one.
- Workers receive source-read permission but source-write, Git mutation, and delegation denial.
- Result identity must match invocation, worker, workflow, state, and state version.
- Worker outputs use exact declared paths and verified SHA-256 digests.
- Results are validate-before-commit and replay is denied.
- Invalid or forward loopbacks are denied.
- Loopbacks mark target-and-later artifacts stale.
- Publication cannot advance without a recorded human approval.
- Runtime state uses atomic replacement and a local single-mutation lock.

## Locked Phase 3 application/workspace invariants

- `application.yaml` is portable and contains no absolute local paths.
- `workspace.local.yaml` is machine-local, uses absolute paths, and is ignored by default.
- Every registered repository has one stable ID and one unique remote or explicit identity.
- Credential-bearing HTTPS remotes, query strings, fragments, and local-file remotes are denied.
- Source access in every repository manifest is exactly `READ_ONLY`.
- Context initialization must fail before writing when the destination is inside an existing Git worktree.
- A bound repository path must equal its Git top-level directory.
- Remote identity mismatch fails closed.
- Duplicate or nested Git roots are denied.
- The context root and every source repository must be disjoint.
- Resolution may write only inside the dedicated context root.
- Phase 3 resolution must never be represented as an immutable source snapshot.

## Locked Phase 4 snapshot invariants

- Source repositories remain read-only and Git mutation commands are forbidden.
- Snapshot and review-target IDs are immutable and cannot be reused.
- Durable descriptors contain no source checkout absolute paths.
- Branch, tag, commit, and HEAD targets bind exact commit and tree object IDs.
- Index captures staged state only; worktree captures staged, unstaged, and non-ignored untracked regular files.
- Protected changed paths, ignored files, symlinks, non-regular files, oversized payloads, and dirty submodule internals fail closed.
- Source state is inspected before and after capture; detected races abort without publishing the requested snapshot ID.
- Completed snapshot directories are published by atomic rename.
- Drift creates a report and never mutates the stored snapshot.
- Review targets bind validated snapshot digests and are immutable; Phase 4 does not perform review analysis.


## Locked Phase 5 discovery invariants

- Discovery operates only from a validated immutable application snapshot.
- Commit-tree content is read from Git objects; index content is read from stage zero; worktree content requires a successful drift check.
- Inventory ordering is repository-relative path ascending.
- Protected, ignored, and symlink content is never read.
- Generated, vendored, binary, oversized, protected, symlink, and submodule exclusions remain visible in coverage ledgers.
- Included content uses SHA-256 and is bound to snapshot and repository identity.
- Discovery candidates are not represented as confirmed runtime behavior.
- Publication uses temporary construction followed by atomic rename.

## Locked Phase 6 adapter invariants

- Adapter manifests are canonical and schema-validated.
- Selection is highest detection score, then stable priority, then adapter ID.
- `generic` is the sole fallback and cannot claim language semantics.
- Every extraction binds exact snapshot, repository, path, file SHA-256, adapter ID, and adapter version.
- Parse failures remain `PARTIAL`; unsupported content remains `UNSUPPORTED` or `SKIPPED`.
- Adapters do not execute source code, macros, templates, annotation processors, source generators, or external references.
- Surface declarations and interface candidates are evidence inputs, not canonical memory or business facts.

## Locked Phase 7 analysis invariants

- Analysis consumes only validated extraction, discovery, and immutable snapshot artifacts.
- Every entity, relation, and observation references exact evidence.
- Evidence binds repository, commit revision, relative path, SHA-256, and locator.
- Explicit syntax and exact API/contract patterns may be `OBSERVED`; unresolved lexical calls remain conservative `INFERRED` relations.
- Analysis never infers business intent.
- Source execution and source writes are denied.
- Scoped analysis declares its scope.
- Incremental analysis reuses unchanged evidence slices and must be semantically equivalent to a full analysis for the same snapshot.
- Publication is temporary construction followed by atomic rename.

## Locked Phase 8 graph invariants

- Cross-repository relationships require evidence from both endpoints.
- Automatic links require exact complementary contract keys.
- Source and target repositories must differ.
- One-sided matches remain unresolved candidates.
- Multiple HTTP provider repositories are ambiguous and must not be promoted automatically.
- Event fan-out may produce multiple exact producer/consumer relationships.
- Shared-data relationships are `INFERENCE` and never establish ownership.
- Graph outputs do not mutate canonical memory.

## Locked Phase 9 memory invariants

- `tu-memory-curator` remains the sole canonical memory writer.
- Memory version directories are immutable.
- `current.yaml` is only an atomic pointer to a completed version.
- FACT and INFERENCE claims require evidence and reasoning.
- Conflicts are preserved and never resolved by arbitrary precedence.
- Stale evidence cannot support a current FACT.
- SQLite and future embeddings are rebuildable accelerators, never canonical truth.
- Invalidation compares exact source digests and propagates affected evidence, entities, relations, and claims.
- Invalidation reports never mutate their base memory version.

## Locked Phase 10 modeling invariants

- Model versions are immutable and bound to one canonical memory version and application snapshot.
- `tu-modeler` remains the sole canonical model writer.
- FACT, IMPLEMENTED_BEHAVIOR, and BUSINESS_INFERENCE records require canonical claims and evidence.
- Business capabilities, actors, ownership, and intent inferred from technical surfaces may not be promoted to FACT.
- Missing deployment, security, business-rule, or state-machine evidence must produce UNKNOWN or LIMITATION records.
- Conflicts survive modeling and are never hidden by arbitrary precedence.
- Model critique and verification are required before current-pointer publication.

## Locked Phase 11 documentation invariants

- Canonical documentation is immutable Markdown, independent of presentation platform.
- Every supported section has claim and evidence traceability.
- Business inference is visibly classified and includes limitations.
- Unknown intent and missing requirements remain unknown.
- The fixed documentation catalog and coverage ledger are deterministic.
- Memory invalidation produces a separate document invalidation report and never mutates a base docset.
- Human publication approval remains an explicit lifecycle gate.

## Locked Phase 12 exporter invariants

- Exporters perform presentation transformation only; canonical semantics may not change.
- Every export is immutable and bound to the source docset digest.
- Profile-specific configuration and file checksums are mandatory.
- Links, front matter, and fenced code structure are validated deterministically.
- Structural qualification does not claim execution of external hosted renderer services.

## Editing rules

- Change canonical policies and schemas before examples or prose.
- Make the smallest coherent change.
- Do not weaken validators to make invalid fixtures pass.
- Every new authority requires positive and negative boundary tests.
- Every new artifact type has exactly one canonical writer.
- Every new workflow state maps to one owner, one skill, and declared outputs.
- Every runtime mutation is validate-before-commit.
- Application management may invoke only read-only Git inspection commands.
- Never store machine-local paths in portable manifests, examples presented as portable, or durable evidence.
- Never hand-edit generated reports or checksums as the primary fix.
- Do not claim live-model, hosted-renderer, or remote-code-host execution unless an explicit runner records that evidence.
- Keep the Python package under the collision-resistant `tu_runtime` namespace.
- Do not upgrade inference to fact to improve apparent coverage.
- Do not silently select one side of a conflict or ambiguous cross-repository match.

## Required commands

```bash
make verify
```

Focused Phase 10–12 validation:

```bash
make model-contract
make model-tests
make documentation-contract
make documentation-tests
make documentation-cli
make export-contract
make export-tests
make verify-phase-10
make verify-phase-11
make verify-phase-12
```

Inspect:

```bash
cat reports/model-contract-report.json
cat reports/model-test-report.json
cat reports/documentation-contract-report.json
cat reports/documentation-test-report.json
cat reports/documentation-cli-report.json
cat reports/export-contract-report.json
cat reports/export-test-report.json
cat reports/phase-12-summary.json
```

## Definition of done

A Phase 10–12 change is complete only when:

- all Phase 1–9 regressions remain green;
- all schemas and governance contracts validate;
- model versions are immutable, snapshot-bound, and memory-bound;
- supported model records resolve to claims and evidence;
- business inference is not promoted to fact;
- unknowns and conflicts remain visible;
- all 13 model artifact families validate and pass critique;
- all 13 canonical documents are generated;
- section-level traceability and coverage ledgers are complete;
- document invalidation identifies affected sections without mutating the base docset;
- all five export profiles validate;
- exporters preserve canonical semantics;
- CLI end-to-end checks pass;
- extracted-package tests pass;
- checksums, reports, status, README, and manifest are regenerated.

## Phase 13–15 continuity

QnA answers and review runs are immutable, snapshot-bound artifacts. Never use generated documentation as sole implementation evidence. Major-or-higher review findings require critic challenge. Suggested patches are advisory and must never be applied. Review exporters may change presentation only; canonical finding meaning, evidence, severity, and locations are invariant.


## Locked Phase 16 quality invariants

- Consolidated quality targets are explicit immutable artifact IDs.
- Every target is validated by its canonical owning runtime.
- Critique is separate from generation where supported.
- Overall PASS is derived only from all required target results.
- Quality reports never mutate the artifacts they assess.

## Locked Phase 17 qualification invariants

- The built-in contract simulator records `live_model_tested: false`.
- No provider/model qualification claim is allowed without an external runner, exact identity/version, configuration, corpus, and evidence.
- Economy correctness remains dependent on schemas, evidence, critics, and deterministic validation rather than hidden flagship reasoning.

## Locked Phase 18 platform invariants

- Platform packages are generated from canonical agent and skill sources.
- Install targets are explicit and must be outside all registered source and context repositories.
- Managed files have ownership and SHA-256 records.
- Existing unmanaged files require explicit force and are backed up.
- Uninstall refuses modified managed files unless force is explicit.
- Cursor project-local activation is manual when automatic placement would violate source-read-only policy.

## Locked Phase 19 integration invariants

- Every required scenario runs in an isolated process.
- Aggregate PASS requires a completed PASS evidence file for every scenario.
- A timed-out aggregate process never implies a scenario PASS.

## Locked Phase 20 release invariants

- Current release version is `1.0.2`.
- Release qualification and SBOM are machine-generated.
- Python cache files are excluded.
- Checksums cover the released source tree.
- Two builds from identical input must be byte-for-byte equal.
- Critical gates must be repeated from the extracted final archive.

## Final verification commands

```bash
make verify-phase-16
make verify-phase-17
make verify-phase-18
make verify-phase-19
make verify-phase-20
```

A `1.0.2` release is complete only when Phase 1–15 backward regressions, Phase 16–20 contracts/tests, release audit, checksum verification, deterministic packaging, and extracted-package verification all pass.

## Locked v1.0.2 agent-native invariants

- Every skill ID, directory, and `SKILL.md` frontmatter name begins with `tu-`; the root product/orchestrator remains `t-understand`.
- Humans interact through natural-language requests in the host agent.
- `ContextRoot`, `$TU`, internal IDs, and pipeline commands are never prerequisites for normal use.
- The root agent silently initializes `<workspace>/.t-understand/` and generates internal IDs.
- `.t-understand/**` is excluded from snapshots, discovery, review, and Git operations.
- Every platform package includes the deterministic engine under `t-understand-engine/`.
- `install.ps1 -Target <platform> [-Force]` and equivalent shell wrappers are the only installation surface.
- Force replaces existing managed or unmanaged installations only after backup and validation.
- Platform packages contain no `ask` permission fallback for normal local work.
- Every `gh` command and every mutating Git operation is denied; Git is read-only inspection only.
- Existing platform JSON configuration is merged, backed up, checksummed, and restored.
