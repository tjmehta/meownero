# Meownero Windows test

This is an unsigned experimental test bundle. The coins have no value. It runs a
private accelerated FCMP++/CARROT regtest on this computer using loopback only.
It does not connect to the public Meownero network. Never enter an existing seed
or use a real wallet. This corrected harness needs a fresh native Windows check.
The prior ARM wallet journey passed; the prior Intel i686/WoW64 journey timed
out during funding. The Intel cause is still unknown.

1. Install native 64-bit CPython 3.13 or later from [python.org](https://www.python.org/downloads/windows/)
   if needed. Choose **Windows installer (64-bit)** on Intel/AMD x64 Windows, or
   **Windows installer (ARM64)** on ARM Windows. Include the Python launcher.
   An x64 Python installation running under ARM emulation will be refused.
2. Extract the entire ZIP into a new local folder you can write to. Keep all its
   files together. Have at least 10 GiB free disk and 5 GiB available RAM. Close
   another running Meownero tester first. Use Windows 10 version 1709 or later,
   subject to the installed Python version's own Windows requirements.
3. Double-click **RUN-TEST.cmd**. It selects i68635 on x64 Windows (WoW64), or
   ARM13 on ARM64 Windows. The ARM controller also requires ARMv8 crypto support.
   Standalone 32-bit Windows is unsupported by this runner. Do not run as admin.
4. Allow up to 25 minutes for the controller. It checks exact bytes,
   clean extraction and native program startup, receives 5 test coins, checks two
   type-7/CARROT payments, restores the disposable wallet, spends 2 coins, opens
   the native CLI, then runs all ten refusal/cancellation controls. It uses an
   owned Windows Job with a 4 GiB memory cap and checks process cleanup.
   If Windows denies creation of the symlink test fixture with error 1314,
   that control is marked NOT_EXECUTED and later independent checks continue.
   The overall result is INCOMPLETE_NATIVE_ARCHIVE_CONTROLS, never PASS. Other
   fixture errors and failed refusals remain failures. Do not run as admin to
   change this result. Intel funding reports distinguish mining, refresh and
   balance-query timeouts; the existing timeout budgets are unchanged.
5. Share **only the report.zip path printed at the end**, even if the result is
   FAIL or NOT_RUN. A new `run-...` folder is used every time. Do not share the
   whole run folder: it can contain disposable wallets, seeds and private logs.
   The report contains the controller's fixed public JSON receipts and hashes.

Leave the window open until the report path appears. Use Ctrl+C once to request
cancellation and allow cleanup to finish. Force-closing Windows or the terminal
may prevent a report. Keep failed runs local for diagnosis. Once the report is
saved and no test is active, the extracted folder and its run folders can be
deleted. The kernel tester lock may remain as an inert file in Windows Temp;
its handle is released by the controller.

No device inventory, account credentials or raw wallet/log files are included
in the bundle or deliberately collected for the report. The successor archives
replace the build host's home prefix with `/BUILD_HOME/` in provenance only.
Each changed provenance member records its original hash and the transformation.
Updated hash bindings describe the distribution copy; they do not claim that
the rewritten scripts or receipts were the bytes originally executed. Programs,
packaged wallet testers and licenses retain their original bytes. The successor
controller, refusal harness and diagnostic wrapper have new hash bindings
recorded in bundle.json. This candidate
still requires independent review before group sharing.
The report does include runtime OS/Python version and process IDs needed to
check the test. Read it before sharing. A PASS is execution evidence for that
machine; independent review still decides acceptance. WoW64 is not evidence of
standalone 32-bit Windows support. The bundle does not establish bare-metal
execution, signing, universal Windows support or whole-release acceptance.

For operators: `python windows-test-bundle.py --prepare-only --target windows-i686`
checks the pinned Intel inputs without running Windows programs. Use
`--target windows-aarch64` for ARM bytes. Such a report is explicitly byte-only
and does not establish native execution. No Python packages or downloads occur
during a test run. Program licenses and build provenance remain in the successor
archives alongside this guide.
