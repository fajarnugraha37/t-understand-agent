# Runtime example

This example shows the Phase 2 control-plane sequence. Phase 3 now supplies real application and workspace resolution artifacts, while immutable snapshots and source-analysis artifacts remain assigned to later phases.

```bash
ROOT=/path/to/t-understand
RUNTIME=/tmp/t-understand-example

cat > /tmp/application-alignment.yaml <<'YAML'
application_id: application-a
status: aligned
YAML

$ROOT/bin/t-understand --runtime-root "$RUNTIME" init \
  --work-id APPLICATION_A_001 \
  --workflow foundation \
  --snapshot APP-SNAPSHOT-PENDING \
  --profile economy

$ROOT/bin/t-understand --runtime-root "$RUNTIME" complete \
  --work-id APPLICATION_A_001 \
  --artifact application-alignment=/tmp/application-alignment.yaml

$ROOT/bin/t-understand --runtime-root "$RUNTIME" route \
  --work-id APPLICATION_A_001
```

The final command creates a depth-one delegation packet for `tu-discoverer` under:

```text
$RUNTIME/APPLICATION_A_001/delegations/
```
