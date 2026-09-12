#!/usr/bin/env python3
"""Compile pinned supply aggregation/RPC formatting with synthetic block storage."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from verify import item, verify_source

HERE = Path(__file__).resolve().parent
MAX = 2**64 - 1
COIN = 10**12


def main():
    src, out = map(Path, sys.argv[1:])
    lock = json.loads((HERE / 'reporting-source-lock.json').read_text())
    verify_source(src, lock)
    core = (src / 'src/cryptonote_core/cryptonote_core.cpp').read_text()
    rpc = (src / 'src/rpc/core_rpc_server.cpp').read_text()
    fmt = (src / 'src/cryptonote_basic/cryptonote_format_utils.cpp').read_text()
    difficulty = (src / 'src/cryptonote_basic/difficulty.cpp').read_text()
    # The adapters supply synthetic transactions and an in-memory range iterator.
    # The aggregation method and formatting functions below remain literal source.
    code = r'''
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <boost/multiprecision/cpp_int.hpp>
using boost::multiprecision::uint128_t;
namespace crypto { using hash = uint64_t; }
struct transaction { uint64_t amount; };
struct block { transaction miner_tx; std::vector<crypto::hash> tx_hashes; };
uint64_t get_outs_money_amount(const transaction& tx) { return tx.amount; }
uint64_t get_tx_fee(const transaction& tx) { return tx.amount; }
struct storage {
  uint64_t reward, fee;
  template<typename F> void for_blocks_range(uint64_t start, uint64_t end, F f) {
    for (uint64_t height = start; height <= end; ++height) {
      block b{{height ? reward + fee : 0}, {}};
      if (height && fee) b.tx_hashes.push_back(fee);
      if (!f(height, height, b)) break;
    }
  }
};
struct core {
  storage m_blockchain_storage;
  void get_transactions(const std::vector<crypto::hash>& hashes,
      std::vector<transaction>& txs, std::vector<crypto::hash>&, bool) {
    for (auto fee : hashes) txs.push_back({fee});
  }
  std::pair<uint128_t,uint128_t> get_coinbase_tx_sum(uint64_t, size_t);
};
namespace cryptonote {
using difficulty_type = uint128_t;
unsigned int default_decimal_point = 12;
'''
    for source, marker in [
        (difficulty, 'std::string hex(difficulty_type v)'),
        (fmt, 'void insert_money_decimal_point('),
        (fmt, 'std::string print_money(const boost::multiprecision::uint128_t &amount,')
    ]:
        code += item(source, marker) + '\n'
    code += '}\n'
    code += item(core, 'std::pair<boost::multiprecision::uint128_t, boost::multiprecision::uint128_t> core::get_coinbase_tx_sum(') + '\n'
    code += item(rpc, 'void store_128(') + '\n'
    code += r'''
int main() {
  uint64_t reward, fee, start, count;
  while (std::cin >> reward >> fee >> start >> count) {
    core node{{reward, fee}};
    auto amounts = node.get_coinbase_tx_sum(start, count);
    for (auto amount : {amounts.first, amounts.second, amounts.first + amounts.second}) {
      uint64_t low, high; std::string wide;
      store_128(amount, low, wide, high);
      // Same wide-string constructor and formatter used by the daemon CLI.
      std::cout << low << ' ' << high << ' ' << wide << ' '
        << cryptonote::print_money(uint128_t(wide), (unsigned int)-1) << ' ';
    }
    std::cout << '\n';
  }
}
'''
    probe = out / 'reporting-probe.cpp'
    probe.write_text(code)
    subprocess.run(['g++', '-std=c++14', '-O2', '-Wall', '-Wextra', str(probe),
                    '-o', str(out / 'reporting-probe')], check=True)
    cases = []
    for units in (9, 12):
        reward = units * COIN
        edge = MAX // reward + 1
        for start, count in [(0, 0), (0, 1), (0, 2), (1, 1),
                             (0, edge), (0, edge + 1), (0, edge + 2),
                             (1, edge + 1), (edge - 1, 3)]:
            for fee in (0, 123456789012):
                cases.append((reward, fee, start, count))
        # Penalized/underclaimed subsidy and independent aggregate-fee overflow.
        cases.append((reward // 2, 0, 0, edge * 2 + 2))
        cases.append((reward, MAX - reward, 1, 3))
    observed = subprocess.check_output([str(out / 'reporting-probe')], text=True,
        input=''.join(' '.join(map(str, c)) + '\n' for c in cases)).splitlines()
    assert len(observed) == len(cases)
    receipts = []
    for case, line in zip(cases, observed):
        reward, fee, start, count = case
        paid = count - int(start == 0 and count > 0)
        expected = [paid * reward, paid * fee, paid * (reward + fee)]
        words = line.split()
        assert len(words) == 12
        for i, total in enumerate(expected):
            low, high, wide, display = words[i*4:i*4+4]
            assert int(low) == total & MAX
            assert int(high) == total >> 64
            assert int(wide, 16) == total
            assert display == f'{total // COIN}.{total % COIN:012d}'
        receipts.append({'reward_atomic': reward, 'fee_atomic': fee,
                         'start': start, 'count': count,
                         'emission_atomic': str(expected[0]),
                         'fee_total_atomic': str(expected[1]), 'observed': words})
    assert any(int(r['emission_atomic']) > MAX for r in receipts)
    bad = {'sha256': dict(lock['sha256'])}
    bad['sha256']['src/cryptonote_core/cryptonote_core.cpp'] = '0' * 64
    try:
        verify_source(src, bad)
    except ValueError:
        pass
    else:
        raise AssertionError('source drift accepted')
    verify_source(src, lock)
    result = {'scope': 'literal core aggregation and RPC/CLI amount formatting; synthetic storage/transactions',
              'launch_ready': False, 'source_lock': lock, 'cases_passed': len(cases),
              'source_drift_refused': True,
              'toolchain': subprocess.check_output(['g++', '--version'], text=True),
              'probe_sha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
              'cases': receipts}
    (out / 'reporting-summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(cases)} reporting cases passed; synthetic storage, not full-node integration')


if __name__ == '__main__':
    main()
