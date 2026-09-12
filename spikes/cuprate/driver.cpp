// SPDX-License-Identifier: BSD-3-Clause
// Unlike chain/daa-benchmark.cpp, retain all 128 bits at the adapter boundary.
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
#include "cryptonote_basic/difficulty.h"

int main() {
  size_t count;
  while (std::cin >> count) {
    assert(count <= 735);
    std::vector<uint64_t> timestamps;
    std::vector<cryptonote::difficulty_type> work;
    for (size_t i = 0; i < count; ++i) {
      uint64_t timestamp;
      std::string cumulative;
      if (!(std::cin >> timestamp >> cumulative)) return 2;
      timestamps.push_back(timestamp);
      work.emplace_back(cumulative);
      assert(i == 0 || work[i] > work[i-1]);
    }
    std::cout << cryptonote::next_difficulty(timestamps, work, 120) << '\n';
  }
  return std::cin.eof() ? 0 : 2;
}
