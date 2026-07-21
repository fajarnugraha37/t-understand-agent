# Phase 13 Assurance — QnA Engine

Phase 13 implements immutable, snapshot-aware QnA bundles. Retrieval is deterministic over canonical claims and evidence. Answers distinguish facts, inferences, conflicts, stale knowledge, and unknowns. Every non-unknown answer includes claim IDs and evidence citations; unsupported questions return UNKNOWN rather than a guess. Bundles include retrieval, direct-source verification, answer, critique, citation validation, Markdown rendering, checksums, tamper detection, and atomic rollback.

Implemented CLI: `qna-ask`, `qna-show`, `qna-answer`, `qna-list`, `qna-validate`, `qna-critique`.
