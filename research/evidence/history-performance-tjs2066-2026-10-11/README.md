# Wallet history performance, TJS-2066

Measured local simulated Linux Qt 6.12 wallet. Baseline is accepted integration `9660919e70c35433762e64c5bc04e0d271830ee6`. The production change is in `1304e0155600ca2eafb26efc24bbc128d005bf0b`; the uninstrumented candidate executable SHA-256 is `623d107442cdab6d78d6cc242e3940d99e037b48f74930b01a5a21193aef1e5d`. These are author checks; independent review, native journey QA and lead integration are required before completion.

## Measurements

Five fresh-process repeats of every page/count case, sequential, pinned to allowed CPU 0. Both instrumented builds use the same fixture generator, counters, Qt toolchain, Release flags, owned Xephyr display :59, xcb, software renderer and basic GUI-thread render loop. No compilation or other author workload ran during either matrix. Shared host scheduling and warm filesystem caches contribute to wall-time spread. The four-record control is the accepted normal story. Larger histories repeat its four transaction shapes with unique IDs/txids and deterministic heights. They are synthetic scalability probes, not network-wallet latency.

Each process records a model-only refresh before QML loads, a settled synchronous refresh with the current page loaded, then its first compact-to-exact toggle. Model-only timing excludes delegates; displayed refresh includes synchronous delegate work. 600 ms settling after engine load exceeds the 180 ms page animation; 300 ms separates refresh and toggle. `frameSwapped` is timed directly with QElapsedTimer in the basic render loop. There is no concurrent render thread or queued timestamp hop, and the synchronous Repeater has completed all delegate creation before the requested post-action frame. This measures submitted Qt frames, not physical display scanout. CPU deltas use getrusage; RSS is fresh-process high-water. Both matrices stayed below the initial 512 MiB process ceiling and 60 s per-case deadline. Those are experiment safety bounds, not product SLOs.

Median milliseconds, with min–max spread. RSS is median process peak MiB. Raw samples retain all five observations and counters.

| Page | Rows | Operation | Baseline sync | Optimized sync | Baseline frame | Optimized frame | CPU baseline → optimized | Peak RSS baseline → optimized |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| overview | 4 | model | 0.099 (0.086–0.122) | 0.037 (0.021–0.044) | 0.099 (0.086–0.122) | 0.037 (0.021–0.044) | 0.112 → 0.048 | 30.0 → 30.0 |
| overview | 4 | refresh | 14.841 (10.018–34.705) | 0.597 (0.495–0.604) | 23.108 (13.021–44.180) | 6.764 (6.469–9.240) | 12.531 → 0.845 | 65.6 → 65.1 |
| overview | 4 | toggle | 14.547 (11.189–44.775) | 1.158 (0.799–1.296) | 25.438 (15.088–52.027) | 9.181 (7.832–11.163) | 14.926 → 3.874 | 65.8 → 65.1 |
| overview | 100 | model | 1.147 (1.070–1.459) | 0.370 (0.274–0.448) | 1.147 (1.070–1.459) | 0.370 (0.274–0.448) | 1.162 → 0.381 | 30.0 → 30.0 |
| overview | 100 | refresh | 28.553 (15.391–33.142) | 0.658 (0.585–5.868) | 39.285 (20.606–42.563) | 6.070 (6.016–11.972) | 14.786 → 0.928 | 65.6 → 65.0 |
| overview | 100 | toggle | 25.928 (20.588–47.376) | 1.340 (0.912–1.603) | 43.557 (31.391–68.928) | 7.895 (7.318–9.189) | 17.422 → 2.631 | 65.6 → 65.1 |
| overview | 1000 | model | 16.920 (15.105–34.619) | 3.761 (2.315–5.711) | 16.920 (15.105–34.619) | 3.761 (2.315–5.711) | 15.103 → 3.777 | 30.8 → 30.8 |
| overview | 1000 | refresh | 40.982 (28.877–57.675) | 5.405 (3.511–6.813) | 46.457 (39.133–65.903) | 11.652 (8.799–12.709) | 27.415 → 4.880 | 66.4 → 66.2 |
| overview | 1000 | toggle | 53.894 (34.365–79.130) | 9.613 (5.110–10.577) | 59.229 (39.202–83.538) | 16.997 (11.880–19.929) | 29.335 → 7.410 | 66.4 → 66.2 |
| activity | 4 | model | 0.090 (0.081–0.139) | 0.021 (0.021–0.053) | 0.090 (0.081–0.139) | 0.021 (0.021–0.053) | 0.102 → 0.029 | 30.0 → 30.0 |
| activity | 4 | refresh | 15.204 (11.404–79.128) | 0.457 (0.288–0.915) | 19.844 (15.012–89.026) | 5.741 (5.607–7.117) | 15.298 → 0.671 | 64.9 → 64.2 |
| activity | 4 | toggle | 17.124 (10.991–60.973) | 0.549 (0.493–0.825) | 23.892 (14.112–102.848) | 6.515 (6.095–6.919) | 13.329 → 1.514 | 64.9 → 64.4 |
| activity | 100 | model | 1.385 (1.124–1.695) | 0.294 (0.210–0.487) | 1.385 (1.124–1.695) | 0.294 (0.210–0.487) | 1.421 → 0.307 | 30.0 → 30.0 |
| activity | 100 | refresh | 246.891 (221.037–672.326) | 0.558 (0.539–0.941) | 280.818 (255.613–717.010) | 6.189 (6.056–7.588) | 267.667 → 1.167 | 97.4 → 82.3 |
| activity | 100 | toggle | 416.481 (196.554–799.303) | 2.439 (2.269–2.635) | 463.774 (234.150–859.585) | 9.728 (8.905–10.641) | 258.834 → 5.387 | 99.4 → 82.5 |
| activity | 1000 | model | 25.490 (13.805–32.979) | 4.832 (3.764–5.714) | 25.490 (13.805–32.979) | 4.832 (3.764–5.714) | 13.979 → 3.881 | 30.8 → 30.8 |
| activity | 1000 | refresh | 4675.107 (2871.107–5213.410) | 4.527 (4.151–5.460) | 5435.582 (3272.593–6150.855) | 15.281 (13.100–16.592) | 2861.012 → 9.010 | 403.2 → 253.5 |
| activity | 1000 | toggle | 3617.466 (2252.971–4239.473) | 22.484 (20.701–35.581) | 4243.072 (2623.606–4971.630) | 57.889 (54.240–78.103) | 2683.097 → 55.538 | 413.8 → 253.9 |

For model-only rows, the frame column repeats the model duration because no window exists. CPU is process CPU through the frame callback for displayed rows, and through refresh for model-only rows. `summary.json` additionally provides CPU, RSS and activity spreads; per-case stdout/stderr and `samples.jsonl` preserve the raw observations.

## Demonstrated costs and changes

At 1,000 records the baseline performs 500,536 ID comparisons, 1,004 full detail-map constructions and two full sorts per refresh. Overview retains four delegates; Activity retains 1,000. An Activity reset creates and destroys all 1,000 delegates, with median toggle CPU 2,683.097 ms versus approximately 14 ms model-only CPU. Delegate recreation is the dominant measured cost. The quadratic lookup is real but secondary in this workload.

The model now formats rows from the transaction pointers it already has, using the existing amount formatter and a shared subtitle helper. `detail(rowId)` and `Ledger::find` remain the occasional dialog/copy/reconciliation lookup; they are removed from bulk refresh rather than given a speculative mutable-ledger cache. Both models share one stable pending-first sort. Matching ID sequences keep persistent indexes/delegates and emit only the roles that changed. Changed IDs/order/count retain the reset path. Unchanged displayed refresh has zero data changes, resets or delegate churn; exact toggles update only affected amount roles. At 1,000 records, bulk detail calls and ID comparisons are zero and sort calls are one. Startup still creates all Activity delegates; the eager Repeater remains and peak RSS includes that allocation.

The four-record control, 100-record and 1,000-record cases all improve. Full-history toggle median frame latency falls from 4,243.072 ms to 57.889 ms, about 73 times faster. This does not establish a general product latency SLO or native packaged-platform support. No QML presentation or simulated backend timer changed.

Qt 6.12 sources used for the model notification contract and timing endpoint: [QAbstractItemModel dataChanged](https://doc.qt.io/qt-6/qabstractitemmodel.html#dataChanged), [QQuickWindow frameSwapped](https://doc.qt.io/qt-6/qquickwindow.html#frameSwapped), [Repeater eager creation](https://doc.qt.io/qt-6/qml-qtquick-repeater.html#considerations-when-using-repeater).

## Verification and bindings

`candidate-manifest.json` binds the uninstrumented executable and tracked wallet source to the code commit. The instrumented source manifests and executable hashes are separate; the instrumentation preparer edits disposable source copies only. Normal CMake does not compile or expose benchmark controls. To repeat, copy `wallet-ui/` at the accepted base and candidate into separate disposable directories, run the same `prepare-history-benchmark.py` overlay, build Release through `env.sh`, then use `run-history-benchmark.py` with an owned Xephyr display. `summarize-history-benchmark.py` rejects missing repeats/cases.

`ctest.txt` records all three passing Qt suites. The new activity suite checks original four-row subtitles/order, exact/compact amount roles and full accessible amounts, 1,000 unique mixed-status rows with an independent stable-order oracle, persistent indexes on amount/status updates, and reset behavior when the history is replaced. The same new checks run against baseline core and fail twice on the unwanted resets, preserved in `negative-control-tst_activity.txt`. Existing controller checks retain unknown-submit, stale reply, consent and recovery behavior.

The native author checks use the existing isolated XTest/AT-SPI/portal harness against the uninstrumented candidate. Initial new focus harness H6 looked for a value leaf that the accepted DefRow intentionally hides; its accessible label is `Status: 1 of 10 confirmations`. The harness was corrected to require that labelled status inside the actual Sent dialog. The original failed result is preserved in `focus-first-results.json`; this was a test-oracle repair, not a product fix. Final journey receipts are recorded in the handoff.

Fable assistance is recorded in `fable-report.md` and `fable-receipt.json`, native session `45c93905-311b-4d90-94aa-398f98350fdb`, actual transcript model `claude-fable-5-1`, high effort. It recommended stable-ID dataChanged and direct row formatting and highlighted focus/reconciliation risks. Its claim of roughly one million lookups was corrected by the measured 500,536 comparisons: the recent model processes four rows, not a second full history. Its proposed universal icon-role exclusion was not used; the implementation compares every non-ID role. An advisor was attempted despite the no-recursion brief; the owner interrupted it before output and required the final bounded report. That attempted call supplies no independent acceptance. No silent model fallback or configuration change occurred.

`primary-before.json` records the unrelated primary checkout changes to preserve during lead integration. TJS-2055 and TJS-2018 evidence is unchanged. Signing, installers, releases, network connectors, live funds and consensus/cryptographic work are outside this task.

Needs TJ: None.
