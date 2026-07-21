# Documentation Exporters

Phase 12 provides five presentation profiles while preserving canonical semantics:

- `plain-markdown`
- `github-markdown`
- `mintlify-mdx`
- `docusaurus-mdx`
- `mkdocs-markdown`

Exports are immutable and bound to the canonical docset manifest digest. Exporters may change file extensions, navigation, and renderer configuration, but may not change classifications, claims, evidence, or traceability.

## Profile outputs

Plain Markdown produces `SUMMARY.md`. GitHub produces a repository-friendly `README.md`. Mintlify produces MDX documents and `docs.json`. Docusaurus produces MDX and `sidebars.js`. MkDocs produces Markdown and `mkdocs.yml`.

## Validation boundary

The runtime validates export schemas, checksums, required profile configuration, Markdown fence balance, front matter, and relative links. It parses generated JSON and YAML configuration. This is deterministic structural qualification; it does not claim that third-party hosted build services were executed.
