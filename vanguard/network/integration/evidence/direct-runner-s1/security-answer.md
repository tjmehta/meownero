Consultation response: **changes needed — one actionable finding (S1, P2)** in the active direct runner. This is not a formal-stage decision, native acceptance or runtime grant.

**Bound candidate.** Clean `35240d74a304f0ca57a972b7a34656e33966844f`, tree `a3a2c979bcbe8dfe49c7e43d937fedbcad453ca6`. Authenticated download of attachment `e8e02b0b-efa7-43f0-aa1f-76d894e267df` returned HTTP 200 directly: 630,699 bytes, SHA256 `520aad57eccc89502a5594f4bd0be25484321830622542d868c663a157e9bfef`. Its `run-profile.py` (`aae30e11…`), `integration/inputs.json` (`a8d24725…`), frozen `profile-integration.py` (`113ab28d…`) and `integration/build.sh` (`7922520d…`) equal the worktree bytes. The frozen driver is byte-identical to `fa7c1962`.

### S1 (P2): the host controller writes through container-planted symlinks and FIFOs

**Boundary.** The container runs as the controller's uid and owns both writable mount roots, `staging/` (`/out`) and `public/` (`/public`). After any build or runtime step, every entry name, file type, link and mode bit under them is chosen by the workload. `bounded_json` already treats them as untrusted (`O_NOFOLLOW`, regular file, owned, nlink 1). Two controller writes do not.

- **A: `run-profile.py:466`.** `(args.out/'staging/BUILD_COMPLETE').write_text('runtime\n')` runs after the build phase, on the success path. A build step can leave `/out/BUILD_COMPLETE` as a symlink, for example an offline Cargo build script or a CMake step. The controller then truncates and overwrites the link target outside the owned root. If that entry is a FIFO instead, the controller blocks in `open()` until the watchdog fires.
- **B: `run-profile.py:556–557`.** Final rows and `receipt.json` are written into `public/` with `n.write_json` (`network.py:141`, a plain `Path.write_text`). On success, `collect_public` (`:391–394`) first removes every entry. If that removal raises, the exception lands in the cleanup `except` (`:539`). The final loop still writes into `public/` and follows any surviving symlink.
  - The workload can force this without any ordering trick: `chmod 0500 /public` on its own mount root makes the first `unlink` raise `PermissionError`. A 0500 subdirectory has the same effect.
  - The same final write also runs after any earlier cleanup exception, such as unconfirmed CID absence.
  - This path also leaves unvalidated producer entries in `public/` next to controller rows. That contradicts `direct-runner.md:76–77`.

**Impact.** Integrity and availability; code execution was not shown. Any file the controller user can write can be truncated and overwritten with fixed text or controller JSON: keys, configs, other tasks' evidence, the source checkout. Untrusted producer content can also survive into the evidence directory.

**Precondition.** Adversary-controlled code inside the pinned build or runtime container: offline Cargo build scripts, upstream source or CMake, built binaries or the driver. That is the threat this containment and its existing `O_NOFOLLOW`/nlink checks are meant to stop.

**Confidence.** High: static source reading plus a disposable reproduction.

**Reproduction.** Disposable fixtures only; no Docker, lock or native work. Python 3.15.2 loaded the real `run-profile.py`, and the probe asserts that lines 466 and 556 are the quoted expressions.
- **probe.py (A):** a `staging/BUILD_COMPLETE` symlink causes the victim file outside the root to become `runtime\n`.
- **probe.py (B):** a 0500 subdirectory plus symlinks for every `c.REQUIRED` name and `receipt.json`. `collect_public` raises `PermissionError`, six symlinks survive, and the final-write loop overwrites all six victims.
- **probe2.py:** `chmod 0500 public/` raises the same error, and all nine names are clobbered. A FIFO at `BUILD_COMPLETE` blocked the same `write_text` for more than 3 s; the child was killed by the timeout.
- Scratch was removed and the worktree is unchanged.
- Evidence is in the `security-evidence/` folder of Security run `61768eac`: probe.py `b7a9959d…`, probe-run1.json `dbc6d94f…`, probe2.py `e5a75408…`, probe-run2.json `01762ddc…`.

**Narrow fix** (`run-profile.py` only):
1. Never open a path in `staging/` or `public/` for writing once the container exists. For the runtime marker, open `staging` with `O_RDONLY|O_DIRECTORY|O_NOFOLLOW`. Then create `BUILD_COMPLETE` with `os.open(..., O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC, 0o600, dir_fd=…)`. If any entry already exists, fail before runtime starts.
2. Treat `public/` purely as untrusted input. After confirmed container absence, create a fresh controller-only directory that is never mounted, for example `args.out/'evidence'` (mkdir 0700). Write all final rows and the receipt there with the same exclusive, no-follow `dir_fd` creates, including on cleanup-failure paths. If `public/` cannot be fully cleared, record FAIL and leave it quarantined; never write into it.
3. Publication must come only from that controller directory. Update `direct-runner.md` and any packaging step so leftovers in `public/` are never exported.

**Acceptance check.** Use actual `main` finalization with substituted Docker responses, like the existing F2/F3 tests:
- (a) A build fixture plants a `BUILD_COMPLETE` symlink to a victim outside the root. Expect: victim unchanged, attempt FAIL, runtime never started. Repeat with a FIFO: expect a prompt FAIL with no hang.
- (b) A runtime fixture plants symlinks for every `REQUIRED` name and `receipt.json`, then runs `chmod 0500 public/`; repeat separately with a 0500 subdirectory. Expect: no file outside the output root changes, result FAIL, only controller-written rows in the evidence directory, and no producer entry exported.
- (c) The existing direct-controller and complete source suites still pass.

### No actionable finding in the rest of the assessed scope

These checks are static source checks; native execution remains NOT_RUN.

- **Network isolation.** The container uses `--network=none` and no `-p`. Before start, `verify_limits` (`:302–309`) checks NetworkMode none, empty PortBindings, CapDrop ALL, no-new-privileges, not privileged, and the uid:gid user. Inside the container's own network namespace, daemons bind 127.0.0.1/::1 and wallets bind 127.0.0.1 (`profile-integration.py:221–223, 386–387`).
- **Per-child RPC authentication.**
  - Each daemon gets a fresh `secrets.token_hex(24)` `RPC_LOGIN`, passed only through that daemon's environment (`:217–218`). `launch` refuses it for non-daemon children (`:58`).
  - The wallet RPC login is generated natively and read from a 0400/0600 private file (`:390`). The CLI's daemon login sits in a 0600 config file (`:404`).
  - Daemons and wallets run with `--restricted-rpc`, and no credential appears in argv.
  - I re-read these lines in the byte-identical frozen driver. The 17-denial and lifecycle logic is reused from the prior Privacy and Security consultations, not re-executed.
- **Credential and environment exclusion.** `Controller.run` passes only PATH, LC_ALL, GIT_NO_LAZY_FETCH and HOME (`:194–195`). `docker create` has no `-e`. The Paperclip token is used only by the in-process `api()` call (`:33–37`). The lock descriptor is `O_CLOEXEC`, and children start with `close_fds`.
- **Bounded public evidence.** `bounded_json` and `public_shapes` accept only fixed literals, hex digests and regex-limited library names. Receipt diagnostics are phase names, numeric exit codes, an OOM boolean and exception type names. The receipt's admission data holds host memory, disk and load counters; its collision lists are always empty when written. PASS completeness is reused from Platform's F3 acceptance (run `6e849f00`), not re-executed here.
- **Exact-owned cleanup.** Process groups are matched by pid plus start ticks. The container is matched by name, label, image and staging mount, then removed by exact ID. The cidfile sits outside both mounts. `docker inspect <name>` lacks `--type container`, but a same-named non-container object makes cleanup fail closed rather than expose anything.
- **Untrusted grant handling.** The grant must be Platform-authored on this issue and contain exactly one block. It must bind the exact commit, inputs, runner, artifact and output root, with a current validity window, positive load and overhead values, and the fixed attempt shape. The artifact is fetched with authentication and digest-compared. IDs are regex-limited before use in a URL or container name. Creating the fresh output root is the one-use marker.

### Rejected or hardening only

- **Host Docker CLI configuration.** `HOME=staging/tmp` puts the controller's `~/.docker` inside the container-writable `/out/tmp`. Docker CLI 29.5.3 (`cmd/docker/docker.go`, `runDocker`) runs plugin hooks only when stdout is a terminal, and the controller uses pipes. The pinned `--host` also overrides contexts. No current effect was established. Optional hardening: give the CLI a controller-owned `--config` directory outside any mount.
- **Bearer forwarding on redirect.** Not exercised: the attachment endpoint answered HTTP 200 directly.

**Limits.** Native listeners, authentication behaviour and cleanup are NOT_RUN. Docker daemon defaults (userns, runtime, IPC) were not inspected. `verify_limits` checks only the named HostConfig fields; the fixed create argv is the primary control. Host overhead and du remain sampled abort rules. No test suite was rerun.

P2P owns the fix under the existing standing per-round allowance. Platform's grant comment follows after that. No grant was issued here. Needs TJ: None.
