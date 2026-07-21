# Phase 18 Assurance — Platform Adapters and Installation

Status: **PASS**, requalified for v1.1.0.

Phase 18 implements private package generation and managed installation for OpenCode, Codex, Claude Code, and Cursor.

v1.1.0 evidence:

- `reports/installation-contract-report.json`: 186 checks PASS;
- `reports/installation-test-report.json`: 12 tests PASS;
- 68 canonical skills and the Codex aggregate skill use the `tu-*` namespace;
- generated packages contain no interactive permission `ask` fallback;
- OpenCode uses explicit allow/deny frontmatter;
- Claude and Cursor JSON permissions are merge-safe and exactly restored on uninstall;
- Codex includes non-interactive approval, workspace-write isolation, and forbidden `gh`/Git-mutation rules;
- exact ownership and checksum manifests;
- source/context target rejection;
- collision backup, doctor, modified-file refusal, forced removal, restoration, and private-engine package tests;
- shell and PowerShell installation wrappers.

External OpenCode, Codex, Claude Code, and Cursor executables were not invoked. Package layouts, private resources, installation behavior, and permission configurations were structurally validated by t-understand.
