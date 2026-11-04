Live-container supervisor audit (lead decision 5a41a0b8)

Scope: direct entry run-profile.py from Docker start through confirmed stopped state
and exclusive cleanup. Frozen native/build calls are listed separately below.
call-inventory.json enumerates every syntactic call in these supervisor functions,
including pre-live/post-absence portions of main. Line references name this candidate.

| Call / source location | Benign condition or fail condition | Disposition |
| --- | --- | --- |
| Controller.run:218-247, Popen:224, pid_identity:42, remember:184 | A supervised child can exit while observed. Its unreaped PID retains /proc identity. Proc descendants can disappear. Spawn/identity permission, malformed metadata, pipe I/O or deadline failure is not proof of native exit. communicate timeouts are expected until the deadline. | Existing ENOENT/ESRCH handling in remember/stop; timeout retry within deadline. All other errors fail closed. Only the actual Popen returncode enters the native diagnostic. A sampler child uses a separate exit observation. |
| Controller.stop:194-216 (remember, proc reads, killpg, wait, sleep) | Child/group exit between observation and signal is benign. Permission denial, persistent owned members or exhausted wait is not benign. | Existing ENOENT/ESRCH catches and start-time checks preserve unrelated PIDs. TERM/KILL and wait remain bounded. Finalization records a real reaped CLI exit even if supervision raises. No assumption that cleanup succeeded. |
| disk_bytes:249-281, du:257 | File or directory disappears between enumeration and stat/opendir. Every other nonzero condition remains a failure. | FIX: explicit -P/-x, check=False; accept only exits0/1 with exactly one numeric total for the exact root. Exit1 requires diagnostics; every diagnostic must be one exact C-locale cannot-access or cannot-read-directory ENOENT line for a lexical child under root, with no empty/dot/dotdot components. Root aliases, disappearance or changed inode/device fail. All other output/exit/permission/parse errors become MetrologyFailure. No stderr exports. |
| sample:283-297, disk_usage:288 | Root/backing filesystem lookup can fail; free space or high-water can violate caps. | Fixed metrology class/code/reason; unknown observation fails closed. Unchanged4GiB free and15GiB allocated high-water thresholds,2s/boundary sampling. Disk row FAIL for disk metrology failure. |
| sample_host:299-320 (proc iteration/read, sysconf, getrusage, numeric parsing) | Proc entries can disappear; existing ENOENT/ESRCH catches apply. Unsupported/permission/malformed observations or exceeded host caps are not benign. | Fixed metrology failure on unobservable data or exceeded allowance. No cap relaxation. Samples/peaks retained. |
| inspect_owned:361-383, Docker inspect and ps | Inspect can return nonzero because the container is absent. CLI error text cannot establish absence. | Already check=False/monitor=False. Each exact CID/label/anchored-name listing must independently exit0 and be empty. Unexpected inspect JSON/identity/mount/state or nonzero listings fail closed; a live collision never becomes absence. No change needed. |
| main native start:815-823 | Attached Docker CLI can return nonzero, or supervisor can stop it following metrology failure. Native phase may also exit nonzero or OOM. | check=False; normal CLI result and reaped CLI returncode are actual native CLI evidence. stopped_exit:161 validates and records actual stopped container ExitCode/OOMKilled. Removed generic CalledProcessError-to-native-code assignment. Metrology code/reason/child exit is separate. |
| cleanup stop/inspect/kill:854-860 | Container exits between inspect and stop/kill, so the command can exit nonzero benignly. | stop already check=False. FIX kill check=False followed by exact inspect. A still-running or unconfirmed container fails closed; no successful exit is invented. |
| cleanup stopped_exit/rm/absence:861-867 | Removal can race with absence. | FIX rm check=False; require independent exact identity absence afterward. Capture stopped native container exit before removal, including metrology-aborted phases. Existing cleanup-failure and owned-PID/fd finalization remain. |
| signal handler:780 and setitimer/finalization | Watchdog, termination or exhausted work/cleanup budget intentionally aborts work. Signal/descriptor/proc failures are not a benign measurement. | Preserve exclusive300s cleanup within full4500s/reuse900s wall caps; no extension, retry grant or inferred PASS. |
| Python dict/list/regex/numeric/Path calls throughout listed functions | Memory, type, malformed OS/Docker result or I/O errors can raise. | Metrology boundary translates sampling errors into fixed codes; other supervisor errors fail the attempt and enter cleanup, never native exit inference. Literal field names only; no exception message or child output serialized. |

Every default/check=True subprocess in the direct host entry:

- run-profile.py:72 pinned Git show (check_output),749-750 Git HEAD/status (check_output): before lock/output/native.
- stage_inputs git archive:334, tar:336, git apply:340: before container creation.
- main image inspect:797 and Docker create:805: before the first native start. Failure can leave uncertain create intent; existing exact-identity recovery applies.
- Controller.run:237's check branch has no check=True invocation while the native workload is live after this correction. du/start/inspect/ps/stop/kill/rm all explicitly use check=False. Meaningful native failure checks still require CLI0/container0/not-OOM.

Calls between phases: read_public_rows/bounded_json/bounded_bytes, public_shapes and
witness_failure validate the build evidence only after stopped_exit confirms the
container stopped. retain_build/private_directory/binary_copy/exclusive_write and
runtime_marker also run while it is stopped. Their stable owned no-follow files,
hashes, metadata, JSON schema, fsync/write/copy and marker refusals remain fail
closed. No concurrent producer disappearance is benign at this boundary. After
confirmed absence collect_public, diagnostics/counter reads, private retention,
rmtree and publish_evidence retain their existing error handling. They are not live
sampler operations. Their auth/retention/export policy bytes are unchanged.

Frozen in-container path (no edit): integration/build.sh:1-36 uses set -eu;
toolchain version commands, cmake configure/build, and freezer --built failures
are build failures. Its EXIT trap's cgroup reads/resource write may fail, leaving
required counters missing and therefore failing the existing evidence gate.
freeze-profile.py:179 rustc version-file read and:185 readelf check_output execute after compilation;
missing/changed binaries or RPC object/witness is a real rejected build, not a
benign walk race. profile-integration.py has no check=True subprocess. It uses
Popen:61 for owned daemons/wallets, and wait/send_signal/kill:67-76; an unexpected
native exit or forced non-graceful save is a real failed requirement. Its readiness
wait:132-140 already tolerates bounded transport/schema/startup errors. Private
RPC/socket/frame/PTY/thread/filesystem calls and require gates intentionally fail
closed outside those polls; an exception produces existing fixed runtime codes and
private traceback. All driver/build/freezer bytes remain exact1b033ea2 bytes.

Evidence and limits:

- Real GNU du9.4 is executed for deletion, allocated-total, no-follow and permission
  controls. The vanished-file fixture enumerates a real file, deletes it, and adds
  that now-missing listed operand to real du. This deterministically obtains the
  same total+ENOENT contract as an internal readdir/stat race, without claiming to
  force GNU du's internal timing. Root total equals remaining st_blocks*512.
- The exact old1b033ea2 sampler fails that identical control with CalledProcessError.
- Stop/kill/rm exit races and native container exit capture are connected actual-main
  fixtures with Docker/admission substituted. A separate real host child proves
  native CLI17 stays17, and stopped CLI code differs from sampler child23.
- No actual Docker/build/runtime, capacity/admission or protected-lock operation ran.
  The original native attempt's actual failed argv/errno is still unobserved.

Primary implementation reference: installed GNU coreutils9.4 manual node
"du invocation" (/usr/share/info/coreutils.info.gz), matching du --version.
-P counts each link itself; -x skips other devices; -B1 reports allocated usage in
bytes; -s emits one total per argument. Official URL:
https://www.gnu.org/software/coreutils/manual/html_node/du-invocation.html
The online fetch timed out; the matching installed manual was read. Exact error
wording is exercised against the installed binary, not inferred from that manual.
