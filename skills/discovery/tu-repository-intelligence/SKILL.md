---
name: tu-repository-intelligence
description: Use Graphify first for focused structural repository discovery when a locally supported usable graph is available, then verify material findings from source and executable checks.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
  graphify_required: false
---

# tu-repository-intelligence

## Objective

Produce a small reusable repository-intelligence package before broad source exploration when structural discovery crosses files, modules, services, repositories, data flows, or integration boundaries.

## Decision procedure

1. Resolve the repository root using read-only Git top-level metadata when available; otherwise use the current working directory.
2. Decide whether structural discovery is useful. Return `not_needed` for a known exact file or symbol, a trivial localized or formatting-only task, build/test/lint execution, a user-provided authoritative path, generated or vendored code, or any task where graph traversal adds no meaningful value.
3. Before running a Graphify command, inspect the first locally available source in this order: installed Graphify skill documentation, Graphify-related `SKILL.md`, repository integration files, `graphify --help`, discovered subcommand help, or existing project scripts.
4. Never invent a Graphify command or graph path.
5. Mark Graphify `available` only when the executable or supported integration exists, the local integration confirms a usable graph, and the required read-only operation is permitted.
6. When available, perform only focused read-only queries needed for the objective. Do not load or paste a complete graph.
7. Record concise findings, affected areas, uncertainties, and direct verification requirements.
8. Verify implementation-critical findings from source, configuration, language-server or symbol resolution, compiler/type checker, build output, tests, schemas, migrations, dependency injection, messaging, and deployment configuration as applicable.
9. Treat reflection, dependency injection, dynamic dispatch, generated code, framework conventions, runtime configuration, event or message routing, database-side logic, plugins, and external systems as potentially incomplete graph relationships.
10. On unavailable Graphify, missing graph, staleness, permission denial, or query failure, continue immediately with normal source inspection, search, language-server, compiler, build, and tests. Mention Graphify only when the failure materially reduces confidence or completeness.

## Forbidden operations

- installing or upgrading Graphify;
- initializing Graphify;
- generating, mutating, updating, or rebuilding a graph;
- inventing subcommands or graph locations;
- treating a graph edge as final implementation authority;
- blocking the task solely because Graphify is unavailable or failed.

## Delegation output

When Graphify was evaluated, pass this concise optional structure:

```yaml
repository_intelligence:
  graphify_status: available | unavailable | not_needed | failed | possibly_stale
  repository_root: "<resolved root when relevant>"
  queries_performed:
    - "<focused query or locally documented read-only operation>"
  findings:
    - entity: "<entity or component>"
      relationship: "<relationship>"
      evidence: "<concise Graphify result>"
      confidence: high | medium | low
  affected_areas:
    - "<module, component, file, schema, event, or test area>"
  uncertainties:
    - "<unverified dynamic, runtime, or stale relationship>"
  verification_required:
    - "<source, test, build, configuration, or runtime check>"
```

Omit large raw output. Do not repeat an orchestrator query unless the delegated objective needs deeper information that was not supplied.
