# t-understand 1.1.2

`t-understand` 1.1.2 fixes the OpenCode execution contract for deep documentation workflows that legitimately run longer than the shell tool's default 120-second timeout.

## Long-running documentation execution

- The installed `agent_runtime.py` emits an immediate stderr heartbeat when `agent-document` starts.
- A recurring heartbeat is emitted every 15 seconds while evidence collection, modeling, document generation, and validation remain active.
- The final machine-readable completion remains on stdout; heartbeat lines are liveness diagnostics only.
- OpenCode instructions require a shell-tool timeout of at least `1800000` milliseconds for `agent-document` and explicitly prohibit the default `120000` millisecond timeout.

## Real end-to-end qualification

- CI now installs the generated OpenCode engine into a clean temporary target.
- It creates and commits a representative Java repository containing a valid OpenAPI 3 server-object declaration and more than one hundred source files.
- It executes the exact installed command `agent_runtime.py agent-document --prompt ...`.
- It requires an immediate heartbeat, final JSON completion, at least the mandatory 41-document catalog, and the published documentation manifest, plan, coverage, and validation artifacts.
- The same end-to-end scenario runs on both `ubuntu-latest` and `macos-latest` with an explicit 120-second completion bound for the representative fixture.

## Installation

The patch release uses version `1.1.2`. Upgrading an existing managed installation requires `./bin/install.sh opencode --force`; user-owned `AGENTS.md` content is preserved and the existing t-understand managed block is replaced rather than duplicated.

---

# t-understand 1.1.1

`t-understand` 1.1.1 fixes repository-wide documentation generation failures caused by valid structured OpenAPI and AsyncAPI server declarations.

## Documentation extraction reliability

- OpenAPI 3 `servers` lists are normalized from server objects using their URL and description.
- AsyncAPI named server maps preserve the logical server name together with URL, protocol, protocol version, and description evidence.
- Swagger 2 host, base path, and schemes are retained as server evidence.
- Adapter item values are defensively converted to deterministic bounded text instead of assuming every parser value is already a string.
- An unexpected failure in one file extractor now produces a `PARTIAL` evidence record with an explicit limitation rather than aborting the complete repository workflow.
- Extraction failures are contained at the file boundary, so the OpenAPI failure reported for `qando-docflow` no longer leaks its Python traceback or prevents the remaining repository from being analyzed.

## Agent invocation and response handling

- OpenCode instructions now require the exact `agent-plan --prompt` and `agent-document --prompt` forms and prohibit positional prompt invocation.
- Private retries, investigation notes, raw tracebacks, and internal progress narration are explicitly excluded from the final response contract.

## Installation

The patch release uses version `1.1.1`, ensuring a new engine package is generated instead of reusing the previous `1.1.0` payload. Upgrading an existing managed installation requires `./bin/install.sh opencode --force`; the managed-block installer preserves user-owned `AGENTS.md` content and replaces the t-understand block without duplication.

---

# t-understand 1.1.0

`t-understand` 1.1.0 adds agent-native multi-repository application discovery and a requirements-driven deep documentation system for business, domain, and application flows.

## Multi-repository application bootstrap

A human can open one child repository or an application parent and ask the agent to treat all repositories as one application. The agent resolves bounded sibling/child Git roots, infers conservative repository roles, initializes one application manifest, stores `.t-understand/` at the common application root, and captures one snapshot containing every repository-local revision.

Existing application workspaces are reused automatically. Normal single-repository prompts remain single-repository unless multi-repository scope is explicit or already registered.

## Adaptive documentation plan

The fixed 13-document catalog is replaced by a requirements-driven plan:

- 41 mandatory application/business/domain/flow/integration/data/operations/reference documents;
- seven documents repeated for every repository;
- five deep documents for each Tier-1 flow;
- one complete document for each Tier-2 flow;
- catalog coverage for every Tier-3 flow.

Every document has a stable requirement ID, unique path, scope, required headings, source-model set, and generation mode. A generation ledger must contain exactly one successful record for every requirement.

## Deep business and domain modeling

The model catalog now includes goals, capabilities, processes, actors, rules, policies, controls, domain overview, bounded contexts, aggregates/entities, value objects, invariants, domain services, commands, domain events, states, decision tables, ownership boundaries, flow failures, consistency, observability, and repository models.

Anti-hallucination rules prevent these invalid promotions:

- repository → confirmed bounded context;
- role/permission → confirmed business persona;
- enum → complete state machine;
- exception → confirmed business policy;
- call graph → complete application flow;
- discovered build/test command → passed execution.

Missing business intent remains an explicit unknown. Business inference requires evidence and a visible limitation.

## Multi-perspective application flows

Important flows are documented across intent, trigger, participants, repository attribution, sequence, sync/async boundaries, state/data impact, transactions/consistency, failures/recovery, security, observability/operations, evidence, and unknowns.

Flow depth is risk-sensitive and scales without silently truncating the plan.

## Completeness and quality gates

Stable publication is denied unless all mandatory metrics equal `1.0`:

- requirement coverage;
- model-record coverage;
- required-section coverage;
- repository coverage;
- flow coverage;
- inference disclosure;
- supported-section traceability.

The verifier also rejects missing documents, missing headings, unsupported facts, stale supported content, duplicate IDs/paths/content, shallow sections/documents, placeholders, broken links, checksum mismatches, and planned/generated requirement differences.

## Preserved guarantees

- conversation-only normal use;
- application source read-only;
- Git inspection-only and `gh` denied;
- `.t-understand/**` excluded from source evidence and Git mutation;
- immutable snapshots, memory, models, and canonical docsets;
- concise chat completion with documentation written as files;
- no build/test pass claims without execution evidence;
- private reasoning and internal IDs remain hidden.
