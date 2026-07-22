# Skills

The complete skill catalog, ownership, status, and workflow mapping remain canonical in `orchestrator/skill-registry.yaml`.

All globally discoverable skills use the `tu-*` namespace and contain validated `SKILL.md` frontmatter. The installer packages the complete skill tree for OpenCode, Codex, Claude Code, and Cursor.

## Shared repository intelligence

`skills/discovery/tu-repository-intelligence/` implements the canonical optional Graphify-first navigation policy from `orchestrator/repository-intelligence-policy.yaml`.

`t-understand` owns the initial Graphify usability decision and focused structural discovery. Terminal workers consume concise findings through the optional delegation context and perform additional focused read-only queries only when their bounded objective needs evidence that was not supplied.

Graphify remains optional and fail-open. The skill does not install, initialize, generate, mutate, update, or rebuild Graphify and never treats graph output as final implementation authority.

## Shared Ponytail-first engineering

`skills/foundation/tu-ponytail-engineering/` implements the canonical smallest-complete-solution policy from `orchestrator/ponytail-engineering-policy.yaml`.

`t-understand` owns the initial decision ladder and passes an optional `ponytail_context` containing the required outcome, preserved behavior, selected solution, alternatives checked, approved abstractions or dependencies, non-goals, risks, and verification requirements. Terminal workers reuse those decisions and reopen them only when new evidence invalidates them.

External Ponytail integration is optional. The shared skill never installs or upgrades Ponytail and never invents commands, files, hooks, modes, or platform support. Without a local integration, the canonical policy is applied directly.

Ponytail-first does not mean shortest code at any cost. Correctness, security, data integrity, contracts, compatibility, compliance, observability, operational safety, performance, maintainability, and material testability remain authoritative.

## Implementation status

A registry entry is marked `implemented` only after its runtime substrate, schema or deterministic contract, tests, and documentation exist. A skill package is not a placeholder: it must remain aligned with its owner agent, authority boundaries, platform packaging, and deterministic validators.
