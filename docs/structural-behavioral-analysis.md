# Structural and Behavioral Analysis

Phase 7 converts validated adapter extraction records and immutable snapshot content into evidence-bound technical understanding.

## Inputs

- one validated adapter extraction;
- its validated discovery artifact;
- its immutable application snapshot;
- optional repository/path scopes;
- optional base analysis for incremental refresh.

## Canonical outputs

- `structural-analysis.yaml`;
- `behavior-analysis.yaml`;
- `evidence.jsonl`;
- `entities.jsonl`;
- `relations.jsonl`;
- `observations.jsonl`;
- `analysis-run.yaml`.

## Epistemic behavior

Exact syntax, annotations, API calls, literal contract keys, literal SQL relations, and explicit failures are `OBSERVED`. Lexical calls that cannot be target-resolved are retained as medium-confidence `INFERRED` relations. The analyzer does not infer business purpose.

Every entity, relation, and observation references at least one evidence record. Evidence records bind application snapshot, repository, commit revision, relative path, SHA-256, and source locator.

## Incremental refresh

`analysis-refresh` compares file digests between a base analysis and candidate extraction. It:

1. identifies added, modified, and deleted paths;
2. removes records whose evidence belongs to changed paths;
3. rebinds unchanged evidence to the candidate snapshot and revision;
4. analyzes changed and added files;
5. publishes one new immutable analysis version.

The test suite compares normalized incremental and full records for semantic equivalence.

## Safety

- source execution is denied;
- source writes are denied;
- captured content must match the extraction SHA-256;
- publication uses a temporary directory and atomic rename;
- tampered artifact hashes fail validation.
