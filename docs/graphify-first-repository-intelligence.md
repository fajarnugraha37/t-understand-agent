# Graphify-first repository intelligence

`t-understand` uses Graphify as an optional repository-intelligence layer. Graphify reduces broad source scanning for cross-file, cross-module, cross-service, data-flow, event-flow, and change-impact work. It never becomes a mandatory runtime dependency.

## Ownership

The canonical semantics live in `orchestrator/repository-intelligence-policy.yaml`. The shared `tu-repository-intelligence` skill implements that policy. `t-understand` performs the first availability decision and initial focused discovery. Terminal workers consume the resulting delegation context and run an additional focused query only when their bounded task needs information that was not already supplied.

Platform adapters do not carry independent Graphify logic. The installer already packages the canonical `orchestrator/**` tree, all `tu-*` skills, and source agent instructions for OpenCode, Codex, Claude Code, and Cursor.

## Availability

Graphify is usable only when all of these are true:

1. the repository root is resolved, preferring read-only Git top-level metadata and otherwise the current working directory;
2. a supported Graphify executable or integration exists;
3. the local integration confirms that a usable project graph is available;
4. the active agent may perform the required read-only operation.

Before invoking a command, the agent inspects local Graphify documentation, a Graphify `SKILL.md`, repository integration files, `graphify --help`, discovered subcommand help, or existing project scripts. The policy does not hardcode a graph path or invent a query command.

Availability checks are quiet. The user is not interrupted merely because Graphify is installed, absent, or skipped.

## Use Graphify first

Graphify is normally useful for:

- architecture and unfamiliar repository exploration;
- dependency relationships and call chains;
- request, execution, persistence, event, and message flows;
- cross-module and cross-repository behavior;
- producer-consumer and API-to-service-to-database paths;
- configuration relationships and implementation ownership;
- change impact across callers, consumers, modules, tests, schemas, migrations, deployment assets, and documentation.

Graphify is normally skipped for an exact known file or symbol, a trivial localized or formatting-only edit, build/test/lint execution, a user-provided authoritative path, generated or vendored code, or a task where graph traversal adds no material value.

## Verification boundary

Graphify findings are navigation and impact-analysis evidence. They are not final implementation authority.

Material conclusions are verified against source code, configuration, symbol resolution, compiler or type checker output, build output, tests, database schemas and migrations, dependency-injection wiring, messaging configuration, and deployment configuration as appropriate.

Static graph extraction may omit or incompletely represent reflection, dependency injection, dynamic dispatch, generated code, framework conventions, runtime configuration, event routing, message routing, database-side logic, plugins, and external systems. These remain visible uncertainties.

## Fail-open behavior

When Graphify is unavailable, the graph is missing, the graph may be stale, permission is absent, or a query fails:

1. do not stop the task;
2. continue with source inspection, search, language-server tooling, compiler/type checker, build, and tests;
3. mention the failure only when it materially reduces confidence or completeness;
4. never install or upgrade Graphify automatically;
5. never initialize, generate, mutate, update, or rebuild a graph automatically.

## Freshness

Treat graph findings as `possibly_stale` when relevant source changed after graph generation, the branch or revision differs materially, generated code or configuration changed, the integration reports stale data, or source contradicts the graph.

When staleness matters, verify directly from source, lower graph-derived confidence, preserve the uncertainty in delegation, and update the graph only under a separate explicit authorization and existing project policy.

## Delegation

When Graphify was evaluated, the delegation packet may include `repository_intelligence`:

```yaml
repository_intelligence:
  graphify_status: available
  repository_root: /workspace/application-a
  queries_performed:
    - focused producer-consumer query defined by the locally installed integration
  findings:
    - entity: OrderCreated
      relationship: produced-by and consumed-by candidates
      evidence: concise Graphify result; source verification still required
      confidence: medium
  affected_areas:
    - order-api
    - order-consumer
  uncertainties:
    - runtime topic remapping may exist in deployment configuration
  verification_required:
    - verify producer and consumer configuration from source
    - run relevant contract and integration tests
```

The package is concise and never contains a complete raw graph dump.

## Example workflow

```text
Cross-module feature request
    ↓
t-understand resolves scope and decides structural discovery is useful
    ↓
t-understand checks local Graphify usability quietly
    ↓
focused read-only Graphify impact query, when available
    ↓
concise findings + affected areas + uncertainties in delegation
    ↓
tu-modeler maps the implementation and validation surface
    ↓
source-owning implementation agent outside t-understand verifies and edits source
    ↓
tu-reviewer compares the diff with the expected impact surface
    ↓
tu-verifier uses source, compiler, and tests as final validation
```

`t-understand` itself remains source-read-only. Approved implementation changes continue to be handed to the appropriate source-writing system, such as `t-think`.
