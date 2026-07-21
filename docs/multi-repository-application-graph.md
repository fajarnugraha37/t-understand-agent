# Multi-Repository Application Graph

Phase 8 creates evidence-backed links across repositories without relying on folder position or model intuition.

## Automatic promotion rules

### Events

An event producer and event consumer are linked when both name the same exact topic key in different repositories.

### HTTP

An HTTP consumer and provider are linked when both name the same exact method and path, and exactly one provider repository exists. Multiple provider repositories are ambiguous and are not promoted.

### Dependencies

An explicit dependency is linked only when it exactly matches one declaration in another repository.

### Shared data

A writer and reader naming the same literal data relation may be linked as `INFERENCE` with medium confidence. This does not establish ownership or runtime deployment topology.

## Unresolved candidates

One-sided, ambiguous, or unmatched contract surfaces remain in `unresolved-candidates.jsonl`. This is intentional evidence preservation, not a failure to produce an answer.

## Guarantees

- every cross-repository edge has evidence from both endpoints;
- source and target repositories differ;
- identifiers and ordering are deterministic;
- graph publication is atomic;
- graph validation checks evidence and entity references;
- no graph output writes to source repositories or canonical memory.
