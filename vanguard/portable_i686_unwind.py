"""Bind the pinned x86 compatibility stub to the real GNU DW2 runtime.

Only the COFF storage class of the empty ABI stub changes. All source, code,
data, relocations, archive members and symbol names remain byte-identical.
This adaptation is specific to the pinned GNU i686 toolchain; native execution
and the exception probe still require a Windows runner.
"""
import hashlib
import json
from pathlib import Path
import re
import struct


def sha(data):
    return hashlib.sha256(data).hexdigest()


def adapt(build, output):
    source = build / 'src/fcmp_pp/fcmp_pp_rust/src/lib.rs'
    stub = '#[cfg(all(target_os = "windows", target_arch = "x86"))]\n#[no_mangle]\npub extern "C" fn _Unwind_Resume() {}'
    assert source.read_text().count(stub) == 1, 'unrecognized ABI compatibility stub'
    archive = build / 'build/portable/src/fcmp_pp/fcmp_pp_rust/libfcmp_pp_rust.a'
    original = archive.read_bytes()
    assert original[:8] == b'!<arch>\n'
    members, names, offset = [], b'', 8
    while offset < len(original):
        header = original[offset:offset + 60]
        assert len(header) == 60 and header[58:] == b'`\n'
        size = int(header[48:58])
        name = header[:16].decode().strip()
        start = offset + 60
        data = original[start:start + size]
        assert len(data) == size
        if name == '//':
            names = data
        elif name.startswith('/') and name[1:].isdigit():
            name = names[int(name[1:]):].split(b'/\n', 1)[0].decode()
        else:
            name = name.rstrip('/')
        members.append({'name': name, 'sha256': sha(data), 'offset': start, 'bytes': size})
        offset = start + size + size % 2
    assert offset == len(original)
    selected = [m for m in members if re.fullmatch(r'fcmp_pp_rust-[0-9a-f]+\.fcmp_pp_rust\.[0-9a-f]+-cgu\.0\.rcgu\.o', m['name'])]
    assert len(selected) == 1, 'ambiguous main Rust object'
    member = selected[0]
    data = original[member['offset']:member['offset'] + member['bytes']]
    machine, sections, stamp, symoff, count, optional, flags = struct.unpack_from('<HHIIIHH', data)
    assert machine == 0x14c and optional == 0
    strtab = symoff + count * 18
    found, index = [], 0
    while index < count:
        raw, value, section, kind, storage, auxiliary = struct.unpack_from('<8sIhHBB', data, symoff + 18 * index)
        name = (data[strtab + struct.unpack_from('<I', raw, 4)[0]:].split(b'\0', 1)[0]
                if raw[:4] == b'\0' * 4 else raw.split(b'\0', 1)[0])
        if name == b'__Unwind_Resume':
            assert value == 0 and section == 1 and kind == 32 and storage == 2 and auxiliary == 0
            found.append(member['offset'] + symoff + 18 * index + 16)
        index += 1 + auxiliary
    assert len(found) == 1, 'unrecognized strong stub symbol'
    changed = bytearray(original)
    changed[found[0]] = 105  # GNU COFF weak storage class, as emitted by objcopy.
    assert len(changed) == len(original)
    assert [i for i, (a, b) in enumerate(zip(original, changed)) if a != b] == found
    archive.write_bytes(changed)
    record = {'kind': 'compiled ABI metadata only', 'source_sha256': sha(source.read_bytes()),
              'archive_before_sha256': sha(original), 'archive_after_sha256': sha(changed),
              'member': member['name'], 'changed_byte_offset': found[0], 'before': 2, 'after': 105,
              'all_other_archive_bytes_unchanged': True, 'native_exception_probe': 'UNTESTED',
              'members_before': members, 'link_maps': {}}
    for target, program in [('src/daemon/CMakeFiles/daemon.dir', 'monerod'),
                            ('src/simplewallet/CMakeFiles/simplewallet.dir', 'monero-wallet-cli'),
                            ('src/wallet/CMakeFiles/wallet_rpc_server.dir', 'monero-wallet-rpc')]:
        link = build / 'build/portable' / target / 'link.txt'
        text = link.read_text()
        assert 'mingw32-g++-posix ' in text and '--allow-multiple-definition' not in text
        map_path = output / (program + '.map')
        modified = text.replace('mingw32-g++-posix ', 'mingw32-g++-posix -Wl,-Map,' + str(map_path) + ' ', 1)
        link.write_text(modified)
        record['link_maps'][program] = {'path': str(map_path), 'link_before_sha256': sha(text.encode()), 'link_after_sha256': sha(modified.encode())}
    (output / 'i686-unwind-adaptation.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    adapt(Path('/out/monero-fcmp'), Path('/out'))
