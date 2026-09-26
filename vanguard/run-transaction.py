#!/usr/bin/env python3
"""Build and run the pinned wallet/core integration, offline under the shared lock."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
PIN = json.loads((ROOT / "vanguard/source-lock.json").read_text())


def command(args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return (sorted((ROOT / "vanguard/transaction").iterdir()) +
            [ROOT / "vanguard/boundary/verify.cpp", ROOT / "vanguard/boundary/verify.h",
             ROOT / "vanguard/run-transaction.py", ROOT / "vanguard/verify-transaction.py"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=ROOT / "build/vanguard-src")
    parser.add_argument("--out", type=Path, required=True, help="new evidence directory")
    args = parser.parse_args()
    src, out = args.src.resolve(), args.out.resolve()
    up = src / "monero-fcmp"
    if out.exists():
        raise SystemExit("refusing existing output directory")
    with open("/tmp/meownero-swarm-20260912-heavy.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        if int(mem["MemAvailable"].split()[0]) * 1024 < 5 * 1024**3 or shutil.disk_usage(ROOT).free < 5 * 1024**3:
            raise SystemExit("requires 5 GiB available memory and disk")
        if command(["git", "-C", str(up), "rev-parse", "HEAD"]) != PIN["upstream"]["commit"]:
            raise SystemExit("upstream revision mismatch")
        base = command(["git", "-C", str(up), "show", "HEAD:tests/CMakeLists.txt"]) + "\n"
        cmake = up / "tests/CMakeLists.txt"
        original = cmake.read_text()
        if original != base + "add_subdirectory(vanguard)\nadd_subdirectory(vanguard_boundary)\n":
            raise SystemExit("unexpected upstream CMake injection; use the accepted boundary preparation")
        if command(["git", "-C", str(up), "diff", "HEAD", "--name-only"]).splitlines() != ["tests/CMakeLists.txt"]:
            raise SystemExit("unexpected upstream tracked changes")
        for path, sha in PIN["upstream"]["submodules"].items():
            sub = up / path
            if command(["git", "-C", str(sub), "rev-parse", "HEAD"]) != sha or command(["git", "-C", str(sub), "status", "--porcelain"]):
                raise SystemExit("submodule mismatch: " + path)
        if digest(up / "src/fcmp_pp/fcmp_pp_rust/Cargo.lock") != PIN["rust"]["cargo_lock_sha256"]:
            raise SystemExit("Cargo.lock mismatch")
        oxide = list((src / "cargo-home/git/checkouts").glob("monero-oxide-*/31c26d9"))
        if len(oxide) != 1 or command(["git", "-C", str(oxide[0]), "rev-parse", "HEAD"]) != PIN["rust"]["monero_oxide_rev"] or command(["git", "-C", str(oxide[0]), "diff", "HEAD"]):
            raise SystemExit("monero-oxide source mismatch")
        rust = Path(os.environ.get("RUST_TOOLCHAIN_DIR", str(Path.home() / ".rustup/toolchains/stable-x86_64-unknown-linux-gnu")))
        if command([str(rust / "bin/rustc"), "-V"]) != PIN["builder"]["rustc"]:
            raise SystemExit("Rust toolchain mismatch")
        for name in ("verify.cpp", "verify.h"):
            if (up / "tests/vanguard_boundary" / name).read_bytes() != (ROOT / "vanguard/boundary" / name).read_bytes():
                raise SystemExit("boundary source mismatch")
        target = up / "tests/vanguard_transaction"
        target.mkdir(exist_ok=True)
        owned = sorted((ROOT / "vanguard/transaction").iterdir())
        if any(p.name not in {f.name for f in owned} for p in target.iterdir()):
            raise SystemExit("unexpected transaction injection file")
        for path in owned:
            shutil.copy2(path, target / path.name)
        out.mkdir(parents=True)
        shutil.copy2(ROOT / "vanguard/source-lock.json", out / "source-lock.json")
        receipt = {"commit": command(["git", "rev-parse", "HEAD"], cwd=ROOT),
                   "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sources()},
                   "upstream": PIN["upstream"]["commit"], "monero_oxide": PIN["rust"]["monero_oxide_rev"],
                   "image": PIN["builder"]["image_id"], "rustc": PIN["builder"]["rustc"], "commands": [], "metrics": {}}

        def container(stage, script, readonly=False):
            name = "vanguard-tx-" + str(os.getpid()) + "-" + stage
            argv = ["docker", "run", "--name", name, "--rm", "--pull=never", "--network=none", "--cpus=2",
                    "--memory=4g", "--memory-swap=4g", "--pids-limit=256", "--ulimit", "core=0", "-u", f"{os.getuid()}:{os.getgid()}",
                    "-v", f"{up}:/src" + (":ro" if readonly else ""),
                    "-v", f"{src / 'cargo-home'}:/cargo-home" + (":ro" if readonly else ""),
                    "-v", f"{rust}:/opt/rust:ro", "-v", f"{out}:/out", "-e", "CARGO_HOME=/cargo-home",
                    "-e", "CARGO_NET_OFFLINE=true", "-e", "PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "-w", "/out", receipt["image"], "bash", "-euc",
                    f"trap 'cat /sys/fs/cgroup/memory.peak > /out/{stage}.memory; cat /sys/fs/cgroup/memory.events > /out/{stage}.memory-events' EXIT\n" + script]
            receipt["commands"].append(argv)
            start = time.monotonic()
            try:
                with (out / (stage + ".docker.log")).open("w") as log:
                    result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
                subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            receipt["metrics"][stage] = {"wall_seconds": time.monotonic() - start, "exit": code}
            (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            if code:
                raise SystemExit(f"{stage} failed; see {out}")

        try:
            cmake.write_text(original + "add_subdirectory(vanguard_transaction)\n")
            (out / "upstream-injection.diff").write_text(command(["git", "-C", str(up), "diff", "HEAD"]) + "\n")
            container("build", """
cd /src/build/vanguard
cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON ../.. > /out/cmake.log 2>&1
make -j1 vanguard_transaction_tests > /out/make.log 2>&1
g++ --version > /out/gxx.txt
rustc -vV > /out/rustc.txt
""")
            binary = up / "build/vanguard/tests/vanguard_transaction/vanguard_transaction_tests"
            receipt["binary"] = {"sha256": digest(binary), "bytes": binary.stat().st_size}
            for run in ("run1", "run2"):
                container(run, f"""
mkdir /out/{run}
cd /out/{run}
/src/build/vanguard/tests/vanguard_transaction/vanguard_transaction_tests /tmp/vanguard-chain > stdout.log 2> stderr.log
""", readonly=True)
        finally:
            cmake.write_text(original)
        (out / "MANIFEST.sha256").write_text("".join(f"{digest(p)}  {p.relative_to(out)}\n" for p in sorted(out.rglob("*")) if p.is_file()))
        subprocess.run(["python3", "-B", str(ROOT / "vanguard/verify-transaction.py"), str(out)], check=True)


if __name__ == "__main__":
    main()
