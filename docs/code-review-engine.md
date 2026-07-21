# Code Review Engine

Review targets are created from immutable snapshots and normalized as `STATIC_AUDIT` or `DIFF`. Runs are stored under `review-runs/<RVW-ID>/`. Full-audit coverage and diff changed-file ledgers are explicit. Major-or-higher findings survive an evidence challenge before publication. Source repositories and Git are read-only.
