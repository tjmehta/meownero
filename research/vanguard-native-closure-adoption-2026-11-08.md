# TJS-1882 native Intel and Windows ARM64 adoption (2026-11-08)

This record adopts two independent acceptances into the release record. Product source stays at `7afd06180af9dc17697e8d5a78931c682dfdc074`; this commit adds research files only.

- **macOS Intel (native):** review `native-intel-kernel-table-independent-review-2026-11-08`, revision `0aeba87f`. Binds product `7afd0618`, CI `8a12c61a` in `tjmehta/meownero-private-archive`, inputs `eb3cd783…` and archive `54912e0c…`. Reviewer reproduction: run 42459882900 attempt 4.
- **Windows ARM64 (native, full controls):** review `windows-arm64-public-runner-independent-review-2026-11-08`, revision `d9beba51`. Binds public `tjmehta/meownero` commit `e4e8be65`, bundle `bedd371b…` and ARM archive `eed161ef…`. Reviewer reproduction: public run 42463019325 attempt 4.

The current seven-target matrix is in `evidence/vanguard-native-closure-tjs1882-2026-11-08/seven-target-status.json`. It gives each target's archive, delivery route, status, binding review revision and limits, and it supersedes the 2026-10-30 status file for current status. Residuals R1–R4 (Intel) and A1–A4 (ARM64) are non-blocking and recorded in their reviews.

The seven-target release stays open until the final stage decision. Lead integration and parent delivery are separate steps.
