#!/usr/bin/env python3
"""Re-derive the Vanguard V1 (TJS-356) claims from an evidence directory written by vanguard/build.sh.

Usage: vanguard/verify.py [research/evidence/vanguard-tjs356-2026-09-23]

It checks the manifest, the pins against vanguard/source-lock.json, run-to-run determinism,
per-vector verdicts and required coverage, and the only permitted findings (VG-F1, VG-F2). It
also decodes every CARROT address in results.json with an independent base58/Keccak-256
decoder, so network prefixes, checksums and embedded keys are not taken on the harness's word.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / 'vanguard' / 'source-lock.json'
FIXED = [1, 2, 4, 8, 128]
FRESH = [1, 2]
DESTINATIONS = ['main', 'subaddress_1_0', 'subaddress_2_7', 'integrated']
NETS = ['mainnet', 'testnet', 'stagenet']
# (standard, integrated, subaddress) prefixes, src/cryptonote_config.h at the pin
PREFIXES = {'mainnet': (18, 19, 42), 'testnet': (53, 54, 63), 'stagenet': (24, 25, 36)}
PAYMENT_ID = bytes(range(0xa0, 0xa8))
# Regression pins from the first run at the upstream pin (valueless, derived from public labels)
ALICE_SPEND = '8a00cf5798092b00484c9081dcd290e2d17dca32ec0fd54ab143ac4f10897802'
ALICE_VIEW = 'bf8390507be86c22af247133f355733c3f6a348e0aa90293ed61883a0ef3f0f6'
ALICE_TESTNET = ('9xPyTHP3WJE13juj2MSU39ewRUDSAgnHSDVcPnLgZWHu1TfHKiNnr1H6oUpiHpDexzB5Ujzig5LnuRk5dVtMBUwyUqxS5yz')
FINDINGS = {
    'VG-F1': (re.compile(r'^fcmp_pp\.(fixed_\d+in|fresh_\d+in)\.extended_1_byte$'), 'accept'),
    'VG-F2': (re.compile(r'^fcmp_pp\.fixed_\d+in\.wrong_n_layers_minus_1$'), 'reject_abort_signal_6'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Keccak-256 (original padding, as Monero's cn_fast_hash) -------------------------------------
RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
      0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
      0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
      0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
      0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
M64 = (1 << 64) - 1


def keccak_f(a):
    for rc in RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & M64) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                r = ROT[x][y]
                b[y][(2 * x + 3 * y) % 5] = ((a[x][y] << r) | (a[x][y] >> (64 - r))) & M64 if r else a[x][y]
        a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def keccak256(data):
    rate = 136
    pad = rate - len(data) % rate
    padded = data + (b'\x81' if pad == 1 else b'\x01' + b'\x00' * (pad - 2) + b'\x80')
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(padded), rate):
        block = padded[off:off + rate]
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(block[8 * i:8 * i + 8], 'little')
        a = keccak_f(a)
    return b''.join(a[i % 5][i // 5].to_bytes(8, 'little') for i in range(4))


# --- Monero base58 and ed25519 point check -------------------------------------------------------
ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
BLOCK_SIZES = [0, 2, 3, 5, 6, 7, 9, 10, 11]


def b58decode(s):
    out = bytearray()
    for off in range(0, len(s), 11):
        chunk = s[off:off + 11]
        n = BLOCK_SIZES.index(len(chunk))
        value = 0
        for ch in chunk:
            value = value * 58 + ALPHABET.index(ch)
        require(value < 1 << (8 * n), f'base58 block overflow in {s}')
        out += value.to_bytes(n, 'big')
    return bytes(out)


def varint(data):
    value, shift = 0, 0
    for i, byte in enumerate(data):
        value |= (byte & 0x7f) << shift
        shift += 7
        if not byte & 0x80:
            return value, data[i + 1:]
    raise ValueError('unterminated varint')


P = 2**255 - 19
D = (-121665 * pow(121666, P - 2, P)) % P


def is_ed25519_point(b):
    y = int.from_bytes(b, 'little') & ((1 << 255) - 1)
    if y >= P:
        return False
    u, v = (y * y - 1) % P, (D * y * y + 1) % P
    x2 = u * pow(v, P - 2, P) % P
    if x2 == 0:
        return not b[31] & 0x80
    return pow(x2, (P - 1) // 2, P) == 1


def decode_address(s):
    raw = b58decode(s)
    body, checksum = raw[:-4], raw[-4:]
    require(keccak256(body)[:4] == checksum, f'checksum mismatch in {s}')
    prefix, rest = varint(body)
    require(len(rest) in (64, 72), f'unexpected payload length {len(rest)} in {s}')
    return prefix, rest[:32].hex(), rest[32:64].hex(), rest[64:]


def main():
    work = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'research/evidence/vanguard-tjs356-2026-09-23')
    lock = json.loads(LOCK.read_text())
    require(keccak256(b'').hex() == 'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470',
            'Keccak-256 self-test failed')
    require(keccak256(b'abc').hex() == '4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45',
            'Keccak-256 self-test failed')

    # 1. The manifest covers every evidence file byte for byte, and nothing else.
    listed = dict(line.split('  ', 1)[::-1] for line in (work / 'MANIFEST.sha256').read_text().splitlines())
    present = {'./' + str(p.relative_to(work)) for p in work.rglob('*') if p.is_file() and p.name != 'MANIFEST.sha256'}
    require(set(listed) == present, f'manifest/file mismatch: {sorted(set(listed) ^ present)}')
    for name, digest in listed.items():
        require(sha256(work / name) == digest, f'hash mismatch for {name}')

    # 2. Pins: the evidence was produced from exactly the committed source lock.
    require((work / 'source-lock.json').read_bytes() == LOCK.read_bytes(), 'evidence source-lock.json != vanguard/source-lock.json')
    require((work / 'upstream-head.txt').read_text().strip() == lock['upstream']['commit'], 'upstream HEAD != pin')
    submodules = {line.split()[1]: line.split()[0].lstrip('+-U') for line in (work / 'upstream-submodules.txt').read_text().splitlines()}
    require(submodules == lock['upstream']['submodules'], f'submodules != pin: {submodules}')
    require((work / 'cargo-lock.sha256').read_text().split()[0] == lock['rust']['cargo_lock_sha256'], 'Cargo.lock != pin')
    toolchain = (work / 'toolchain.txt').read_text()
    require(f"image_id={lock['builder']['image_id']}\n" in toolchain, 'builder image != pin')
    require(f"rustc: {lock['builder']['rustc']};" in toolchain, 'rustc != pin')
    status = (work / 'upstream-injection-status.txt').read_text().splitlines()
    require(sorted(status) == sorted([' M tests/CMakeLists.txt', '?? tests/vanguard/CMakeLists.txt', '?? tests/vanguard/vanguard_tests.cpp']),
            f'upstream tree carries more than the harness injection: {status}')
    require((work / 'upstream-injection.diff').read_text().count('\n+add_subdirectory(vanguard)\n') == 1, 'injection diff')
    harness = dict(line.split('  ', 1)[::-1] for line in (work / 'harness-source.sha256').read_text().splitlines())
    require(harness == {n: sha256(ROOT / 'vanguard/harness' / n) for n in ('CMakeLists.txt', 'vanguard_tests.cpp')},
            'evidence was built from a different harness source than vanguard/harness')
    artifacts = [line.split() for line in (work / 'artifacts.txt').read_text().splitlines()]
    require([a[2] for a in artifacts] == ['src/fcmp_pp/fcmp_pp_rust/libfcmp_pp_rust.a', 'src/fcmp_pp/libfcmp_pp.a',
                                          'src/carrot_core/libcarrot_core.a', 'src/carrot_impl/libcarrot_impl.a',
                                          'tests/vanguard/vanguard_tests'], 'artifact list')
    require(all(re.fullmatch(r'[0-9a-f]{64}', a[0]) and int(a[1]) > 0 for a in artifacts), 'artifact receipts malformed')
    build = json.loads((work / 'build-metrics.json').read_text())
    require(build['build_wall_seconds'] > 0 and build['container_memory_peak_bytes'] > 0, 'build metrics missing')

    # 3. Determinism: results.json is byte-identical across the two runs.
    require((work / 'run1/results.json').read_bytes() == (work / 'run2/results.json').read_bytes(), 'run1/run2 results differ')
    results = json.loads((work / 'run1/results.json').read_text())
    require(results['schema'] == 'meownero-vanguard-results/1', 'results schema')
    vectors = {v['id']: v for v in results['vectors']}
    require(len(vectors) == len(results['vectors']), 'duplicate vector ids')

    # 4. Verdicts: every vector matches its expectation, or carries one of the two documented findings exactly.
    known = 0
    for v in results['vectors']:
        matches = v['observed'] == 'accept' if v['expect'] == 'accept' else v['observed'].startswith('reject')
        if v['finding']:
            pattern, observed = FINDINGS[v['finding']]
            require(pattern.match(v['id']) and v['observed'] == observed, f"finding {v['finding']} misapplied to {v['id']}")
            known += 1
        else:
            require(matches, f"{v['id']}: expected {v['expect']}, observed {v['observed']}")
        require(v['pass'] is True, f"{v['id']} not marked pass")
    summary = results['summary']
    require(summary == {'total': len(vectors), 'passed': len(vectors), 'known_findings': known, 'failed': 0}, f'summary {summary}')
    for name, (pattern, _) in FINDINGS.items():
        require(any(v['finding'] == name for v in results['vectors']), f'{name} did not reproduce')
    require(all(vectors[f'fcmp_pp.{k}.extended_1_byte']['finding'] == 'VG-F1' for k in
                [f'fixed_{n}in' for n in FIXED] + [f'fresh_{n}in' for n in FRESH]), 'VG-F1 not on every extended vector')

    # 5. Coverage required by TJS-356.
    def expect(vid, verdict):
        require(vid in vectors, f'missing vector {vid}')
        require(vectors[vid]['expect'] == verdict, f'{vid} expects {vectors[vid]["expect"]}')
        return vectors[vid]

    for n in FIXED:
        p = f'fcmp_pp.fixed_{n}in.'
        require('layout_ok=true' in expect(p + 'valid', 'accept')['detail'], f'{p}valid layout')
        for s in ['flip_input_tuple_byte0', 'flip_sal_proof_byte0', 'flip_membership_first_byte', 'flip_membership_middle_byte',
                  'flip_membership_last_byte', 'truncated_1_byte', 'wrong_tree_root', 'wrong_n_layers_plus_1',
                  'wrong_signable_tx_hash', 'wrong_key_image', 'wrong_pseudo_out'] + (['swapped_key_images', 'swapped_pseudo_outs'] if n >= 2 else []):
            expect(p + s, 'reject')
    for n in FRESH:
        p = f'fcmp_pp.fresh_{n}in.'
        detail = dict(kv.split('=') for kv in expect(p + 'valid', 'accept')['detail'].split())
        require(detail['proof_bytes'] == detail['expected_bytes'], f'{p}valid proof length')
        for s in ['truncated_1_byte', 'wrong_n_layers_plus_1', 'wrong_n_layers_minus_1', 'rererandomized_input', 'non_member_input',
                  'flip_input_C_tilde_byte0'] + (['swapped_inputs'] if n >= 2 else []):
            expect(p + s, 'reject')
        require(sum(1 for vid in vectors if vid.startswith(p + 'flip_byte_')) == 3, f'{p} byte flips')
    expect('fcmp_pp.fresh_1in.old_root_proof_vs_old_root', 'accept')
    expect('fcmp_pp.fresh_1in.old_root_proof_vs_grown_root', 'reject')
    require('key_image_matches_legacy=true' in expect('sal.valid', 'accept')['detail'], 'SA/L key image != legacy key image')
    for s in ['wrong_signable_tx_hash', 'wrong_key_image', 'other_rerandomization_of_same_output', 'prove_with_wrong_x']:
        expect('sal.' + s, 'reject')
    for s in ['main', 'subaddress_1_0']:
        expect(f'carrot.scan.{s}.recipient_view_key', 'accept')
        for t in ['other_account_view_key', 'view_tag_flipped', 'input_context_changed', 'amount_commitment_replaced', 'encrypted_amount_flipped']:
            expect(f'carrot.scan.{s}.{t}', 'reject')

    # 6. CARROT addresses, decoded independently of the upstream decoder.
    keys = dict(kv.split('=') for kv in expect('carrot.keys.main_view_pubkey_is_kv_G', 'accept')['detail'].split())
    require(keys == {'K_s': ALICE_SPEND, 'K0_v': ALICE_VIEW}, f'CARROT key hierarchy drifted from the pin: {keys}')
    sub_spends = {}
    for dest in DESTINATIONS:
        for net in NETS:
            p = f'carrot.address.{dest}.{net}.'
            address = expect(p + 'round_trip', 'accept')['detail'].removeprefix('address=')
            prefix, spend, view, pid = decode_address(address)
            standard, integrated, sub = PREFIXES[net]
            require(prefix == {'main': standard, 'integrated': integrated}.get(dest, sub), f'{p} prefix {prefix}')
            if dest in ('main', 'integrated'):
                require((spend, view) == (ALICE_SPEND, ALICE_VIEW), f'{p} keys')
            else:
                require(spend != ALICE_SPEND and view != ALICE_VIEW, f'{p} subaddress reuses main keys')
                sub_spends.setdefault(dest, set()).add(spend)
            require(pid == (PAYMENT_ID if dest == 'integrated' else b''), f'{p} payment id')
            for other in NETS:
                if other != net:
                    expect(p + f'decoded_as_{other}', 'reject')
            expect(p + 'checksum_char_changed', 'reject')
            expect(p + 'truncated_1_char', 'reject')
    require(all(len(v) == 1 for v in sub_spends.values()) and len(set.union(*sub_spends.values())) == 2,
            'subaddress spend keys must be stable across networks and distinct from each other')
    require(vectors['carrot.address.main.testnet.round_trip']['detail'] == f'address={ALICE_TESTNET}', 'testnet main address drifted')

    bad = dict(kv.split('=') for kv in expect('carrot.address.main.testnet.invalid_spend_point', 'reject')['detail'].split())
    index = int(bad['non_point_index'])
    for i in range(index + 1):
        candidate = keccak256(f'meownero-vanguard-tjs356/non-point/{i}'.encode())
        require(is_ed25519_point(candidate) == (i < index), f'non-point search disagrees at index {i}')
    require(keccak256(f'meownero-vanguard-tjs356/non-point/{index}'.encode()).hex() == bad['spend_bytes'], 'non-point bytes')

    # 7. Resource receipts for both runs.
    for run in ('run1', 'run2'):
        metrics = json.loads((work / run / 'metrics.json').read_text())
        require(metrics['schema'] == 'meownero-vanguard-metrics/1', f'{run} metrics schema')
        require(metrics['total_wall_seconds'] > 0 and metrics['peak_rss_kib'] > 0, f'{run} metrics')
        random_ids = {vid for vid in vectors if vid.startswith(('fcmp_pp.fresh', 'sal.'))}
        require(set(metrics['random_input_observed']) == random_ids, f'{run} raw observations incomplete')
        require(json.loads((work / run / 'container.json').read_text())['container_memory_peak_bytes'] > 0, f'{run} container peak')
        require(f'vectors={len(vectors)} failed=0' in (work / run / 'stdout.log').read_text(), f'{run} stdout summary')

    print(f'PASS_VANGUARD_RECEIPTS vectors={len(vectors)} known_findings={known} '
          f"upstream={lock['upstream']['commit'][:12]} addresses_decoded={len(DESTINATIONS) * len(NETS)}")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as e:
        print(f'FAIL {e}')
        sys.exit(1)
