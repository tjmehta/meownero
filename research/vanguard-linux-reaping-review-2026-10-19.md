# Linux process reaping correction for independent source review

TJ's owner approval and the original reviewer's source clearance at
`630f6fbcd84e8475816da823a1c15197226ff4d4` are retained. This successor needs
ec85048c's comment-only source review under decision `8572f862`. It is not a
release-stage submission. No new tester binary or release acceptance resulted.

The evidence directory is
`evidence/vanguard-linux-reaping-tjs1882-2026-10-19/`.

The writer qualified an actual native ARM Ubuntu 22.04 VZ guest on build-mac.
It used 2 CPUs, 10 GiB RAM, a 60 GiB disk, no shared mounts and no Rosetta.
The guest supplied glibc 2.35, the required AES/PMULL/SHA1/SHA2 features,
Python 3.13.16, an idle VM-local Docker daemon and about 9.25 GiB available RAM.
The exact image SHA256 is
`86e13258765945ad792dac75fac7f02f4db9fa73a4a535ffa472266e7041fa19`.
Canonical's checksum signature passed gpgv with the installed Ubuntu cloud-image
keyring. The July image's archive HTTPS endpoint failed; the current image was
explicitly pinned rather than falling through to an unchecked image.
`vm-fallback.yaml` matches the actual recorded configuration digest.
Guest-only preparation took 94.408 seconds under a 20-minute, 2-CPU, 2-GiB limit.
The preparation script, downloaded package hashes and installed versions remain
available with the qualification record.

The original full ARM39 controller then failed closed during fetch after 2.87
seconds with `UNVERIFIED_FIRST_ZOMBIE`. Git had completed checkout before Python's
timed wait reaped its child. The supervisor had first observed that child after
exit, and therefore refused to infer its executable identity. It forwarded
cancellation to its owned wrapper, proved all six recorded PIDs absent, removed
its lock and issued no cleanup signal to the unverified child. No compilation,
archive packaging or wallet journey started.

`vanguard/run-portable-ci.py` now gives a first-observed Linux zombie at most
250 ms for its parent to reap it. The existing phase deadline caps this wait.
Only independent numeric PID-absence proof permits continuation. UID checks
still precede this branch. The observation remains quarantined and supplies no
signal authority. A zombie that stays present still fails with the original
reason. Live process, PID identity, privilege and cleanup checks are retained.
Darwin does not enter the new waiting branch; its existing absence record gains
an explicit proof field. There is no new dependency or process scheduler.

This changes the shared supervisor called by the Linux phase controller and
Mac archive checker. The separate local 38/39 successor inputs bind its new
bytes. Their sixteen helper bindings validate. Frozen hosted carriers and the
first local admission inputs remain intact; frozen inputs must not be run
against changed helper bytes. No hosted publication or dispatch occurred.
Two admission fixtures now bind the current shared supervisor so their existing
OS/refusal and provenance assertions reach the intended code.

The new real-process regression fails on the original supervisor. On the
correction, both the local Linux run and qualified native ARM guest prove
transient-zombie absence, persistent-zombie refusal, wrapper/child reaping and
preservation of an unrelated live process. The ARM run recorded ten actual
grace observations, with a maximum of 0.120884 seconds. Seven admission tests
pass. The previous 81 inventory/privacy/package-diagnostic cases are reused
from review `60c9c32a`; they were not rerun or upgraded to native release proof.
Deadline capping is inspected here; these new cases do not independently test
cancellation or every historical adversarial identity case.

All six pre-existing dirty/untracked regular-file hashes remain unchanged.
All 36 frozen bindings resolve to unchanged source carriers and original Git
objects. Both owned VMs, the downloaded image and converted raw cache, the host
heavy lock and exact task staging directory were removed after evidence fetch.
Existing Colima remained Running with 4 CPUs, 6 GiB RAM and its 100 GiB disk.
`ios cleanup complete` rejected this staging subdirectory because it is outside
its task-completion roots; exact owned staging was removed directly instead.

| Requested target | Retained disposition |
| --- | --- |
| Windows x64 | Historical scoped native acceptance and delivery retained. No fresh test. |
| macOS Apple Silicon | Historical scoped native acceptance and delivery retained. No fresh test. |
| macOS Intel | Historical scoped native acceptance and delivery retained. No fresh test. |
| Windows x86 | i68635 packet retained. Native x64 Windows/WoW64 execution and capacity route remain outstanding; standalone 32-bit Windows is untested. |
| Windows ARM64 | ARM12's terminal native build failure on `sys/mman.h` remains unresolved. |
| Linux x64 | Linux38 Ubuntu22 build/archive/ABI/journey/control suite remains untested. Current container has no KVM/VM launcher; direct physical-host SSH refused host-key verification. No trust bypass or shared-daemon use. |
| Linux ARM64 | Native Ubuntu22 runner qualified, then disposed. Full original controller failed at fetch. Correction has focused native process evidence only and awaits source review. |

Historical Ubuntu24 Linux builds/journeys and the accepted published Docker leaf
remain valid within their recorded scope. Included Actions capacity remains
unconfirmed because the installed token cannot read billing. No paid dispatch,
integration, deployment or group message occurred. Debian12, Fedora/RHEL,
Arch/openSUSE, current Linux release archives, ABI audits, payment/restore/later
spend/CLI journeys and ten controls remain untested for this successor.

The original reviewer should inspect this exact diff and reproduce the focused
regression, especially the persistent-zombie refusal and absence-only authority.
Return findings or source clearance by comment and reassign the existing issue
to writer `92a7b4f2-787b-4cbb-954e-46831397ab09` with status `todo`. Preserve
workspace `a1e39b67` and stage `82aa96f6`; do not issue a release-stage decision.
After clearance, the writer requalifies a newly owned ARM Ubuntu22 guest and
runs the entire controller using `local-39-reaping-inputs.json`, then pursues
the x64 isolation/access route. Final artifacts still need independent review.
No new TJ input is needed for this source correction.

Primary contracts: [Python 3.13 timed process waits](https://docs.python.org/3.13/library/subprocess.html#subprocess.Popen.wait),
[Linux exit/reaping semantics](https://man7.org/linux/man-pages/man2/waitpid.2.html),
[Lima VZ](https://lima-vm.io/docs/config/vmtype/),
[Python 3.13.16 release checksum](https://www.python.org/downloads/release/python-31316/).
