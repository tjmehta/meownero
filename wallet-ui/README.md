# Meownero Wallet: native shell with a simulated backend

This is a compiled C++/Qt Quick (QML) 6.12.0 desktop app. It implements the
accepted wallet design (`docs/design/gui-wallet/`, revision 5) against an
explicitly simulated wallet engine and node. **No wallet, daemon, network,
real address or genuine seed is connected or accepted.** Every screen says it
is a local regtest with test coins, and the ribbon says the build is
simulated. The design rationale is in `docs/adr/ADR-002-native-wallet-ui.md`.
`docs/design/gui-wallet/native-handoff.md` holds the scope.

It is unsigned and local. There is no package, installer, updater or release.
The only tested host is Linux x86_64. Nothing here establishes Windows, macOS
or packaged Linux support.

## Layout

| Path | What it owns |
| --- | --- |
| `src/amount.*` | Exact atomic-unit parsing and formatting. Port of the prototype's `parseAmount`/`fmt` and `PARSER_CASES`, with the system locale's decimal separator |
| `src/ledger.*` | Simulated history, balance rules (total vs unlocked, 60/10-block unlock), status text |
| `src/simulatedbackend.*` | Deterministic, asynchronous fake engine/node with typed calls only. It opens no socket, file or process |
| `src/walletcontroller.*` | The one controller QML talks to. It owns session identity, prepared payments and review tokens, consent tokens, stale-reply refusal, unknown-submit reconciliation, recovery-word lifetime, lock and the allowlisted diagnostics |
| `src/activitymodel.*` | Display rows for Activity/Overview |
| `qml/` | Standard Qt Quick Controls (Basic style) with the accepted tokens in `Theme.qml`. QML gets display values and actions only |
| `qml/ReviewerFixtures.qml` | Separate reviewer window that stages simulated states. Opened only with `--reviewer-fixtures`; not part of the app's interaction model |
| `tests/` | QtTest suites for amounts and controller state |

## Build (Linux x86_64, no sudo)

The toolchain is open-source Qt 6.12.0 from the official mirror, installed by
aqtinstall into a user directory. It also needs two Ubuntu packages, extracted
rather than installed: `libxcb-cursor0` (runtime) and the GL/EGL headers.

```sh
T=~/.local/share/meownero/toolchain
python3 -m venv $T/venv && $T/venv/bin/pip install aqtinstall==3.3.0 ninja
$T/venv/bin/aqt install-qt linux desktop 6.12.0 linux_gcc_64 --outputdir $T/qt \
    --archives icu qtbase qtdeclarative
mkdir -p $T/debs $T/sysroot && cd $T/debs
apt-get download libxcb-cursor0 libgl-dev libglx-dev libopengl-dev mesa-common-dev libegl-dev
for d in *.deb; do dpkg-deb -x $d $T/sysroot; done
cd $T/sysroot/usr/lib/x86_64-linux-gnu
for l in libGL libGLX libOpenGL libEGL; do ln -sf $(ls /usr/lib/x86_64-linux-gnu/$l.so.? | head -1) $l.so; done
```

Then, from the repository root:

```sh
source wallet-ui/env.sh
cmake -S wallet-ui -B wallet-ui/build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build wallet-ui/build
(cd wallet-ui/build && ctest --output-on-failure)
sha256sum wallet-ui/build/meownero-wallet
```

`env.sh` sets `QT_RCC_SOURCE_DATE_OVERRIDE` and `SOURCE_DATE_EPOCH`, and
`CMakeLists.txt` maps source and build paths. With the same toolchain, a clean
build in any directory produces the same executable bytes. That was checked by
building in two different directories.

## Run

```sh
source wallet-ui/env.sh
wallet-ui/build/meownero-wallet                       # first run (Welcome)
wallet-ui/build/meownero-wallet --start overview      # simulated fixture wallet, unlocked
wallet-ui/build/meownero-wallet --start unlock        # fixture wallet, locked (password: simulated)
wallet-ui/build/meownero-wallet --story dust|large|empty|normal --reviewer-fixtures
```

Shortcuts: Ctrl+1–6 for the sections, Ctrl+L to lock, Escape to close
dialogs, and the standard copy shortcut on a focused address or transaction ID
(⌘ on macOS, where the platform maps it). Settings (⌘,) maps to the Wallet
page where the platform defines that key.

## Simulated behaviour you should know

- The fixture wallet's password is `simulated`. A wallet created or restored
  in the session uses the password chosen for it, and only a digest of it is
  kept in memory.
- Recovery words are fixed sample words that cannot form a valid phrase.
  Restore accepts only those words; anything else is refused. Typed words are
  cleared after the restore step and are never written anywhere.
- Fees, txids and addresses are fixtures. Regtest sends only to the two kit
  wallets. The testnet view is a labelled design preview.
- "Get test coins" simulates `generateblocks`. Reviewer fixtures stage node
  and engine states, reorgs, send outcomes (accepted, refused, connection
  drops) and how an unknown submission resolves.

## Boundaries kept

No WebEngine, WebView, remote QML, network access, credentials in QML,
Docker, `vanguard/`, `chain/`, CI or source-lock changes. The live connector
does not exist. `SimulatedBackend` stands where the authenticated loopback
wallet RPC client will go; see the route proposal in
`research/evidence/native-wallet-tjs2018-2026-10-10/README.md`.
