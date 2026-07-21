---
name: tu-capability-help
description: Render repository-aware greeting, help, and capability details without starting a heavyweight analysis workflow.
compatibility: t-understand, opencode, codex, claude-code, cursor
metadata:
  owner: t-understand
  source_write: denied
---

# tu-capability-help

## Objective

Respond to greeting-only and explicit help prompts using the canonical capability catalog.

## Rules

- Do not start repository discovery, analysis, memory, documentation, QnA, or review for a greeting-only prompt.
- A substantive request overrides a greeting prefix.
- Show user outcomes, not internal skill names or runtime commands.
- Detect only lightweight workspace status: no workspace, new repository, or known repository.
- Keep the default greeting to seven capabilities or fewer and include example prompts.
- Follow the human's conversation language when the host can determine it.
