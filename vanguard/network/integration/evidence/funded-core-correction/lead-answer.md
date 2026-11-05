Lead decision, TJ may reverse: adopted as proposed, with two required witnesses.

Core's two P1 findings are real, and they were caught before a 4-hour native run, which is exactly what the serial consultation is for.

**Scope.** You, from clean 68963718, in `vanguard/network/` only. One implementation pass plus at most one correction pass, at most 45 minutes from the first edit. Changes are limited to the funded driver and its closed contract, connected tests, pinned source bindings and audit, the affected operator and item-5 matrix documentation, and the required frozen inventories and evidence. The genesis driver and evidence, build.sh/freezer, compiled identity, overlay, pins, shared writers, auth/privacy/redactor, workload, caps, deadlines and retained authority are all unchanged.

**F1 – N60 refusal.** Expect the active CARROT path's `-4` (`not_enough_usable_money` mapped at `wallet_rpc_server.cpp:3925-3928`). A bare `-4` is not a maturity proof, so the refusal row also requires all of the following at N60:
- The sender wallet reports the b1 coinbase as received (total balance > 0) and unlocked balance = 0, with that output's exact unlock = 61 lineage.
- No tx result is returned, both daemon pools are still empty, and the chain height is unchanged by the attempt.
- The same request succeeds at N≥61, with the exact output and key-image lineage.

Any other code, early success, a lineage mismatch or a pool change fails. Reproduce the known-bad `-37` expectation on 68963718.

**F2 – light mode.** Set `MONERO_RANDOMX_UMASK=4` (RANDOMX_FLAG_FULL_MEM, which pinned `rx-slow-hash.c:109,230-234,278,330` honours) in every funded daemon child environment. Bind the `light_mode=true` witness to the actual launch environment of every daemon start, including B's restart, so it can never be unconditional. A launch without the mask fails before the daemon starts. Leave the genesis driver's environment as accepted. Reproduce the known-bad unconditional witness on 68963718. This also protects the 4 GiB container: two full datasets alone exceed it.

**Then.** Focused and full source checks, refreeze/check, commit and an exact packet with failures attributed. Reviews run serially: Platform on the changed source, then Core on F1 semantics, then Security on signer, credentials and export. A same finding failing twice comes back to me. Only after all three ACCEPT does Platform issue the fresh 15,000 s detached runtime-only `--reuse-build` grant on the published 3eedebc0/1b2815e2 authority, with every condition from 058ab9ae (including the no-heavy-lock-conflict confirmation). All older grants stay consumed.

Core decision 47234b59 (count 2) is unchanged; no formal Core until F1 native PASS. launch_ready=false; public_launch=false. Needs TJ: None.
