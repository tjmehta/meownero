#!/usr/bin/env python3
"""Pinned P2Pool source slices and a mainnet-only experimental profile gate.

No live RPC, shares, PPLNS, output construction or payouts. Wallet decoding keeps
upstream checksum/curve checks; its non-enforcing FCMP warning is removed, not
stubbed as successful. See generated adaptation diffs and the track report.
"""
import difflib
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from source_probe import build as stock_probe, function

HERE = Path(__file__).resolve().parent
# Read the public fixture without importing the historical executable daemon probe.
ADDRESS = ast.literal_eval(re.search(r"^ADDRESS = (.+)$", (HERE / 'devnet_probe.py').read_text(), re.M)[1])
MAX = 2**64 - 1
ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
SIZES = [0, 2, 3, 5, 6, 7, 9, 10, 11]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, files):
    for name, expected in files.items():
        if sha(root / name) != expected:
            raise ValueError('source mismatch: ' + name)


def literal(source, pattern):
    return re.search(pattern, source, re.S).group()


def change(source, before, after):
    if source.count(before) != 1:
        raise ValueError('ambiguous adaptation: ' + before)
    return source.replace(before, after)


def base58(data):
    result = ''
    for i in range(0, len(data), 8):
        part = data[i:i+8]
        n = int.from_bytes(part, 'big')
        encoded = ''
        while n:
            n, digit = divmod(n, 58)
            encoded = ALPHABET[digit] + encoded
        result += encoded.rjust(SIZES[len(part)], '1')
    return result


def decode_fixture(address):
    data = b''
    for i in range(0, len(address), 11):
        part = address[i:i+11]
        n = 0
        for char in part:
            n = n * 58 + ALPHABET.index(char)
        data += n.to_bytes(SIZES.index(len(part)), 'big')
    return data


def varint(n):
    data = []
    while n >= 128:
        data.append((n & 127) | 128)
        n >>= 7
    return bytes(data + [n])


def generate(p2pool, target, profile, forks, flat):
    read = lambda name: (p2pool / name).read_text()
    common = read('src/common.h')
    wallet = read('src/wallet.cpp')
    reward = function(read('src/block_template.cpp'), 'static FORCEINLINE uint64_t get_base_reward(')
    adapted_reward = reward
    if flat:
        adapted_reward = change(reward,
            '\tconst uint64_t result = ~already_generated_coins >> 19;\n\treturn (result < BASE_BLOCK_REWARD) ? BASE_BLOCK_REWARD : result;',
            '\t(void)already_generated_coins;\n\treturn PROFILE_REWARD;')
    decoder = function(wallet, 'bool Wallet::decode(')
    # This upstream check only logs a warning; no FCMP library is linked here.
    warning = function(decoder, 'if (!torsion_check())')
    adapted_decoder = change(decoder, warning,
        '// Informational FCMP torsion warning omitted in this isolated probe.')
    constants = wallet.split('namespace {', 1)[1].split('} // namespace', 1)[0]
    if flat:
        constants = change(constants, '{ 18, 53, 24 }', '{ 120, 53, 24 }')
        constants = change(constants, '{ 42, 63, 36 }', '{ 123, 63, 36 }')
    original = reward + '\n' + wallet.split('namespace {', 1)[1].split('} // namespace', 1)[0] + decoder
    adapted = adapted_reward + '\n' + constants + adapted_decoder
    (target / 'adaptation.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), adapted.splitlines(True), 'pinned-slices', 'experimental-slices')))
    code = read('src/block_template.cpp').split('#include', 1)[0] + '''
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include "hardforks.h"
extern "C" {
#include "crypto-ops.h"
}
#define FORCEINLINE inline
#define NOINLINE
#define ROTL64(x,y) (((x) << (y)) | ((x) >> (64-(y))))
namespace p2pool {
constexpr size_t HASH_SIZE = 32;
enum class NetworkType { Mainnet, Testnet, Stagenet, Invalid };
struct hash { uint8_t h[32]; };
struct Wallet {
    static constexpr int ADDRESS_LENGTH = 95;
    uint64_t m_prefix = 0; hash m_keys[2]{}; uint32_t m_checksum = 0;
    NetworkType m_type = NetworkType::Invalid; bool m_subaddress = false;
    bool valid() const { return m_type != NetworkType::Invalid; }
    bool decode(const char* address);
};
struct SideChain {
    static NetworkType s_networkType;
    static uint64_t network_major_version(uint64_t height);
};
NetworkType SideChain::s_networkType = NetworkType::Mainnet;
// Same memcpy load semantics; no RandomX/CPU-dispatch dependency in this slice.
template<class T> T read_unaligned(const T* p) { T v; memcpy(&v, p, sizeof(v)); return v; }
'''
    for name, value in [('PROFILE_GENESIS', profile['genesis']), ('PROFILE_SHARE_ID', profile['share_id'])]:
        code += f'const std::string {name} = {json.dumps(value)};\n'
    code += f'constexpr uint64_t PROFILE_REWARD = {profile["reward_atomic"]}ULL;\n'
    code += f'constexpr uint64_t PROFILE_WEIGHT_FLOOR = {profile["weight_floor"]}ULL;\n'
    for signature in ['FORCEINLINE uint64_t umul128(', 'FORCEINLINE uint64_t udiv128(']:
        code += function(common, signature) + '\n'
    code += literal(read('src/pool_block.h'), r'static constexpr uint64_t BASE_BLOCK_REWARD = .*?;') + '\n'
    code += adapted_reward + '\n'
    code += function(read('src/block_template.cpp'), 'static FORCEINLINE uint64_t get_block_reward(') + '\n'
    code += function(read('src/side_chain.cpp'), 'uint64_t SideChain::network_major_version(') + '\n'
    code += 'int stock_share_reward_guard(uint64_t total_reward) {\n'
    code += function(read('src/pool_block_parser.inl'), 'if (total_reward < BASE_BLOCK_REWARD)')
    code += '\nreturn 0;\n}\n'
    keccak = read('src/keccak.cpp')
    code += 'enum KeccakParams { HASH_DATA_AREA = 136, ROUNDS = 24 };\n'
    code += literal(keccak, r'const uint64_t keccakf_rndc\[24\] = .*?};') + '\n'
    code += function(keccak, 'NOINLINE void keccakf_plain(') + '\n'
    code += 'auto keccakf = keccakf_plain;\n'
    for name in ['keccak_step', 'keccak_finish']:
        code += function(keccak, 'NOINLINE void ' + name + '(') + '\n'
    code += function(read('src/keccak.h'), 'template<size_t N>') + '\n'
    code += constants + '\n' + adapted_decoder + '\n'
    code += (HERE / 'selected_gate.inc').read_text() + '\n} // namespace p2pool\n'
    code += '''int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "floor") {
        uint64_t amount;
        while (std::cin >> amount) std::cout << (p2pool::stock_share_reward_guard(amount) == 0) << '\\n';
        return 0;
    }
    if (argc == 2 && std::string(argv[1]) == "hash") {
        std::string input;
        while (std::cin >> input) {
            std::string bytes;
            for (size_t i = 0; i < input.size(); i += 2)
                bytes += static_cast<char>(std::stoul(input.substr(i, 2), nullptr, 16));
            uint8_t digest[32];
            p2pool::keccak(reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size(), digest);
            const char* hex = "0123456789abcdef";
            for (auto b : digest) std::cout << hex[b >> 4] << hex[b & 15];
            std::cout << '\\n';
        }
        return 0;
    }
    return p2pool::main();
}
'''
    (target / 'probe.cpp').write_text(code)
    subprocess.run(['g++', '-std=c++17', '-O1', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=undefined', '-fno-sanitize-recover=all', '-include', 'cstddef',
        '-I', str(forks.parent), '-I', str(p2pool / 'external/src/cryptonote'),
        str(target / 'probe.cpp'), str(forks),
        str(target.parent / 'crypto-ops.o'), str(target.parent / 'crypto-ops-data.o'),
        '-o', str(target / 'probe')], check=True)


def execute(binary, rows):
    inputs = ''.join(' '.join(map(str, row)) + '\n' for row in rows)
    output = subprocess.check_output([str(binary)], input=inputs, text=True)
    return [line.split() for line in output.splitlines()], inputs, output


def main():
    p2pool, meow, overlays, out = map(Path, sys.argv[1:])
    pin = json.loads((HERE / 'selected-source-lock.json').read_text())
    receipt = Path('/genesis-receipt')
    if sha(receipt) != pin['historical_genesis_receipt']['sha256']:
        raise ValueError('historical genesis receipt drift')
    assert json.loads(receipt.read_text())['genesis'] == pin['historical_genesis_receipt']['genesis']
    upstream = json.loads((HERE / 'upstream.json').read_text())
    verify(p2pool, upstream['files'])
    verify(p2pool, pin['p2pool'])
    verify(meow, pin['meownero'])
    verify(overlays, pin['overlays'])
    meow_lock = json.loads((overlays / 'source-lock.json').read_text())
    verify(meow, meow_lock['sha256'])
    for root, name in [(p2pool, 'src/side_chain.cpp'), (meow, 'src/cryptonote_config.h'),
                       (overlays, 'selected-9-90.patch')]:
        try:
            verify(root, {name: '0' * 64})
        except ValueError:
            pass
        else:
            raise AssertionError('drift accepted')
    historical = out / 'stock-reward-fork'
    historical.mkdir()
    stock_probe(p2pool, historical)
    # Sequential C jobs, then sequential C++ jobs; never a full project build.
    for name in ['crypto-ops', 'crypto-ops-data']:
        subprocess.run(['gcc', '-O1', '-c', str(p2pool / f'external/src/cryptonote/{name}.c'),
                        '-o', str(out / (name + '.o'))], check=True)
    profiles = []
    for name, units, seconds in [('selected-9-90', 9, 90), ('fallback-12-120', 12, 120)]:
        target = out / name
        target.mkdir()
        for path in ['src/cryptonote_config.h', 'src/cryptonote_basic/cryptonote_basic_impl.cpp']:
            dest = target / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(meow / path, dest)
        patch = overlays / (name + '.patch')
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=target, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=target, check=True)
        config = (target / 'src/cryptonote_config.h').read_text()
        reward = int(re.search(r'#define MEOW_BLOCK_REWARD\s+\(\(uint64_t\)(\d+)\)', config)[1])
        spacing = int(re.search(r'#define DIFFICULTY_TARGET_V2\s+(\d+)', config)[1])
        floor = int(re.search(r'#define CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5\s+(\d+)', config)[1])
        assert (reward, spacing, floor) == (units * 10**12, seconds, 300000)
        assert 'CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 120;' in config
        assert 'CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 123;' in config
        profile = {'name': name, 'reward_atomic': reward, 'seconds': spacing, 'weight_floor': floor,
                   'regular_address_prefix': 120, 'genesis': pin['historical_genesis_receipt']['genesis'],
                   'genesis_provenance': 'historical mainnet RPC receipt; overlays leave genesis unchanged',
                   'fork_table_sha256': pin['meownero']['src/hardforks/hardforks.cpp'],
                   'overlay_sha256': sha(patch), 'config_sha256': sha(target / 'src/cryptonote_config.h')}
        # Probe identity only. Never use as a production P2Pool consensus ID.
        profile['share_id'] = hashlib.sha256(b'meownero/p2pool/isolated-probe/v1\0' +
            json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        (target / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
        generate(p2pool, target, profile, meow / 'src/hardforks/hardforks.cpp', True)
        subprocess.run(['git', 'apply', '-R', str(patch)], cwd=target, check=True)
        for path in ['src/cryptonote_config.h', 'src/cryptonote_basic/cryptonote_basic_impl.cpp']:
            assert (target / path).read_bytes() == (meow / path).read_bytes()
        profiles.append(profile)

    fixture = decode_fixture(ADDRESS)
    assert len(fixture) == 69 and fixture[0] == 120 and base58(fixture) == ADDRESS
    binary = out / profiles[0]['name'] / 'probe'
    def address(prefix, keys=fixture[1:-4]):
        payload = varint(prefix) + keys
        digest = subprocess.check_output([str(binary), 'hash'], input=payload.hex()+'\n', text=True).strip()
        return base58(payload + bytes.fromhex(digest)[:4])
    assert address(120) == ADDRESS  # Existing public fixture checks independent historical checksum.
    addresses = {'meow': ADDRESS, 'monero': address(18), 'testnet': address(156),
                 'stagenet': address(150), 'subaddress': address(123), 'integrated': address(121, fixture[1:-4]+bytes(8)),
                 'checksum': ADDRESS[:-1]+('1' if ADDRESS[-1] != '1' else '2'),
                 'invalid-alphabet': '0'+ADDRESS[1:], 'truncated': ADDRESS[:-1],
                 'invalid-point': address(120, bytes([255])*64)}
    side = (p2pool / 'src/side_chain.cpp').read_text()
    stock_ids = {}
    for name in ['default', 'mini', 'nano']:
        numbers = re.search(name+r'_consensus_id\[HASH_SIZE\] = \{ ([\d, ]+) \}', side)[1]
        stock_ids[name] = bytes(int(v) for v in numbers.split(',')).hex()
    assert len({p['share_id'] for p in profiles} | set(stock_ids.values())) == 5
    # Actual stock decoder checksum and curve acceptance control, plus stock reward/fork.
    stock = dict(profiles[0], name='stock-address', share_id=stock_ids['default'])
    stock_dir = out / stock['name']
    stock_dir.mkdir()
    generate(p2pool, stock_dir, stock, p2pool / 'external/src/hardforks/hardforks.cpp', False)
    stock_rows = [[stock['genesis'], stock['share_id'], a, 0, 1, 1, 300000, 0, 0]
                  for a in [addresses['monero'], ADDRESS]]
    actual, inputs, output = execute(stock_dir / 'probe', stock_rows)
    assert actual == [['ok', '35184372088831', '1'], ['address', '0', '1']], actual
    (stock_dir / 'vectors.txt').write_text(inputs)
    (stock_dir / 'results.txt').write_text(output)
    results = {'compatible': False, 'pool_started': False, 'payouts_tested': False,
               'scope': 'compiled reward/fork/decoder source slices plus experimental mainnet profile gate',
               'source_drift_refusals': ['p2pool', 'meownero', 'selected overlays'],
               'stock_address_positive_and_negative_pass': True, 'profiles': [],
               'toolchain': subprocess.check_output(['g++', '--version'], text=True),
               'resource_policy': {'memory_mib': 512, 'swap_mib': 0, 'cpus': 0.5, 'compiler_jobs': 1, 'network': 'none'}}
    for profile, other in [(profiles[0], profiles[1]), (profiles[1], profiles[0])]:
        reward = profile['reward_atomic']
        rows, expected, labels = [], [], []
        def add(label, status='ok', amount=None, **kw):
            case = dict(genesis=profile['genesis'], share_id=profile['share_id'], address=ADDRESS,
                        supply=0, height=1, version=16, median=300000, weight=0, fees=0)
            case.update(kw)
            rows.append(list(case.values()))
            expected.append([status, str((reward if amount is None else amount) if status == 'ok' else 0),
                             '1' if case['height'] == 0 else '16'])
            labels.append(label)
        for height in [1, 2, MAX // reward, MAX // reward + 1, MAX]:
            for supply in [0, reward, MAX-reward-1, MAX-reward, MAX-reward+1, MAX-1, MAX]:
                for median in [0, 300000, 2100000, 2**32-1]:
                    m = max(median, 300000)
                    for weight in [0, m, m+1, m*9//8, m*3//2, m*15//8, 2*m-1, 2*m, 2*m+1]:
                        for fees in [0, 123456789012]:
                            ok = weight <= 2*m
                            r = reward if weight <= m else reward * weight * (2*m-weight) // (m*m)
                            add('reward-penalty-fees', 'ok' if ok else 'weight', r+fees,
                                height=height, supply=supply, median=median, weight=weight, fees=fees)
        controls_start = len(rows)
        add('correct-profile')
        add('wrong-genesis', 'genesis', genesis='0'*64)
        add('missing-genesis', 'genesis', genesis='-')
        add('cross-profile-share-id', 'sharechain', share_id=other['share_id'])
        add('missing-share-id', 'sharechain', share_id='-')
        for name, identity in stock_ids.items():
            add('stock-'+name+'-share-id', 'sharechain', share_id=identity)
        for name, value in addresses.items():
            add('address-'+name, 'ok' if name == 'meow' else 'address', address=value)
        add('genesis-not-mineable', 'genesis-mining', height=0, version=1)
        for version in [0, 1, 15, 17, 255]:
            add('wrong-fork-'+str(version), 'fork', version=version)
        add('median-domain', 'median-domain', median=2**32)
        add('huge-median-domain', 'median-domain', median=MAX)
        add('fee-last-valid', amount=MAX, fees=MAX-reward)
        add('fee-overflow', 'fee-overflow', fees=MAX-reward+1)
        add('penalized-fee-last-valid', amount=MAX, weight=450000, fees=MAX-reward*3//4)
        add('zero-subsidy-fees', amount=MAX, weight=600000, fees=MAX)
        # Do not silently adopt P2Pool's 0.6 minimum or replace it with flat subsidy.
        add('below-stock-share-reward-floor', amount=reward*(600000-1)//300000**2, weight=599999)
        target = out / profile['name']
        actual, inputs, output = execute(target / 'probe', rows)
        if actual != expected:
            mismatches = [(labels[i], rows[i], a, e) for i, (a, e) in enumerate(zip(actual, expected)) if a != e]
            raise AssertionError((len(actual), len(expected), mismatches[:5]))
        (target / 'vectors.txt').write_text(inputs)
        (target / 'results.txt').write_text(output)
        controls = [{'name': labels[i], 'input': rows[i], 'output': actual[i]} for i in range(controls_start, len(rows))]
        (target / 'controls.json').write_text(json.dumps(controls, indent=2)+'\n')
        results['profiles'].append({**profile, 'cases_passed': len(rows),
            'oracle_cases': controls_start, 'controls_passed': len(controls),
            'reverse_apply_restores_source': True, 'vectors_sha256': sha(target / 'vectors.txt'),
            'results_sha256': sha(target / 'results.txt'), 'probe_cpp_sha256': sha(target / 'probe.cpp'),
            'first_saturating_block': MAX // reward + 1,
            'single_full_reward_varint_bytes': len(varint(reward)),
            'historical_single_full_reward_varint_bytes': len(varint(900000000000)),
            'stock_output_max_atomic': 2**56-1})
        stock_matrix = []
        for supply in [0, reward, MAX-reward-1, MAX-reward, MAX-reward+1, MAX]:
            observed = json.loads(subprocess.check_output([str(historical / 'probe'), str(supply), '1', '0']))
            assert observed['reward'] == max((MAX-supply) >> 19, 600000000000)
            assert observed['reward'] != reward and observed['major_version'] != 16
            stock_matrix.append({'supply': supply, 'stock': observed, 'selected_reward': reward, 'selected_version': 16})
        amounts = [0, 600000000000-1, 600000000000, reward*3//4, reward]
        floor_results = subprocess.check_output([str(target / 'probe'), 'floor'],
            input=''.join(str(v)+'\n' for v in amounts), text=True).splitlines()
        assert floor_results == ['0', '0', '1', '1', '1'], floor_results
        results['profiles'][-1]['stock_mismatch_cases'] = stock_matrix
        results['profiles'][-1]['compiled_stock_share_floor_controls'] = [
            {'amount': amount, 'accepted_by_floor_guard_only': result == '1'}
            for amount, result in zip(amounts, floor_results)]
    verify(p2pool, upstream['files'])
    verify(p2pool, pin['p2pool'])
    verify(meow, meow_lock['sha256'])
    verify(meow, pin['meownero'])
    verify(overlays, pin['overlays'])
    results['container_observed'] = {name: (Path('/sys/fs/cgroup') / name).read_text().strip()
        for name in ['memory.max', 'memory.swap.max', 'memory.peak', 'cpu.max', 'cpu.weight']}
    (out / 'summary.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
