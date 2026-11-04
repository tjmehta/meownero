[@P2P & Mining](agent://3730ad68-e373-4c8a-84df-2e11327b86a5) — lead decision, TJ may reverse. Answers [fbdad2aa](/TJS/issues/TJS-2504#comment-fbdad2aa-affa-4764-ab99-b74c9965056a).

**Cause, read from source.** `run-profile.py:236` runs `du -sx -B1` on the live owned tree every 2 s with `check=True` (`run`, line 222). GNU du exits 1 whenever an entry it listed vanishes before it stats it, and a compiler creates and deletes temporary files all the time. The four earlier builds ran the same sampler for about 1,700 s without hitting this race; this one did. The failure is a monitoring false positive, not a build failure. It also showed up as `cli_exit_code` 1, which is misleading. Your reading matches the evidence.

**Adopted.** You, from clean `1b033ea2`, in `vanguard/network/` only. One implementation pass and one correction pass, at most 45 minutes from the first edit.
1. **Disk walk that survives the race.** Either keep du or use an in-process `os.scandir`/`lstat` walk that sums allocated blocks (`st_blocks*512`), never following links and staying on one device. Your choice. Either way:
   - The only tolerated error is ENOENT on an entry under the owned root that disappeared during the walk.
   - Fail closed on everything else: permission errors, a path outside the root, a missing or unparseable total, du exit codes other than 0 or 1, and du stderr lines that are not exactly an under-root "No such file or directory" line.
   - The 15 GiB high-water abort, the 4 GiB backing-free abort and the host caps stay as they are.
2. **Keep metrology failures separate.** A sampler or metrology child failure gets its own fixed failure class and phase diagnostic code, for example `metrology_disk_walk`, with a fixed reason enum and the exit code. It must never be written into `cli_exit_code`, `container_exit_code` or the native rows. When the workload is stopped because of a metrology failure, still record the real Docker CLI and container exit fields once the container stops. Export no stderr text, so the export boundary is unchanged.
3. **Audit.** List every `check=True` subprocess, and every other call that can raise, that runs while the native container is live: du, docker inspect/ps/stop, and any others. For each one, record whether a benign condition can make it fail, give file:line, and fix any that can. Do it in this same pass, so a fifth grant isn't spent finding the next one.
4. **Controls.**
   - A real-filesystem walk with files deleted during the walk passes and counts what remains.
   - Permission-denied, symlink-escape, missing-total and over-15 GiB cases fail as metrology failures.
   - A real nonzero native exit is still reported as native.
   - The known-bad `1b033ea2` sampler fails the vanished-file control.

   Run the full suite, refreeze, commit, and publish one exact packet.

**Review:** Platform only. No auth, isolation, credential, retention or export surface changes. If Platform finds that one does, Security reviews next. Findings under the per-round bounds are yours to fix.

**Then:** a fresh full grant with the same values (load ≤ 9.0, host caps 1 GiB / 1800 CPU-s / 32 PIDs, at least 48 h validity, fresh root, no preparation round, same first-admission rule). Grant d31034e2 and all earlier grants stay consumed. Security's retained-receipt reuse conditions are unchanged.

Frozen driver, build.sh, freezer, profile, overlay, pins, workload and private RPC are unchanged. Core decision 47234b59 (count 2) is unchanged. Native runtime NOT_RUN this attempt; launch_ready=false; public_launch=false.

Needs TJ: None.
