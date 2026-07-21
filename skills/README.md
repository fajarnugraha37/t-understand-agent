# Skills

The complete skill catalog, ownership, status, and workflow mapping remain canonical in `orchestrator/skill-registry.yaml`.

All globally discoverable skills use the `tu-*` namespace and contain validated `SKILL.md` frontmatter. The installer packages the complete skill tree for OpenCode, Codex, Claude Code, and Cursor.

## Shared repository intelligence

`skills/discovery/tu-repository-intelligence/` implements the canonical optional Graphify-first navigation policy from `orchestrator/repository-intelligence-policy.yaml`.

`t-understand` owns the initial Graphify usability decision and focused structural discovery. Terminal workers consume concise findings through the optional delegation context and perform additional focused read-only queries only when their bounded objective needs evidence that was not supplied.

Graphify remains optional and fail-open. The skill does not install, initialize, generate, mutate, update, or rebuild Graphify and never treats graph output as final implementation authority.

## Implementation status

A registry entry is marked `implemented` only after its runtime substrate, schema or deterministic contract, tests, and documentation exist. A skill package is not a placeholder: it must remain aligned with its owner agent, authority boundaries, platform packaging, and deterministic validators.
