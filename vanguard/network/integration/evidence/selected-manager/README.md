# Selected manager source evidence

Run `f256c6b4-dd7b-487f-b125-8fc3a9e4dda7`, October 29, 2026. Read `integration/manager-contract.md` first. The full lead decision and author/run provenance are in `authorization.json`.

One implementation pass and one correction pass produced a partial source adapter and helper command interface. All 82 source tests pass: 29 manager, 24 outer, 18 profile, 11 handoff. The initial ordering-assertion failure remains in `pass1-tests.log`; the corrected result is in `pass2-tests.log`. Fixtures use only disposable files, a disposable child process, memfds and unnamed Unix sockets. Admissions, OOM, timeouts, host commands and recovery are modeled; no host manager or native workload was run.

`source-check.json` verifies 32 preserved repository inputs, 63 pinned upstream paths, all ten overlay hashes and the exact Cargo/toolchain tree fingerprints. Those unchanged sections also match commit `1475518b` byte-for-byte. Existing helper/native receipts retain their original attribution and were not rerun.

`synthetic-command-example.json` contains synthetic paths, device identities, operator names and provenance solely to make the command builder inspectable. It is not a real host binding, installation plan, resource snapshot or activation request. Default helper and outer invocations return3; all four capability bindings and the bootstrap hash remain null.

Missing source includes the privileged helper server, exact systemd custody/deadline/namespace recovery wiring, independent observer/export, and legacy-inner atomic create integration. The source artifact is not complete, accepted, host qualified, grant ready or launch ready. Source tests cannot establish a privileged operator. The lead must obtain that operator/authority/preparation binding through the existing parent route, then arrange exact source review and any further bounded integration. All host/native rows remain NOT_RUN. Needs TJ: None for this handoff.
