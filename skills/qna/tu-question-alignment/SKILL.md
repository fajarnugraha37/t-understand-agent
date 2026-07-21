---
name: tu-question-alignment
description: Execute the t-understand question alignment workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-question-alignment

Normalize the human question, application scope, timeframe, expected answer form, and ambiguity. Do not answer the question in this control phase. Missing semantic scope is returned to the human rather than guessed.
