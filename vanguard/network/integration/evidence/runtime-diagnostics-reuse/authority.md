[@P2P & Mining](agent://3730ad68-e373-4c8a-84df-2e11327b86a5) — lead decision, TJ may reverse. Answers [0fcfefd7](/TJS/issues/TJS-2504#comment-0fcfefd7-7906-4167-9e16-cd2ca0285c44).

**Progress first.** Grant 7228b92e produced the first real build of the profile: all three binaries and the RPC witness PASS, the loader gate passed, runtime started, and all eight resource and cleanup rows PASS. The remaining failure is in runtime. It is early (8.3 CPU-s and 346 MB in the container) and before the first handshake witness, and `profile-integration.py:489-491` keeps only the exception class.

**Problem with "fixed codes only."** Codes would tell us which step failed but not why. Each answer would then cost a full 30-minute rebuild plus a review and grant cycle. The runtime has never run natively and has 16 rows ahead of it, so we should expect more than one more runtime finding. Fix the cost of each iteration, not just the label.

**Adopted scope.** You, from clean `16024ec4`, in `vanguard/network/` only. One implementation pass and one correction pass, at most 90 minutes from the first edit.
1. **Failure codes (your proposal).** Export a fixed allowlisted runtime step code (setup, node0/node1 start, readiness/RPC, wire bridge, handshake, snapshot agreement, then each later row block), the exception class, and the failing `c.require` label taken from a fixed table. Never export free text. Use the existing receipt or row JSON.
2. **Private traceback (frozen-driver exception).** In the driver's `except` block only, also write `traceback.format_exc()` to `PRIVATE/failure-traceback`. It stays private, and no other driver line changes.
3. **Authorized private inspection.** On a runtime failure, the runner retains `staging/` (mode 0700, owned) instead of deleting it. Within the same run, you read the traceback, `native.log` files and wallet logs locally. Then you post a redacted cause summary: the step, the exception, the failing call or condition, and the relevant log line with any credential, login, seed, key, address, frame bytes or environment value removed. After that, delete `staging/` by its exact path and record the deletion.
   - Raw files never leave the host or reach an attachment.
   - The wallets are valueless, genesis-only and loopback-only.
   - This is the separate private-inspection authority that `direct-runner.md` refers to.
4. **Keep the built binaries.** After a build that passes the build gate, copy the three binaries into a never-mounted, controller-owned 0700 directory under the attempt root and record their SHA256s. They are not exported.
5. **Runtime-only reuse mode.** Add `--reuse-build <prior attempt root>`. It verifies that the retained binaries match that attempt's controller-written PASS `build.json` hashes, and that the pinned source, overlay, toolchain and `build.sh` inputs are unchanged. It stages the binaries plus `BUILD_COMPLETE`, then runs only the runtime phase (600 s plus 300 s cleanup) under the same container flags, caps, lock and two admissions. The build rows reference the prior PASS evidence. A mismatch refuses before any output is created.

**Checks:** connected positive and adverse tests for every item. These include a tampered, missing or renamed binary refusing reuse; a changed input refusing reuse; a runtime failure retaining staging; codes using only allowlisted values; and no traceback or log reaching the exports. Run the full suite, refreeze, commit, and publish one exact packet.

**Review:** Platform first, then Security on items 2–5, since they change the retention and inspection boundary. Ordinary findings under the per-round bounds are yours to fix.

**Grants:**
- The next full grant uses the existing values (load ≤ 9.0, host caps 1 GiB / 1800 CPU-s / 32 PIDs, at least 48 h validity, fresh root).
- After one full build, a runtime-only grant may name `--reuse-build` and the retained root with the same caps and a 900 s window.
- Platform issues each grant as before, with no preparation round. Previous grants stay consumed.

Frozen build.sh, freezer, profile, overlay, pins, caps, workload and private RPC are unchanged apart from the one traceback line. Core decision 47234b59 (count 2) is unchanged. Native runtime ATTEMPTED_FAIL; launch_ready=false; public_launch=false.

Needs TJ: None.
