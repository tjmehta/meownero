#!/usr/bin/env python3
"""Compile two exact pinned P2Pool routines, without building/running a pool.

The generated harness stubs only SideChain's network enum/state. Hardfork tables
are linked from upstream unchanged. Address and parser findings are source guards,
not a claim to execute the complete wallet/share parsers.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def build(source, work):
    pin = json.loads(Path(__file__).with_name('upstream.json').read_text())
    for name, expected in pin['files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected, name
    read = lambda name: (source / name).read_text()
    reward = function(read('src/block_template.cpp'),
                      'static FORCEINLINE uint64_t get_base_reward(')
    version = function(read('src/side_chain.cpp'),
                       'uint64_t SideChain::network_major_version(')
    base = re.search(r'static constexpr uint64_t BASE_BLOCK_REWARD = .*?;',
                     read('src/pool_block.h')).group()
    wallet = read('src/wallet.cpp')
    assert 'valid_prefixes[] = { 18, 53, 24 };' in wallet
    assert 'valid_prefixes_subaddress[] = { 42, 63, 36 };' in wallet
    assert 'static constexpr int ADDRESS_LENGTH = 95;' in read('src/wallet.h')
    assert 'm_prefix = data[0];' in wallet
    parser = read('src/pool_block_parser.inl')
    assert 'if (m_majorVersion != sidechain.network_major_version(m_txinGenHeight)) return __LINE__;' in parser
    assert 'if (total_reward < BASE_BLOCK_REWARD)' in parser
    assert 'EXPECT_BYTE(TXOUT_TO_TAGGED_KEY);' in parser
    assert 'if (unlock_height != m_txinGenHeight + MINER_REWARD_UNLOCK_TIME)' in parser
    unit = '''#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include "hardforks.h"
#define FORCEINLINE inline
enum class NetworkType { Mainnet, Testnet, Stagenet };
struct SideChain {
    static NetworkType s_networkType;
    static uint64_t network_major_version(uint64_t height);
};
NetworkType SideChain::s_networkType = NetworkType::Mainnet;
'''
    unit = read('src/block_template.cpp').split('#include', 1)[0] + unit
    unit += base + '\n' + reward + '\n' + version + '''
int main(int argc, char** argv) {
    if (argc != 4) return 2;
    SideChain::s_networkType = static_cast<NetworkType>(std::strtoull(argv[3], nullptr, 10));
    std::cout << "{\\\"reward\\\":" << get_base_reward(std::strtoull(argv[1], nullptr, 10))
              << ",\\\"major_version\\\":" << SideChain::network_major_version(std::strtoull(argv[2], nullptr, 10))
              << "}\\n";
}
'''
    (work / 'probe.cpp').write_text(unit)
    subprocess.run(['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror',
                    '-include', 'cstddef', '-I', str(source / 'external/src/hardforks'),
                    str(work / 'probe.cpp'), str(source / 'external/src/hardforks/hardforks.cpp'),
                    '-o', str(work / 'probe')], check=True)
    cases = []
    for supply, height, network, expected_reward, expected_version in [
        (0, 1, 0, 35184372088831, 1),
        (900000000000, 2, 0, 35184370372218, 1),
        ((1 << 64) - 1, 2689608, 0, 600000000000, 16),
        (0, 1009826, 0, 35184372088831, 1),
        (0, 1009827, 0, 35184372088831, 2),
        (0, 1983520, 1, 35184372088831, 16),
        (0, 1151720, 2, 35184372088831, 16),
    ]:
        actual = json.loads(subprocess.check_output(
            [str(work / 'probe'), str(supply), str(height), str(network)]))
        assert actual == {'reward': expected_reward, 'major_version': expected_version}, actual
        cases.append({'supply': supply, 'height': height, 'network': network, **actual})
    result = {'source_sha256_verified': len(pin['files']), 'compiled_cases': cases,
              'source_guards': ['Monero-only one-byte prefixes', '95-character addresses',
                                'historical hardfork equality', '0.6 minimum share reward',
                                'tagged coinbase outputs', '60-block coinbase unlock'],
              'compatible': False, 'scope': 'two exact compiled routines plus static source guards'}
    (work / 'source-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    build(Path(sys.argv[1]), Path(sys.argv[2]))
