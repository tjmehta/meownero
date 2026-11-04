# Adopted source scope

Interaction 81de4466-14e3-4d2a-bfa3-d8eaebcc50dd; resolved by 8f050fb0-7908-4b7f-be53-45d17272cec7 at 2026-11-04T03:03:45.088Z.

Lead decision, TJ may reverse: adopted, with a wider check under the second-attempt rule.

**Confirmed.** `run-profile.py:427-428` allows only `lib…\.so` names. Every glibc amd64 executable lists `ld-linux-x86-64.so.2` in DT_NEEDED, so a correct build.json is always refused.

**Why the scope is wider.** Three granted attempts have now each failed at a different seam between the real build output and the code that accepts it: the cleanup absence text, the RPC object path, and now the loader SONAME. Each fix passed source tests built on synthetic stand-ins. The shared false premise is that synthetic fixtures prove the producer/consumer contract. A fourth 30-minute build must not be the instrument that finds the next seam.

**Adopted scope.** You, from clean `bf6acfba`, in `vanguard/network/` only. One implementation pass and one correction pass, at most 60 minutes from the first edit.
1. **Predicate:** your proposal as written. Keep the grammar and the 32-entry cap, add exactly `ld-linux-x86-64.so.2`, keep the loader in the evidence, and keep every adverse refusal.
2. **Real-data build check (required before any new grant).** Copy the existing real historical daemon/CLI/RPC ELFs into a disposable tree laid out like the pinned build. Add the retained compile log from build-diagnostics (attachment 729928e9 or the ea19d496 export) and a real-layout RPC object stand-in. Run the unchanged frozen `built()` on it, with readelf only and no execution. Then feed the build.json it produces through the actual controller `read_public_rows()` and the build gate in `main()`. It must pass end to end. Keep this as a connected test.
3. **Static audit of the runtime rows.** For every runtime row in `public_shapes()` (peer, wallet, auth, isolation, reopen), map each field the frozen driver emits (file:line) to the validator that checks it (file:line). That covers type, int/str, hex case and prefix, list lengths and literal constants. List every mismatch in one table. Fix controller-side mismatches in this same pass. A mismatch that needs a driver change comes back to me as one list, not one per attempt.
4. **Keep rejected payloads.** When build.json is refused, put its bounded bytes (≤ 64 KiB, using the existing no-follow single-link reader) and the key path that failed into `build-diagnostics.json`. For a refused runtime row, export only the failing key path, not the values. The next failure should name its exact cause.

**Review.** Platform reviews the changed source first. Security then reviews only the allowlist change and the rejected-payload retention, because together they widen what untrusted container output reaches the export. Findings under the per-round bounds are yours to fix. A second failed round on the same finding comes back to me.

**Then.** A fresh Platform grant comment with the same values: load ≤ 9.0, host caps 1 GiB / 1800 CPU-s / 32 PIDs, at least 48 h validity, a fresh output root, no preparation round, and the same first-admission rule. Grants 365fa3e9, d9a6559b and ea19d496 stay consumed. The host peaks so far (≤ 478 MB, ≤ 225 CPU-s, 2 PIDs) are within the caps.

Frozen build.sh, freezer, driver, profile, overlay, pins, caps and workload are unchanged. Core decision 47234b59 (count 2) is unchanged. Native runtime NOT_RUN. Needs TJ: None.
