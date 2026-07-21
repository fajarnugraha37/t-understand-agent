# Documentation generation

`t-understand 1.1.0` generates documentation as validated artifacts rather than as a long chat response.

## Pipeline

```text
application workspace resolution
→ multi-repository snapshot
→ discovery and language/contract extraction
→ structural and behavioral analysis
→ cross-repository graph
→ canonical memory
→ system/business/domain/flow models
→ documentation requirements
→ adaptive document plan
→ document generation
→ section traceability
→ completeness ledger
→ critique and verification
→ atomic stable publication
```

## Output

The canonical immutable docset is stored under `.t-understand/documentation/canonical/<docset>/`. The stable human-facing copy is published under `.t-understand/output/documentation/latest/`.

The mandatory base catalog contains 41 documents. Runtime planning adds seven documents per repository and additional Tier-1/Tier-2 flow documents. Tier-3 flows remain fully represented in the flow catalog.

## Completeness

Every run emits a requirements ledger before drafting and a generation ledger after drafting. Their requirement-ID sets must match exactly. Coverage for requirements, model records, required sections, repositories, and flows must be `1.0`. Supported sections must resolve to claims and evidence. Business inference must disclose its limitations.

A large repository or document count does not permit truncation. The generator processes the plan deterministically and sequentially when necessary. An area without sufficient evidence is documented as unknown or partial rather than omitted or fabricated.

## Quality

The critique rejects unsupported claims, stale supported sections, missing required headings, placeholders, shallow sections/documents, and duplicate content. The verifier checks schemas, digests, checksums, links, traces, requirement/generation equality, and all coverage thresholds.

Builds and tests are not executed by documentation generation unless separately requested; therefore their success is never claimed from command discovery alone.
