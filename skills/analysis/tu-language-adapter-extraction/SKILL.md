---
name: tu-language-adapter-extraction
description: Execute the t-understand language adapter extraction workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-language-adapter-extraction

## Objective

Apply the highest-scoring deterministic language or contract adapter to each included inventory file.

## Inputs

- validated discovery artifact;
- immutable snapshot content;
- canonical adapter manifests.

## Procedure

1. Verify file SHA-256 against inventory.
2. Select a specialized adapter by detection score and stable priority.
3. Fall back to `generic` only when no specialized adapter qualifies.
4. Extract surface declarations, dependencies, interface candidates, configuration keys, and entry points.
5. Record `PARTIAL` or `UNSUPPORTED` instead of guessing.

## Outputs

- `adapter-extraction` JSONL;
- `adapter-run` summary;
- capability matrix on request.

## Boundaries

No macro execution, runtime loading, source generation, semantic call graph, or business inference is performed.
