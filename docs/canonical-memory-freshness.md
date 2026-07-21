# Canonical Memory and Freshness

Phase 9 consolidates validated analysis and graph artifacts into immutable, application-scoped memory versions.

## Canonical versus runtime data

Canonical records:

- evidence;
- entities;
- intra- and cross-repository relations;
- claims;
- conflicts;
- invalidation ledger.

Runtime accelerators:

- SQLite index;
- FTS5 table when available;
- LIKE-search fallback.

Runtime indexes are always rebuildable from canonical JSONL and are never source of truth.

## Claim rules

- `FACT` requires current evidence and deterministic reasoning;
- `INFERENCE` requires supporting evidence and explicit reasoning;
- `CONFLICT` preserves incompatible supported claims;
- stale memory cannot support an unqualified current fact;
- duplicate providers are not resolved by arbitrary precedence.

## Freshness

A memory version is current only for the exact application snapshot from which it was built and only when its status is `CURRENT`. A different snapshot is stale until digest comparison and refresh occur.

## Invalidation

`memory-invalidate` compares canonical evidence file digests with a candidate discovery inventory. It reports:

- added paths;
- modified paths;
- deleted paths;
- invalidated evidence IDs;
- affected entity IDs;
- affected relation IDs;
- affected claim IDs.

The report is immutable and does not mutate the base memory version.

## Conflict behavior

Conflicts are first-class records. The current implementation detects duplicate HTTP provider contracts across repositories. Future phases may add business, deployment, schema, and documentation conflicts without changing the core conflict contract.
