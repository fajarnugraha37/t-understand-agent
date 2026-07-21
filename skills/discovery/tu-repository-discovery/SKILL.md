---
name: tu-repository-discovery
description: Execute the t-understand repository discovery workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-repository-discovery

## Objective

Discover repository shape, build roots, entry-point candidates, contracts, deployment assets, CI assets, and migrations from one validated immutable snapshot.

## Inputs

- `application-snapshot`;
- validated workspace resolution;
- discovery ID.

## Procedure

1. Enumerate snapshot files in deterministic path order.
2. Classify files without reading protected content.
3. Identify languages, build systems, module roots, entry-point candidates, contracts, deployments, CI, and migrations.
4. Emit repository and application coverage ledgers.
5. State unsupported or excluded constructs explicitly.

## Outputs

- `application-discovery`;
- one `repository-discovery` per repository.

## Boundaries

This skill does not infer call graphs, runtime behavior, or business intent.
