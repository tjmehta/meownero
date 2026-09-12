
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
std::string hex(difficulty_type v)
  {
    static const char chars[] = "0123456789abcdef";
    std::string s;
    while (v > 0)
    {
      s.push_back(chars[(v & 0xf).convert_to<unsigned>()]);
      v >>= 4;
    }
    if (s.empty())
      s += "0";
    std::reverse(s.begin(), s.end());
    return "0x" + s;
  }
void insert_money_decimal_point(std::string &s, unsigned int decimal_point)
  {
    if (decimal_point == (unsigned int)-1)
      decimal_point = default_decimal_point;
    if(s.size() < decimal_point+1)
    {
      s.insert(0, decimal_point+1 - s.size(), '0');
    }
    if (decimal_point > 0)
      s.insert(s.size() - decimal_point, ".");
  }
std::string print_money(const boost::multiprecision::uint128_t &amount, unsigned int decimal_point)
  {
    std::stringstream ss;
    ss << amount;
    std::string s = ss.str();
    insert_money_decimal_point(s, decimal_point);
    return s;
  }
}
std::pair<boost::multiprecision::uint128_t, boost::multiprecision::uint128_t> core::get_coinbase_tx_sum(const uint64_t start_offset, const size_t count)
  {
    boost::multiprecision::uint128_t emission_amount = 0;
    boost::multiprecision::uint128_t total_fee_amount = 0;
    if (count)
    {
      const uint64_t end = start_offset + count - 1;
      m_blockchain_storage.for_blocks_range(start_offset, end,
        [this, &emission_amount, &total_fee_amount](uint64_t, const crypto::hash& hash, const block& b){
      std::vector<transaction> txs;
      std::vector<crypto::hash> missed_txs;
      uint64_t coinbase_amount = get_outs_money_amount(b.miner_tx);
      this->get_transactions(b.tx_hashes, txs, missed_txs, true);
      uint64_t tx_fee_amount = 0;
      for(const auto& tx: txs)
      {
        tx_fee_amount += get_tx_fee(tx);
      }
      
      emission_amount += coinbase_amount - tx_fee_amount;
      total_fee_amount += tx_fee_amount;
      return true;
      });
    }

    return std::pair<boost::multiprecision::uint128_t, boost::multiprecision::uint128_t>(emission_amount, total_fee_amount);
  }
void store_128(boost::multiprecision::uint128_t value, uint64_t &slow64, std::string &swide, uint64_t &stop64)
  {
    slow64 = (value & 0xffffffffffffffff).convert_to<uint64_t>();
    swide = cryptonote::hex(value);
    stop64 = ((value >> 64) & 0xffffffffffffffff).convert_to<uint64_t>();
  }

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
