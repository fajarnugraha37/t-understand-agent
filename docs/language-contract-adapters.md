# Language and Contract Adapters

Phase 6 provides eleven deterministic adapters:

1. generic text fallback;
2. Java;
3. JavaScript and TypeScript;
4. Python;
5. Go;
6. Rust;
7. .NET languages;
8. SQL;
9. BPMN and DMN;
10. OpenAPI and AsyncAPI;
11. Dockerfile, Kubernetes, and Terraform infrastructure.

Each adapter has a canonical manifest under `language-adapters/<id>/adapter.yaml`. The manifest declares its version, priority, detection patterns, capability levels, fallback status, and runtime implementation.

## Selection contract

```text
all adapters detect
→ highest score
→ highest stable priority
→ lexicographically smallest adapter ID
→ generic fallback
```

Specialized adapters require a detection score of at least 50. The selection algorithm is deterministic and does not use an AI model.

## Extraction contract

Every record is bound to:

- extraction ID;
- snapshot ID;
- repository ID;
- repository-relative path;
- exact file SHA-256;
- adapter ID and version.

Adapters emit surface declarations, dependencies, interface candidates, configuration keys, entry points, status, and limitations. `PARTIAL` and `UNSUPPORTED` are valid outcomes; unsupported constructs are never silently promoted to facts.

## Cheap-model behavior

File selection, parsing, ordering, hashing, and schema validation are mechanical. A cheap model receives compact extraction records rather than entire repositories. Later reasoning phases can therefore use evidence slices without making model quality a hidden integrity dependency.
