# Reconciliation negative control

This is a disposable mutation of the writer's archived TJS-996 bundle, made
outside both repository worktrees. In both runs, `rolled_back.key_images` was
changed from `[2, 2]` to `[0, 0]` and `rolled_back.pools` from `[[txid], [txid]]`
to `[[], []]` in `public/result.json` and the `reorg_key_image_rollback` event.
The two edited file hashes were recomputed in `MANIFEST.sha256`; all other files
were copied unchanged. No altered receipt is included in this QA bundle.

Against the exact candidate checkout, the writer's
`vanguard/verify-daemon-p2p.py` returned exit 0 and printed
`PASS_DAEMON_P2P_RECEIPT_RECONCILIATION`; `sha256sum --status -c`
also returned 0. The independent
`research/qa_vanguard_daemon_p2p_tjs1003.py` returned exit 1 at its exact
`[2, 2]`/two-pool assertion. The captured stdout/stderr is in
`negative-rollback-verifier.log` and `negative-rollback-qa.log`.

This demonstrates that the writer verifier's PASS marker alone does not prove
the requested confirmed-to-pooled rollback. The original and independently
reproduced unmodified receipts each do show `[2, 2]` and the transaction in
both pools, as the QA oracle outputs record.
