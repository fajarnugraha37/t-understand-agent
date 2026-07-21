# Runtime CLI Reference

Global option:

```text
--runtime-root PATH
```

It must appear before the subcommand and is required for every work-item command. This prevents implicit writes inside a source repository. Standalone `workflows`, `validate-packet`, and `validate-result` do not require it.

## Commands

### `workflows`

Lists workflow IDs, initial states, terminal states, and state counts.

### `init`

Creates a new work item.

```bash
t-understand --runtime-root /path/to/context/runtime init --work-id WORK_ID --workflow foundation --snapshot SNAPSHOT_ID --profile economy
```

### `status`

Returns persisted state plus derived owner, skill, expected outputs, and terminal status.

### `route`

For root-owned states, returns the required human/orchestrator action. For worker states, creates or returns the active delegation packet.

### `complete`

Completes an orchestrator-owned state using an exact `TYPE=PATH` artifact set.

### `accept-result`

Validates and accepts a worker result envelope. It advances, blocks, or loops back according to the result status.

### `record-approval`

Records a human approval or rejection. Rejection requires a valid earlier loopback target.

### `resume`

Resumes a blocked work item without silently advancing its state.

### `validate-work`

Revalidates state, active delegation, artifact existence, and artifact digests.

### `validate-packet` and `validate-result`

Validate standalone delegation and result files against their runtime schemas.
