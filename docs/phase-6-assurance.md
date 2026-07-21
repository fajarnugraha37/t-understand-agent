# Phase 6 Assurance — Language and Contract Adapters

Phase 6 implements eleven deterministic, snapshot-bound adapters with stable selection and a generic fallback.

The adapters cover Java, JavaScript/TypeScript, Python, Go, Rust, .NET, SQL, BPMN/DMN, OpenAPI/AsyncAPI, Dockerfile/Kubernetes/Terraform, and generic text. Every extraction retains the exact source file SHA-256 and explicit limitations.

Evidence is recorded in `reports/discovery-contract-report.json`, `reports/adapter-test-report.json`, `reports/discovery-cli-report.json`, and `reports/phase-6-summary.json`.

The adapters provide syntax and contract surface extraction. Semantic behavior analysis begins in Phase 7.
