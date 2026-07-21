# Release Qualification

Phase 20 is the final release gate; v1.0.2 requalifies the complete v1.0.0 platform after agent-native UX, installer, namespace, and permission hardening. It does not implement another analysis capability; it proves that the complete source tree, registries, reports, adapters, and package are coherent.

## Release gates

- `VERSION` is exactly `1.0.2`;
- Phase 16 quality tests pass;
- Phase 17 qualification tests pass;
- Phase 18 installation tests pass;
- Phase 19 integration matrix passes;
- all four platform adapters are present;
- every canonical and aggregate skill has YAML frontmatter and a `tu-*` name;
- generated platform packages have no interactive `ask` fallback;
- Python cache artifacts are absent from the release tree;
- release qualification report validates;
- software bill of materials validates;
- checksum inventory passes;
- ZIP integrity passes;
- two builds from identical input are byte-for-byte equal;
- critical validation is repeated from an extracted archive.

## Release artifacts

```text
reports/release-qualification.json
reports/software-bill-of-materials.json
CHECKSUMS.sha256
t-understand-v1.0.2-agent-native-bundle.zip
```

The software bill of materials records path, SHA-256, and size for release files, plus declared Python dependencies.

## Explicit non-claims

- The provider-neutral qualification harness does not claim that a live commercial or open-weight model was tested.
- Documentation exporters do not claim execution by hosted third-party renderer services.
- Review exporters do not claim remote submission to GitHub or GitLab APIs.
- Platform permission files are structurally validated; external OpenCode, Codex, Claude Code, and Cursor executables are not invoked by this release harness.
