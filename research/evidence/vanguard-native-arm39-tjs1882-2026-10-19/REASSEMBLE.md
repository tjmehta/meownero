ARM39 Linux aarch64 candidate; independent artifact acceptance pending.

Put all nine numbered parts and PARTS.SHA256SUMS in one fresh directory. Verify every part, concatenate explicitly in numerical order, then verify the whole archive before extracting.

```sh
sha256sum -c PARTS.SHA256SUMS
cat meownero-vanguard-aarch64.tar.gz.part001 meownero-vanguard-aarch64.tar.gz.part002 meownero-vanguard-aarch64.tar.gz.part003 meownero-vanguard-aarch64.tar.gz.part004 meownero-vanguard-aarch64.tar.gz.part005 meownero-vanguard-aarch64.tar.gz.part006 meownero-vanguard-aarch64.tar.gz.part007 meownero-vanguard-aarch64.tar.gz.part008 meownero-vanguard-aarch64.tar.gz.part009 > meownero-vanguard-aarch64.tar.gz
sha256sum -c SHA256SUMS
mkdir meownero-arm39
tar -xzf meownero-vanguard-aarch64.tar.gz -C meownero-arm39
cd meownero-arm39/meownero-vanguard-aarch64
python3 -B tester.py preflight
```

On macOS use `shasum -a 256 -c` in place of `sha256sum -c`. This ELF package executes on Linux ARM64, requiring glibc 2.35+, Python 3.8+ and ARMv8 crypto instructions (AES/PMULL/SHA1/SHA2). It is unsigned. Use the included TESTER.md for a fresh disposable valueless regtest payment/receive/restore/later-spend journey. No shared public network is supplied.

The immutable in-archive release.json intentionally records its build-time BUILT_UNTESTED status. The separately bound native receipts record later Ubuntu 22.04 and Debian 12 userland execution of these exact bytes; they do not change independent acceptance.

Parent owns group delivery after independent acceptance. Each part is at most 8 MiB, fitting the existing WhatsApp document route (50 MiB cap) and Paperclip attachment limit (10 MB). Authenticated board links are reviewer downloads, not a public group route. Parent can use these local export files or authenticated task downloads, then send the nine documents and checksum/instruction files using the existing approved gateway route. No group send occurred in this run.
