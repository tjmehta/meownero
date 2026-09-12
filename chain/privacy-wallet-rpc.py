#!/usr/bin/env python3
"""Startup wallet-to-daemon controls for the pinned wallet RPC, NOT a network sandbox.

The authenticated local RPC controller can change TLS/trust with set_daemon.
OpenAlias RPC/address lookups can use DNS outside SOCKS despite --no-dns.
Use literal native addresses in the controlling application; application-level
OpenAlias enforcement remains unimplemented. No process-wide anonymity claim.
See research/swarm-privacy-2026-09-12.md for evidence and trust assumptions.
"""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit


def port(value):
    if not re.fullmatch(r"[0-9]{1,5}", value) or not 1 <= int(value) <= 65535:
        raise argparse.ArgumentTypeError("port must be 1..65535")
    return str(int(value))


def proxy(value):
    try:
        host, number = value.split(":")
        if not ipaddress.IPv4Address(host).is_loopback:
            raise ValueError()
        return f"{host}:{port(number)}"
    except (ValueError, argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError("proxy must be a numeric loopback IPv4:port") from None


def daemon(value, fingerprint):
    # Reject parser normalization, credentials, URL paths and option injection.
    if not value.isascii() or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("daemon URL must be ASCII without whitespace")
    parsed = urlsplit(value)
    if parsed.username is not None or parsed.password is not None or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("daemon URL must have only scheme, host and explicit port")
    host = parsed.hostname or ""
    number = port(str(parsed.port or 0))
    if parsed.netloc != f"{host}:{number}":
        raise ValueError("daemon URL must use a canonical lowercase host and explicit port")
    if host.endswith(".onion"):
        if not re.fullmatch(r"[a-z2-7]{56}\.onion", host) or parsed.scheme != "http" or fingerprint:
            raise ValueError("onion mode requires http://<56-character-onion>:port without a TLS fingerprint")
        # Tor validates the onion checksum and authenticates the service, not this launcher.
        return value, ["--daemon-ssl", "disabled"]
    if parsed.scheme != "https" or not fingerprint or not re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint):
        raise ValueError("clearnet mode requires HTTPS and a SHA-256 certificate fingerprint (64 hex characters)")
    if len(host) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
        raise ValueError("unsupported daemon hostname (IPv4 or ASCII DNS name required)")
    return value, ["--daemon-ssl", "enabled", "--daemon-ssl-allowed-fingerprints", fingerprint.lower()]


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--binary", required=True, type=Path, help="verified monero-wallet-rpc binary")
    parser.add_argument("--state-dir", required=True, type=Path, help="private wallet/RPC state directory")
    parser.add_argument("--rpc-port", required=True, type=port)
    parser.add_argument("--proxy", required=True, type=proxy)
    parser.add_argument("--daemon", required=True)
    parser.add_argument("--daemon-fingerprint")
    args = parser.parse_args()
    try:
        address, tls = daemon(args.daemon, args.daemon_fingerprint)
        binary = args.binary.resolve(strict=True)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError("binary must be an executable file")
        os.umask(0o077)
        args.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        state = args.state_dir.resolve(strict=True)
        info = state.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("state directory must be owned by this user with no group/other permissions")
    except (OSError, ValueError, argparse.ArgumentTypeError) as error:
        parser.error(str(error))
    os.chdir(state)
    argv = [str(binary), "--wallet-dir", str(state / "wallets"),
            "--rpc-bind-ip", "127.0.0.1", "--rpc-bind-port", args.rpc_port,
            "--proxy", args.proxy, "--daemon-address", address, "--untrusted-daemon",
            "--no-dns", "--shared-ringdb-dir", str(state / "ringdb"),
            "--log-file", str(state / "wallet-rpc.log"), "--log-level", "0",
            "--max-log-file-size", "1048576", "--max-log-files", "2",
            "--max-concurrency", "1", *tls]
    # Upstream creates a mode-0600 random RPC login file in state. No auth override,
    # config file, arbitrary extra arguments, proxy preflight or direct retry.
    os.execv(str(binary), argv)


if __name__ == "__main__":
    main()
