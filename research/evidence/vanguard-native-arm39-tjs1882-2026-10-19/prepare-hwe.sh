#!/bin/bash
set -euo pipefail
umask 077
install -d -m 700 /var/lib/tjs1882/qualification-hwe
cd /var/lib/tjs1882/qualification-hwe
test "$(uname -m)" = aarch64
test "$(getconf GNU_LIBC_VERSION)" = 'glibc 2.35'
dpkg-query -W -f='${binary:Package}=${Version}\n' > packages-before.txt
apt-cache policy linux-image-generic-hwe-22.04 > candidate.txt
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o APT::Keep-Downloaded-Packages=true --download-only install -y --no-install-recommends linux-image-generic-hwe-22.04=6.8.0-138.138~22.04.1
sha256sum /var/cache/apt/archives/*.deb > downloaded-debs.sha256
DEBIAN_FRONTEND=noninteractive apt-get --no-download install -y --no-install-recommends linux-image-generic-hwe-22.04=6.8.0-138.138~22.04.1
dpkg-query -W -f='${binary:Package}=${Version}\n' > packages-after.txt
sha256sum /var/lib/apt/lists/*InRelease > repository-inrelease.sha256
sha256sum /boot/vmlinuz-6.8.0-138-generic /boot/initrd.img-6.8.0-138-generic > boot-files.sha256
printf '%s\n' PASS_PINNED_HWE_INSTALL_REBOOT_REQUIRED
