// SPDX-License-Identifier: BSD-3-Clause
// Narrow C ABI for benchmarking the actual pinned DAA from Python.
#include <cstdint>
#include <limits>
#include <vector>
#include "cryptonote_basic/difficulty.h"

extern "C" uint64_t meow_next_difficulty(const uint64_t *timestamps,
    const uint64_t *cumulative, size_t count, size_t target)
{
  std::vector<uint64_t> ts(timestamps, timestamps + count);
  std::vector<cryptonote::difficulty_type> work(cumulative, cumulative + count);
  const auto result = cryptonote::next_difficulty(ts, work, target);
  if (result > std::numeric_limits<uint64_t>::max()) return 0;
  return result.convert_to<uint64_t>();
}
