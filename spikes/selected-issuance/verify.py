#!/usr/bin/env python3
"""Pinned, compiled reward/tally probe. No full-node or network readiness claim."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
MAX = 2**64 - 1
COIN = 10**12


def item(source, marker):
    start = source.index(marker)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def verify_source(src, lock):
    for name, expected in lock['sha256'].items():
        if hashlib.sha256((src / name).read_bytes()).hexdigest() != expected:
            raise ValueError('source mismatch: ' + name)


def main():
    src, out = map(Path, sys.argv[1:])
    lock = json.loads((HERE / 'source-lock.json').read_text())
    verify_source(src, lock)
    results = {'scope': 'compiled extracted reward and both tally expressions; not full node',
               'source_lock': lock, 'profiles': [], 'launch_ready': False,
               'toolchain': subprocess.check_output(['g++', '--version'], text=True)}
    # Verify fail-closed source provenance using a deliberately wrong digest.
    bad = {'sha256': dict(lock['sha256'])}
    bad['sha256']['src/cryptonote_config.h'] = '0' * 64
    try:
        verify_source(src, bad)
    except ValueError:
        results['source_drift_refused'] = True
    else:
        raise AssertionError('source drift accepted')
    chain = (src / 'src/cryptonote_core/blockchain.cpp').read_text()
    main_tally = 'already_generated_coins = base_reward < (MONEY_SUPPLY-already_generated_coins) ? already_generated_coins + base_reward : MONEY_SUPPLY;'
    alt_tally = 'bei.already_generated_coins = (block_reward < (MONEY_SUPPLY - prev_generated_coins)) ? prev_generated_coins + block_reward : MONEY_SUPPLY;'
    assert main_tally in chain and alt_tally in chain
    for name, units, seconds in [('selected-9-90', 9, 90), ('fallback-12-120', 12, 120)]:
        target = out / name
        target.mkdir()
        for path in ('src/cryptonote_config.h', 'src/cryptonote_basic/cryptonote_basic_impl.cpp'):
            dest = target / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / path, dest)
        patch = HERE / (name + '.patch')
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=target, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=target, check=True)
        changed = (target / 'src/cryptonote_basic/cryptonote_basic_impl.cpp').read_text()
        # These are literal functions from the hash-verified source plus the overlay.
        code = '''#include <cassert>
#include <iostream>
#include "cryptonote_config.h"
#include "int-util.h"
#define MERROR(x) do {} while (0)
'''
        code += item(changed, 'size_t get_min_block_weight(') + '\n'
        code += item(changed, 'bool get_block_reward(') + '\n'
        code += 'uint64_t tally(uint64_t already_generated_coins, uint64_t base_reward) {' + main_tally + ' return already_generated_coins; }\n'
        code += 'uint64_t alt(uint64_t prev_generated_coins, uint64_t block_reward) { struct { uint64_t already_generated_coins; } bei; ' + alt_tally + ' return bei.already_generated_coins; }\n'
        code += f'static_assert(MEOW_BLOCK_REWARD == {units} * COIN, "reward");\nstatic_assert(DIFFICULTY_TARGET_V2 == {seconds}, "spacing");\n'
        code += '''int main() {
  size_t median, weight; uint64_t supply; unsigned version;
  while (std::cin >> median >> weight >> supply >> version) {
    uint64_t reward = 0;
    bool ok = get_block_reward(median, weight, supply, reward, version);
    std::cout << ok << ' ' << reward << ' ' << tally(supply, reward) << ' ' << alt(supply, reward) << '\\n';
  }
}
'''
        (target / 'probe.cpp').write_text(code)
        subprocess.run(['g++', '-std=c++14', '-O2', '-Wall', '-Wextra',
                        '-I', str(target / 'src'), '-I', str(src / 'contrib/epee/include'),
                        str(target / 'probe.cpp'), str(src / 'contrib/epee/src/int-util.cpp'),
                        '-o', str(target / 'probe')], check=True)
        reward = units * COIN
        cases, expected = [], []
        for version in range(1, 17):
            zone = 20000 if version < 2 else 60000 if version < 5 else 300000
            for median in [0, zone, zone * 7]:
                m = max(median, zone)
                for weight in [0, m, m + 1, m * 9 // 8, m * 3 // 2, m * 15 // 8, 2*m - 1, 2*m, 2*m + 1]:
                    for supply in [0, 1, MAX - reward - 1, MAX - reward, MAX - reward + 1, MAX - 1, MAX]:
                        ok = weight <= 2*m
                        r = (reward if weight <= m else reward * weight * (2*m - weight) // (m*m)) if ok else 0
                        cases.append(f'{median} {weight} {supply} {version}\n')
                        expected.append([int(ok), r, min(MAX, supply+r), min(MAX, supply+r)])
        observed = subprocess.check_output([str(target / 'probe')], input=''.join(cases), text=True)
        actual = [[int(v) for v in line.split()] for line in observed.splitlines()]
        assert actual == expected, name + ' reward/penalty/tally mismatch'
        # Application is reversible; historical source bytes must return exactly.
        subprocess.run(['git', 'apply', '-R', str(patch)], cwd=target, check=True)
        for path in ('src/cryptonote_config.h', 'src/cryptonote_basic/cryptonote_basic_impl.cpp'):
            assert (target / path).read_bytes() == (src / path).read_bytes()
        annual = reward * (365*86400 // seconds) // COIN
        assert annual == 3153600
        results['profiles'].append({'name': name, 'reward_atomic': reward, 'seconds': seconds,
            'annual_meow_before_penalties': annual, 'cases_passed': len(cases),
            'first_saturating_block': MAX // reward + 1,
            'tally_horizon_years': (MAX // reward + 1) * seconds / (365*86400),
            'overlay_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
            'reverse_apply_restores_source': True})
    verify_source(src, lock)
    (out / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
