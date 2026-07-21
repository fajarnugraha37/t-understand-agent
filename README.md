# t-understand

Version **1.1.0** is an agent-native release of the complete Phase 1–20 platform.

The human-facing interface is the conversation inside OpenCode, Codex, Claude Code, or Cursor. The deterministic runtime, snapshots, evidence, memory, documentation, QnA, review, and quality artifacts are implementation details managed by the installed agent.

## Install

PowerShell:

```powershell
.\bin\install.ps1 -Target opencode
```

Replace an existing or modified installation:

```powershell
.\bin\install.ps1 -Target opencode -Force
```

Unix-like shells:

```bash
./bin/install.sh opencode
./bin/install.sh opencode --force
```

Supported targets:

```text
opencode
codex
claude-code
cursor
```

`-Force`/`--force` is explicit replacement authority. It rebuilds the package, replaces an existing managed or unmanaged installation, preserves previous files as backups, and writes a fresh ownership manifest.

Normal installation does not ask for:

- `ContextRoot`;
- package or installation IDs;
- a configuration target directory;
- a runtime command.

Advanced custom install location remains available through `-InstallRoot` or `--install-root`.

## Use

Open the desired repository in the selected agent host and ask normal questions, for example:

```text
Understand this repository and explain its architecture.
```

```text
How does the order creation flow work, and where is each claim proven?
```

```text
Generate technical documentation for this application.
```

```text
Review my current changes against HEAD and show only material findings.
```

```text
Which documentation became stale after these changes?
```

The agent automatically:

1. detects the active Git worktree;
2. bootstraps private state under `<workspace>/.t-understand/`;
3. excludes that directory from source snapshots and review;
4. creates internal operation IDs;
5. selects or captures immutable snapshots;
6. delegates to terminal `tu-*` agents and skills;
7. verifies evidence, freshness, critique, and output contracts;
8. explains the useful result in normal language.

The user is never expected to invoke the internal runtime or understand its storage layout.


## Multi-repository applications

Open any repository in an application workspace and explicitly refer to all repositories when you want application-level understanding:

```text
Treat all repositories in this workspace as one application. Understand them deeply and generate comprehensive documentation.
```

The agent discovers bounded sibling/child Git roots, creates one application workspace, stores managed state at the common root, captures one multi-repository snapshot, and generates application-level plus per-repository documentation.

## Deep business, domain, and flow documentation

Version 1.1.0 uses a requirements-driven adaptive plan. It starts from 41 mandatory documents, adds seven documents for every repository, creates deep Tier-1 flow documentation, and retains every lower-tier flow in the flow catalog. Publication requires 100% requirement, model-record, required-section, repository, flow, inference-disclosure, and traceability coverage.

Business intent is never invented from code. Repository boundaries, roles, enums, exceptions, and call graphs remain explicitly classified as candidates or partial evidence unless stronger evidence exists. Missing knowledge is documented as an unknown rather than silently omitted.

## Greeting and documentation behavior

A greeting-only message such as `hi` returns a concise capability card and does not start heavyweight analysis. A substantive request overrides the greeting prefix.

Explicit documentation requests are artifact-first. For example:

```text
Understand this repository deeply and write comprehensive documentation.
```

The agent runs the private understanding pipeline, writes multiple documents under:

```text
<workspace>/.t-understand/output/documentation/latest/
```

and returns only a concise completion summary in chat. A long chat-only documentation response is treated as incomplete. Build and test success are never claimed unless those commands were actually executed with captured evidence.

## Managed internal state

`.t-understand/` is tool-owned workspace metadata, not application source. It contains snapshot descriptors, extracted evidence, canonical memory, models, generated documentation, QnA bundles, review artifacts, and verification reports.

Rules:

- it is excluded from t-understand source inventory and review;
- it is never staged, committed, pushed, or modified through Git;
- agents may write there without asking for a storage location;
- internal paths and IDs are shown only when explicitly requested for diagnostics or reproducibility.

## Doctor and uninstall

PowerShell:

```powershell
.\bin\doctor.ps1 -Target opencode
.\bin\uninstall.ps1 -Target opencode
.\bin\uninstall.ps1 -Target opencode -Force
```

Unix-like shells:

```bash
./bin/doctor.sh opencode
./bin/uninstall.sh opencode
./bin/uninstall.sh opencode --force
```

Uninstall without force refuses to remove managed files that have been modified. Forced uninstall removes them and restores pre-install backups when present.

## Agent-native architecture

Installed platform packages contain:

- the `t-understand` root coordinator;
- ten terminal `tu-*` subagents;
- all namespaced `tu-*` skills;
- no-prompt local permission rules;
- the packaged deterministic engine under `t-understand-engine/`;
- schemas, policies, language adapters, and output templates.

The engine is invoked silently by the host agent. It is not a second human-facing entry point.

## Permission boundary

Inside the active working directory:

```text
read/search                         ALLOW
create/edit/delete/move             ALLOW
tools/shell/build/test/validate     ALLOW
per-operation approval prompt       DISABLED
```

Hard boundaries:

```text
outside working directory           DENY
gh commands                         DENY
mutating Git commands               DENY
read-only Git inspection            ALLOW
nested terminal-agent delegation    DENY
```

Broad tool permissions do not authorize t-understand to change application source. The only normal workspace write is managed `.t-understand/**` metadata. Suggested review patches remain advisory and are handed to `t-think` when implementation is approved.

## Capability set

- single-repo, monorepo, and multi-repo understanding;
- branch, tag, commit, HEAD, index, and worktree snapshots;
- eleven language and contract adapter families;
- structural and conservative behavioral analysis;
- multi-repository contract graph;
- canonical evidence, claims, conflicts, freshness, and invalidation;
- system and business modeling;
- technical and business documentation;
- Markdown, GitHub, Mintlify, Docusaurus, and MkDocs export profiles;
- source-cited QnA with direct snapshot verification;
- static and comparative code review;
- review critique, severity calibration, merge gates, and exporters;
- consolidated quality verification;
- provider-neutral cheap-model contract qualification;
- managed installers for OpenCode, Codex, Claude Code, and Cursor;
- deterministic release packaging and checksums.

## Core invariants

1. Human interaction is conversational.
2. Internal storage and operation IDs are never prerequisites for the human.
3. Application source is read-only to t-understand.
4. `.t-understand/**` is managed metadata and excluded from source evidence.
5. Git is read-only; `gh` is denied.
6. Implementation claims require revision-bound source evidence.
7. Facts, inferences, conflicts, unknowns, and stale knowledge remain distinct.
8. Workers are terminal and cannot delegate.
9. Suggested patches are never applied automatically.
10. A flagship model is never a hidden correctness dependency.

See `docs/agent-native-workflow.md`, `docs/platform-adapters-installation.md`, and `docs/tool-permissions-and-skill-namespace.md`.
