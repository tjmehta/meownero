These ten parts reconstruct the exact native Linux38 archive tested by the writer. Independent acceptance remains pending. The parent owns group delivery; authenticated Board links are not a group download.

Download parts 001 through 010 and SHA256SUMS into one empty directory. Verify every part, reassemble without overwriting an existing archive, and verify all bytes:

```sh
tail -n +2 SHA256SUMS | sha256sum -c -
(set -C; cat linux38-fc4bde3b.tar.gz.part??? > meownero-vanguard-linux38-x86_64.tar.gz)
sha256sum -c SHA256SUMS
```

The final archive is 76,582,444 bytes with SHA256 fc4bde3b0a665bebcd22140fbc67fad2f15b5c841252a18dff0d5c5d79d56743. Extract after verification and follow the included tester guide. Native x64 Ubuntu22 Docker userland passed; minimum glibc is 2.35. Other distribution journeys remain untested here. The archive is unsigned. Its immutable embedded build-time status remains BUILT_UNTESTED; adjacent exact-byte evidence records the later writer journey pass, pending independent review.
