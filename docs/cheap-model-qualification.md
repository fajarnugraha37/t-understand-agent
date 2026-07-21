# Cheap-Model Qualification

Phase 17 provides a provider-neutral contract qualification harness for the execution guarantees used by `t-understand`.

## Profiles

```text
economy
balanced
deep-analysis
```

## Contract scenarios

```text
bounded-context
structured-output
evidence-citation
critic-loopback
unknown-not-guess
review-finding-proof
```

The built-in `contract-simulator` verifies deterministic task envelopes, required structured fields, evidence obligations, critic separation, unknown handling, and finding-proof requirements. It does not invoke an external AI model.

Every matrix row therefore records:

```yaml
runner: contract-simulator
live_model_tested: false
```

No provider or model may be described as qualified until a future live runner records the provider, model identifier, version, configuration, test corpus, and observed results.

## Output

```text
<context-root>/qualification/runs/<QUAL-ID>/
├── qualification-report.yaml
└── qualification-manifest.yaml
```

Reports are immutable, schema-validated, digested, and atomically published.

## CLI

```bash
t-understand --context-root /path/to/context \
  qualification-run --qualification-id QUAL-BASELINE

t-understand --context-root /path/to/context qualification-matrix
```

Other commands are `qualification-show`, `qualification-list`, and `qualification-validate`.
