# Verified source boundary

Authority: Meownero lead comment f44e6422-ea8c-4f5d-a211-78eab75077ca, 2026-11-03.

- Python runtime observed: 3.15.2. Python 3.15 docs: https://docs.python.org/3.15/library/os.html — descriptor-relative os.open/stat, O_NOFOLLOW/O_NONBLOCK, fstat and positional pread. Reads are metadata checked and bounded before decoding.
- Docker CLI listing contract: https://docs.docker.com/reference/cli/docker/container/ls/ — --all includes stopped containers, --no-trunc preserves full IDs, --filter supports label/name/id, and --format allows headerless IDs. Independent queries conservatively refuse any match.
- Exact anchored name semantics follow Docker name-filter regular expression support; this source-only suite models the CLI responses, and does not independently qualify the live engine. Platform review remains required.
- Local pinned integration/build.sh identifies exactly configure.log, build.log, rustc.txt, cargo.txt, cmake-version.txt and BUILD_COMPLETE phase switch. The driver/freezer/build recipe are unchanged.

Limits: no Docker daemon, native workload, capacity admission or original heavy lock was used in this source round. Compiler diagnostics are permitted only before runtime by the cited lead decision; runtime data remain private. Logs are refused above 16 MiB; version files above 4 KiB. These read ceilings bound input inspection, without changing resource caps/workload.

Versioned Docker implementation reference: https://github.com/moby/moby/blob/v28.5.1/daemon/list.go and https://github.com/moby/moby/blob/v28.5.1/api/types/filters/parse.go (name uses regexp Match; label uses exact key/value). This verifies the anchored filter design against that version, not the currently running engine. No live engine claim is made.
