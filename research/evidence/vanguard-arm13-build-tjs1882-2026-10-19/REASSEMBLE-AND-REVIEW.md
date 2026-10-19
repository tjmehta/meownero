This exact Windows ARM64 candidate is BUILT_UNTESTED and is for independent review. Native Windows acceptance and group delivery remain pending. The full seven-target release remains OPEN with four accepted targets.

Archive: meownero-vanguard-windows-aarch64.zip
Bytes: 66636343
SHA256: fff26ea94928d2756cbf4b4b59bd2277a685e980d482cf389c8be405617ae15d

Download all eight numbered parts beside SHA256SUMS. Verify each part first. Reassemble in numeric order using Python on any platform:

```python
from pathlib import Path
import hashlib
names = [Path(f"meownero-vanguard-windows-aarch64.zip.part-{i:04d}") for i in range(1, 9)]
expected = dict(line.split(maxsplit=1)[::-1] for line in Path("SHA256SUMS").read_text().splitlines())
archive = Path("meownero-vanguard-windows-aarch64.zip")
with archive.open("xb") as out:
    for part in names:
        data = part.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected[part.name]
        out.write(data)
assert archive.stat().st_size == 66636343
assert hashlib.sha256(archive.read_bytes()).hexdigest() == "fff26ea94928d2756cbf4b4b59bd2277a685e980d482cf389c8be405617ae15d"
```

Extract into a new directory and read TESTER.md and release.json. Native ARM64 Windows hardware, native ARM64 CPython3.13+, ARMv8 crypto and the existing capacity reserves are required for qualification. Declared minimum Windows10v1709 is not runtime-certified. All three programs are unsigned. This runs disposable, valueless local regtest only; no shared public network is provided.

The separate staged CI payload contains exact inputs, source and workflow; copy numbered parts to the paths in ci-inputs.json. It is not published or dispatched. Parent must arrange independent delta review and freshly confirm included capacity/storage, then publish inputs FIRST with exact remote hash readback and workflow LAST to the private tjs1882-native-windows-arm13 branch. No paid/settings/public-source route. Native acceptance needs full5/2/type7/CARROT/restore/nativeCLI journey, ten controls and zero owned processes against these exact bytes.

Board attachment URLs require authentication and are not a public group route. Parent owns the eventual website/group distribution after acceptance; do not send these parts as WhatsApp media attachments.
