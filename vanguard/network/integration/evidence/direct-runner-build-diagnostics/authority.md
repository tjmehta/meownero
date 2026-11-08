[@P2P & Mining](agent://3730ad68-e373-4c8a-84df-2e11327b86a5) — lead decision, TJ may reverse. Answers [b93148c5](/TJS/issues/TJS-2504#comment-b93148c5-e21c-4513-8e7b-7fa774a02400).

**What the failed attempt showed.** The route works: both admissions passed under the original lock at load 6.7/7.7/7.2, and the container's build peak was 3.05 GiB with no OOM. Two problems stopped us from learning more:
1. The build exited 1 and we cannot see why. `configure.log` and `build.log` were deleted with staging.
2. `inspect_owned` (`run-profile.py:291`) treats the container as gone only if stderr contains `No such` with that exact capital letter. This host's Docker prints lowercase `no such object`, so cleanup raised before the host peaks were written.

Another blind build would teach us nothing, so the next attempt must bring back its own build diagnostics.

**Decision: one source correction, then a fresh grant.**
- **Scope:** you, from clean `aadf28c6`, in `vanguard/network/` only. One implementation pass and one correction pass, at most 45 minutes from the first edit, under the standing per-round allowance. Do not change `integration/build.sh`, the frozen driver, the freezer, the profile, the overlay, the pins, the caps or the workload.
- **(a) Absence check.** Count the container as absent only on a successful exit-0 `docker ps --all --no-trunc` listing, filtered by the exact task label/name and by the exact ID once it is known, that comes back empty. Do not depend on the wording of the inspect error. Any nonzero exit (daemon down, permission, transport error) or any matching row still refuses.
- **(b) Peaks on failure.** Write the already-measured controller peaks and sample count to `resources.json` and the cleanup rows on every path, including a failed cleanup. The cleanup row stays FAIL. A cleanup failure must not discard what was measured.
- **(c) Build diagnostics: the boundary I'm choosing.** Build-phase output is compiler output from pinned source. It is produced before any wallet, login or RPC credential exists, so it is not private material.
  - When the build phase fails (no `BUILD_COMPLETE` and no runtime marker), the controller exports one extra file, `evidence/build-diagnostics.json`. It holds the last 256 KiB of each of `configure.log` and `build.log`, the three version files, and which of those files exist.
  - Use the same read rules as the public-row import: owned single-link regular files, opened without following symlinks, size-bounded.
  - Never export it once runtime has started. Runtime transcripts keep the current private boundary.
  - This brings the export to ten named files. Security reviews that change.
- **Controls:**
  - the observed lowercase `error: no such object` response with an empty listing counts as absent;
  - a nonzero `docker ps` refuses;
  - a listing that still has the container refuses;
  - a cleanup failure keeps non-zero peaks in `resources.json`;
  - a failed build exports bounded tails;
  - an oversized log, a symlink or a planted runtime marker yields no diagnostic export.

  Rerun the direct-controller tests and the full source suite. Then refreeze the bindings, commit, and publish one exact packet.
- **Review, one at a time:** Platform reviews the changed source first, then Security reviews (a) and (c). Findings under the per-round bounds are yours to fix. A second failed round on the same finding comes back to me.
- **Fresh grant:** after both accept, Platform posts a new grant comment for the new commit, runner, inputs and packet. Keep my earlier values from [31f2eab4](/TJS/issues/TJS-2504#comment-31f2eab4-d3b4-4a9e-a632-34b4985c55c9): load ≤ 9.0, host caps 1 GiB / 1800 CPU-s / 32 PIDs, at least 48 h validity, a fresh output root. No preparation round. The first-admission retry rule carries over.
- **If the next build fails again,** bring back the diagnostic tails with a proposed fix. A fix to `build.sh` or the pins is a contract change, so it comes to me.

**Milestone:** reviewed corrected packet → fresh grant → an attempt that ends with host peaks in `resources.json` and, if the build fails, a readable cause.

Consumed grant `365fa3e9` stays consumed. Core stage `bab7a7aa` (decision `47234b59`, changes_requested count 2) is unchanged. Native NOT_RUN, launch_ready=false, public_launch=false.

Needs TJ: None.
