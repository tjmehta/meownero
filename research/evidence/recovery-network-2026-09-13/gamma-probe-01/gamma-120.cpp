#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <type_traits>
#include <vector>
extern "C" {
#include "random.h"
}
#define CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE 10
#define THROW_WALLET_EXCEPTION_IF(c, ...) do { if(c) throw std::runtime_error("picker invariant"); } while(0)
#define MTRACE(x) do {} while(0)
namespace crypto {
// Probe is serial: preserve production random.c/Keccak and native random templates.
void generate_random_bytes_thread_safe(size_t n, uint8_t *p) { generate_random_bytes_not_thread_safe(n,p); }
  template<typename T>
  T rand() {
    static_assert(std::is_standard_layout<T>(), "cannot write random bytes into non-standard layout type");
    static_assert(std::is_trivially_copyable<T>(), "cannot write random bytes into non-trivially copyable type");
    typename std::remove_cv<T>::type res;
    generate_random_bytes_thread_safe(sizeof(T), (uint8_t*)&res);
    return res;
  }

  /* UniformRandomBitGenerator using crypto::rand<uint64_t>()
   */
  struct random_device
  {
    typedef uint64_t result_type;
    static constexpr result_type min() { return 0; }
    static constexpr result_type max() { return result_type(-1); }
    result_type operator()() const { return crypto::rand<result_type>(); }
  };

  /* Generate a random value between range_min and range_max
   */
  template<typename T>
  typename std::enable_if<std::is_integral<T>::value, T>::type rand_range(T range_min, T range_max) {
    crypto::random_device rd;
    std::uniform_int_distribution<T> dis(range_min, range_max);
    return dis(rd);
  }

  /* Generate a random index between 0 and sz-1
   */
  template<typename T>
  typename std::enable_if<std::is_unsigned<T>::value, T>::type rand_idx(T sz) {
    return crypto::rand_range<T>(0, sz-1);
  }

}

#define DIFFICULTY_TARGET_V2 120
#define GAMMA_SHAPE 19.28
#define GAMMA_SCALE (1/1.61)
#define DEFAULT_UNLOCK_TIME (CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE * DIFFICULTY_TARGET_V2)
#define RECENT_SPEND_WINDOW (15 * DIFFICULTY_TARGET_V2)
namespace tools {
  class gamma_picker
  {
  public:
    uint64_t pick();
    gamma_picker(const std::vector<uint64_t> &rct_offsets);
    gamma_picker(const std::vector<uint64_t> &rct_offsets, double shape, double scale);
    uint64_t get_num_rct_outs() const { return num_rct_outputs; }

  private:
    struct gamma_engine
    {
      typedef uint64_t result_type;
      static constexpr result_type min() { return 0; }
      static constexpr result_type max() { return std::numeric_limits<result_type>::max(); }
      result_type operator()() { return crypto::rand<result_type>(); }
    } engine;

private:
    std::gamma_distribution<double> gamma;
    const std::vector<uint64_t> &rct_offsets;
    const uint64_t *begin, *end;
    uint64_t num_rct_outputs;
    double average_output_time;
  };

gamma_picker::gamma_picker(const std::vector<uint64_t> &rct_offsets, double shape, double scale):
    rct_offsets(rct_offsets)
{
  gamma = std::gamma_distribution<double>(shape, scale);
  THROW_WALLET_EXCEPTION_IF(rct_offsets.size() <= CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE, error::wallet_internal_error, "Bad offset calculation");
  const size_t blocks_in_a_year = 86400 * 365 / DIFFICULTY_TARGET_V2;
  const size_t blocks_to_consider = std::min<size_t>(rct_offsets.size(), blocks_in_a_year);
  const size_t outputs_to_consider = rct_offsets.back() - (blocks_to_consider < rct_offsets.size() ? rct_offsets[rct_offsets.size() - blocks_to_consider - 1] : 0);
  begin = rct_offsets.data();
  end = rct_offsets.data() + rct_offsets.size() - (std::max(1, CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE) - 1);
  num_rct_outputs = *(end - 1);
  THROW_WALLET_EXCEPTION_IF(num_rct_outputs == 0, error::wallet_internal_error, "No rct outputs");
  average_output_time = DIFFICULTY_TARGET_V2 * blocks_to_consider / static_cast<double>(outputs_to_consider); // this assumes constant target over the whole rct range
};

gamma_picker::gamma_picker(const std::vector<uint64_t> &rct_offsets): gamma_picker(rct_offsets, GAMMA_SHAPE, GAMMA_SCALE) {}

uint64_t gamma_picker::pick()
{
  double x = gamma(engine);
  x = exp(x);

  if (x > DEFAULT_UNLOCK_TIME) 
  {
    // We are trying to select an output from the chain that appeared 'x' seconds before the
    // current chain tip, where 'x' is selected from the gamma distribution recommended in Miller et al.
    // (https://arxiv.org/pdf/1704.04299/).
    // Our method is to get the average time delta between outputs in the recent past, estimate the number of
    // outputs 'n' that would have appeared between 'chain_tip - x' and 'chain_tip', select the real output at
    // 'current_num_outputs - n', then randomly select an output from the block where that output appears.
    // Source code to paper: https://github.com/maltemoeser/moneropaper
    //
    // Due to the 'default spendable age' mechanic in Monero, 'current_num_outputs' only contains
    // currently *unlocked* outputs, which means the earliest output that can be selected is not at the chain tip!
    // Therefore, we must offset 'x' so it matches up with the timing of the outputs being considered. We do
    // this by saying if 'x` equals the expected age of the first unlocked output (compared to the current
    // chain tip - i.e. DEFAULT_UNLOCK_TIME), then select the first unlocked output.
    x -= DEFAULT_UNLOCK_TIME;
  }
  else 
  {
    // If the spent time suggested by the gamma is less than the unlock time, that means the gamma is suggesting an output
    // that is no longer feasible to be spent (possible since the gamma was constructed when consensus rules did not enforce the
    // lock time). The assumption made in this code is that an output expected spent quicker than the unlock time would likely
    // be spent within RECENT_SPEND_WINDOW after allowed. So it returns an output that falls between 0 and the RECENT_SPEND_WINDOW.
    // The RECENT_SPEND_WINDOW was determined with empirical analysis of observed data.
    x = crypto::rand_idx(static_cast<uint64_t>(RECENT_SPEND_WINDOW));
  }

  uint64_t output_index = x / average_output_time;
  if (output_index >= num_rct_outputs)
    return std::numeric_limits<uint64_t>::max(); // bad pick
  output_index = num_rct_outputs - 1 - output_index;

  const uint64_t *it = std::lower_bound(begin, end, output_index);
  THROW_WALLET_EXCEPTION_IF(it == end, error::wallet_internal_error, "output_index not found");
  uint64_t index = std::distance(begin, it);

  const uint64_t first_rct = index == 0 ? 0 : rct_offsets[index - 1];
  const uint64_t n_rct = rct_offsets[index] - first_rct;
  if (n_rct == 0)
    return std::numeric_limits<uint64_t>::max(); // bad pick
  MTRACE("Picking 1/" << n_rct << " in block " << index);
  return first_rct + crypto::rand_idx(n_rct);
};

}

int main(int argc, char **argv) {
  size_t blocks=std::stoull(argv[1]), samples=std::stoull(argv[2]), repeats=std::stoull(argv[3]);
  double conversion=std::stod(argv[4]);
  std::vector<uint64_t> offsets(blocks);
  for(size_t i=0;i<blocks;++i) offsets[i]=i+1;
  for(size_t trial=0;trial<repeats;++trial) {
    tools::gamma_picker picker(offsets);
    std::vector<double> ages; ages.reserve(samples);
    size_t rejected=0;
    while(ages.size()<samples) {
      uint64_t o=picker.pick();
      if(o>=blocks) { if(++rejected>samples) return 3; continue; }
      double age=(blocks-1-o)*conversion;
      if(age<0 || age>blocks*conversion) return 4;
      ages.push_back(age);
    }
    std::sort(ages.begin(),ages.end());
    std::cout << (ages[(samples-1)/2]+ages[samples/2])/2 << "\n";
  }
}
