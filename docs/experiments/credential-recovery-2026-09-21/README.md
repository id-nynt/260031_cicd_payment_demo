# Credential startup and pending-record recovery

The original campaign failed before HTTP transmission while constructing its Authorization header. An invalid token input contained a control character. Older code recorded the local exception as uncertain and retained a pending dispatch, which blocked subsequent campaigns. The old JSON logger also failed to escape that character.

Changes: validate live repository/token inputs before campaign creation; independently validate token characters in Java before dispatch state is created; serialize all JSON control characters correctly; extend explicit legacy evidence recovery to recognize the exact invalid Authorization-header exception. Only the migration reader tolerates historical unescaped control characters. Original bytes and pending state are archived before settlement. Network uncertainty, missing runs, foreign campaign evidence and acknowledged runs remain protected.

The actual record was settled without network requests in the recovery campaign listed in `recovery-summary.json`. Its archived journal is byte-identical to the original. The repository-wide pending file is no longer present. No live workflow, deployment, push or merge was performed during recovery.

Validation: 41 Python tests and 29 Java tests passed. Tests cover malformed tokens without secret echo/network requests, raw-control-character historical evidence, rejection of insufficient evidence, and valid JSON logging. Persistent artifact validation passes; no model/agent regeneration is needed because the generic policy and generator inputs did not change.

Live build-only verification requires an authenticated GitHub CLI session. The published worker tag `bdi-worker-20260921-052412` was confirmed, but the available session returned HTTP 401 for `/user`. The user was asked to authenticate without sharing a token in chat. A build-only project was generated locally under `runs/connection-check-project`; it cannot select deployment jobs.

A real Jason smoke campaign with simulated adapters also reached achieved; its journal parsed successfully and contained exactly one terminal event (`runs/credential-fix-smoke`).
