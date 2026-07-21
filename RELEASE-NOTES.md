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
