# Superseded for two claims (2026-09-18)

The observed-exposure request recordings in this directory remain valid and were
independently MANIFEST-verified by the studio lead at `1ab38af`.

Two claims from this first run are **superseded** by
`research/evidence/wallet-transport-2026-09-18b/` after TJS-41 acceptance findings:

1. **Trust mode.** This run omitted `--trusted-daemon` and called the boundary
   "untrusted". Per `src/wallet/wallet2.cpp` `make_basic`, a local (127.0.0.1)
   daemon is auto-trusted unless a trust flag is given, so this run was actually
   **trusted**. The successor run sets an explicit `--untrusted-daemon` and
   verifies untrusted mode at runtime (`rescan_spent` rejected with
   "This command requires a trusted daemon.").

2. **Denial/recovery.** This run recorded `wallet_observed_failure = "refresh
   returned daemon error; no crash"` although the refresh RPC did **not** raise
   (`failure` was `None`) — an asserted error with no evidence. The successor run
   classifies the wallet's reaction strictly from evidence (raw RPC reply +
   recorded post-denial retries); the actual behavior is a **transparent retry**
   with no client-side error, and recovery is asserted only against the recorded
   retry.

The observed request paths / first-relay-origin recording here are not superseded.
