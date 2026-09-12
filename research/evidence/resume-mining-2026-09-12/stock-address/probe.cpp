/*
 * This file is part of the Monero P2Pool <https://github.com/SChernykh/p2pool>
 * Copyright (c) 2021-2026 SChernykh <https://github.com/SChernykh>
 * Portions Copyright (c) 2012-2013 The Cryptonote developers
 * Portions Copyright (c) 2014-2021 The Monero Project
 * Portions Copyright (c) 2021 XMRig <https://github.com/xmrig>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */


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
const std::string PROFILE_GENESIS = "20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8";
const std::string PROFILE_SHARE_ID = "22af7ee7b50b6892e399da6b2c6c4427b25104d4a9048e00b16e9df04407f918";
constexpr uint64_t PROFILE_REWARD = 9000000000000ULL;
constexpr uint64_t PROFILE_WEIGHT_FLOOR = 300000ULL;
FORCEINLINE uint64_t umul128(uint64_t a, uint64_t b, uint64_t* hi)
{
	const unsigned __int128 r = static_cast<unsigned __int128>(a) * static_cast<unsigned __int128>(b);
	*hi = r >> 64;
	return static_cast<uint64_t>(r);
}
FORCEINLINE uint64_t udiv128(uint64_t hi, uint64_t lo, uint64_t divisor, uint64_t* remainder)
{
	const unsigned __int128 n = (static_cast<unsigned __int128>(hi) << 64) + lo;

	const uint64_t result = n / divisor;
	*remainder = n % divisor;

	return result;
}
static constexpr uint64_t BASE_BLOCK_REWARD = 600000000000ULL;
static FORCEINLINE uint64_t get_base_reward(uint64_t already_generated_coins)
{
	const uint64_t result = ~already_generated_coins >> 19;
	return (result < BASE_BLOCK_REWARD) ? BASE_BLOCK_REWARD : result;
}
static FORCEINLINE uint64_t get_block_reward(uint64_t base_reward, uint64_t median_weight, uint64_t fees, uint64_t weight)
{
	if (weight <= median_weight) {
		return base_reward + fees;
	}

	if (weight > median_weight * 2) {
		return 0;
	}

	// This will overflow if median_weight >= 2^32
	// Maybe fix it later like in Monero code, but it'll be fiiiine for now...
	// Performance of this code is more important

	uint64_t product[2];
	product[0] = umul128(base_reward, (median_weight * 2 - weight) * weight, &product[1]);

	uint64_t rem;
	uint64_t reward = udiv128(product[1], product[0], median_weight * median_weight, &rem);

	return reward + fees;
}
uint64_t SideChain::network_major_version(uint64_t height)
{
	const hardfork_t* hard_forks;
	size_t num_hard_forks;

	switch (s_networkType)
	{
	case NetworkType::Mainnet:
	default:
		hard_forks = mainnet_hard_forks;
		num_hard_forks = num_mainnet_hard_forks;
		break;

	case NetworkType::Testnet:
		hard_forks = testnet_hard_forks;
		num_hard_forks = num_testnet_hard_forks;
		break;

	case NetworkType::Stagenet:
		hard_forks = stagenet_hard_forks;
		num_hard_forks = num_stagenet_hard_forks;
		break;
	}

	uint64_t result = 1;
	for (size_t i = 1; (i < num_hard_forks) && (height >= hard_forks[i].height); ++i) {
		result = hard_forks[i].version;
	}
	return result;
}
int stock_share_reward_guard(uint64_t total_reward) {
if (total_reward < BASE_BLOCK_REWARD) {
			return __LINE__;
		}
return 0;
}
enum KeccakParams { HASH_DATA_AREA = 136, ROUNDS = 24 };
const uint64_t keccakf_rndc[24] = 
{
	0x0000000000000001, 0x0000000000008082, 0x800000000000808a,
	0x8000000080008000, 0x000000000000808b, 0x0000000080000001,
	0x8000000080008081, 0x8000000000008009, 0x000000000000008a,
	0x0000000000000088, 0x0000000080008009, 0x000000008000000a,
	0x000000008000808b, 0x800000000000008b, 0x8000000000008089,
	0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 
	0x000000000000800a, 0x800000008000000a, 0x8000000080008081,
	0x8000000000008080, 0x0000000080000001, 0x8000000080008008
};
NOINLINE void keccakf_plain(std::array<uint64_t, 25>& st)
{
	for (int round = 0; round < KeccakParams::ROUNDS; ++round) {
		uint64_t bc[5];

		// Theta
		bc[0] = st[0] ^ st[5] ^ st[10] ^ st[15] ^ st[20];
		bc[1] = st[1] ^ st[6] ^ st[11] ^ st[16] ^ st[21];
		bc[2] = st[2] ^ st[7] ^ st[12] ^ st[17] ^ st[22];
		bc[3] = st[3] ^ st[8] ^ st[13] ^ st[18] ^ st[23];
		bc[4] = st[4] ^ st[9] ^ st[14] ^ st[19] ^ st[24];

#define THETA(i) { \
			const uint64_t t = bc[((i) + 4) % 5] ^ ROTL64(bc[((i) + 1) % 5], 1); \
			st[(i) +  0 ] ^= t; \
			st[(i) +  5] ^= t; \
			st[(i) + 10] ^= t; \
			st[(i) + 15] ^= t; \
			st[(i) + 20] ^= t; \
		}

		THETA(0);
		THETA(1);
		THETA(2);
		THETA(3);
		THETA(4);

		// Rho Pi
		const uint64_t t = st[1];
		st[ 1] = ROTL64(st[ 6], 44);
		st[ 6] = ROTL64(st[ 9], 20);
		st[ 9] = ROTL64(st[22], 61);
		st[22] = ROTL64(st[14], 39);
		st[14] = ROTL64(st[20], 18);
		st[20] = ROTL64(st[ 2], 62);
		st[ 2] = ROTL64(st[12], 43);
		st[12] = ROTL64(st[13], 25);
		st[13] = ROTL64(st[19],  8);
		st[19] = ROTL64(st[23], 56);
		st[23] = ROTL64(st[15], 41);
		st[15] = ROTL64(st[ 4], 27);
		st[ 4] = ROTL64(st[24], 14);
		st[24] = ROTL64(st[21],  2);
		st[21] = ROTL64(st[ 8], 55);
		st[ 8] = ROTL64(st[16], 45);
		st[16] = ROTL64(st[ 5], 36);
		st[ 5] = ROTL64(st[ 3], 28);
		st[ 3] = ROTL64(st[18], 21);
		st[18] = ROTL64(st[17], 15);
		st[17] = ROTL64(st[11], 10);
		st[11] = ROTL64(st[ 7],  6);
		st[ 7] = ROTL64(st[10],  3);
		st[10] = ROTL64(t, 1);

		//  Chi
#define CHI(j) { \
			const uint64_t st0 = st[(j)    ]; \
			const uint64_t st1 = st[(j) + 1]; \
			const uint64_t st2 = st[(j) + 2]; \
			const uint64_t st3 = st[(j) + 3]; \
			const uint64_t st4 = st[(j) + 4]; \
			st[(j)    ] ^= ~st1 & st2; \
			st[(j) + 1] ^= ~st2 & st3; \
			st[(j) + 2] ^= ~st3 & st4; \
			st[(j) + 3] ^= ~st4 & st0; \
			st[(j) + 4] ^= ~st0 & st1; \
		}

		CHI( 0);
		CHI( 5);
		CHI(10);
		CHI(15);
		CHI(20);

		// Iota
		st[0] ^= keccakf_rndc[round];
	}
}
auto keccakf = keccakf_plain;
NOINLINE void keccak_step(const uint8_t* &in, int &inlen, std::array<uint64_t, 25>& st)
{
	constexpr int rsiz = KeccakParams::HASH_DATA_AREA;
	constexpr int rsizw = rsiz / 8;

	for (; inlen >= rsiz; inlen -= rsiz, in += rsiz) {
		for (int i = 0; i < rsizw; i++) {
			st[i] ^= read_unaligned(reinterpret_cast<const uint64_t*>(in) + i);
		}
		keccakf(st);
	}
}
NOINLINE void keccak_finish(const uint8_t* in, int inlen, std::array<uint64_t, 25>& st)
{
	constexpr int rsiz = KeccakParams::HASH_DATA_AREA;
	constexpr int rsizw = rsiz / 8;

	keccak_step(in, inlen, st);

	// last block and padding
	alignas(8) uint8_t temp[144];

	memcpy(temp, in, inlen);
	temp[inlen++] = 1;
	memset(temp + inlen, 0, rsiz - inlen);
	temp[rsiz - 1] |= 0x80;

	for (int i = 0; i < rsizw; i++) {
		st[i] ^= reinterpret_cast<uint64_t*>(temp)[i];
	}

	keccakf(st);
}
template<size_t N>
FORCEINLINE void keccak(const uint8_t* in, int inlen, uint8_t (&md)[N])
{
	static_assert((N == 32) || (N == 200), "invalid size");

	std::array<uint64_t, 25> st = {};
	keccak_step(in, inlen, st);
	keccak_finish(in, inlen, st);
	memcpy(md, st.data(), N);
}


// Allow only regular addresses (no integrated addresses, no subaddresses)
// Values taken from cryptonote_config.h (CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX)
constexpr uint64_t valid_prefixes[] = { 18, 53, 24 };

constexpr uint64_t valid_prefixes_subaddress[] = { 42, 63, 36 };

constexpr std::array<int, 9> block_sizes{ 0, 2, 3, 5, 6, 7, 9, 10, 11 };
constexpr int num_full_blocks = p2pool::Wallet::ADDRESS_LENGTH / block_sizes.back();
constexpr int last_block_size = p2pool::Wallet::ADDRESS_LENGTH % block_sizes.back();

constexpr int block_sizes_lookup[11] = { 0, -1, 1, 2, -1, 3, 4, 5, -1, 6, 7 };

constexpr char alphabet[] = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
constexpr size_t alphabet_size = sizeof(alphabet) - 1;

static_assert(alphabet_size == 58, "Check alphabet");

struct ReverseAlphabet
{
	int8_t data[256];
	int num_symbols;

	static constexpr ReverseAlphabet init()
	{
		ReverseAlphabet result = {};

		for (int i = 0; i < 256; ++i) {
			result.data[i] = -1;
		}

		result.num_symbols = 0;
		for (size_t i = 0; i < alphabet_size; ++i) {
			if (result.data[static_cast<uint8_t>(alphabet[i])] < 0) {
				result.data[static_cast<uint8_t>(alphabet[i])] = static_cast<int8_t>(i);
				++result.num_symbols;
			}
		}

		return result;
	}
};

constexpr ReverseAlphabet rev_alphabet = ReverseAlphabet::init();

static_assert(rev_alphabet.num_symbols == 58, "Check alphabet");


bool Wallet::decode(const char* address)
{
	m_type = NetworkType::Invalid;

	if (!address || (strlen(address) != ADDRESS_LENGTH)) {
		return false;
	}

	constexpr int last_block_size_index = block_sizes_lookup[last_block_size];

	static_assert(last_block_size_index >= 0, "Check ADDRESS_LENGTH");

	uint8_t data[static_cast<size_t>(num_full_blocks) * sizeof(uint64_t) + last_block_size_index] = {};
	int data_index = 0;

	for (int i = 0; i <= num_full_blocks; ++i) {
		uint64_t num = 0;
		uint64_t order = 1;

		for (int j = ((i < num_full_blocks) ? block_sizes.back() : last_block_size) - 1; j >= 0; --j) {
			const int8_t digit = rev_alphabet.data[static_cast<uint8_t>(address[j])];
			if (digit < 0) {
				return false;
			}

			uint64_t hi;
			const uint64_t tmp = num + umul128(order, static_cast<uint64_t>(digit), &hi);
			if ((tmp < num) || hi) {
				return false;
			}

			num = tmp;
			order *= alphabet_size;
		}

		address += block_sizes.back();

		for (int j = static_cast<int>((i < num_full_blocks) ? sizeof(num) : last_block_size_index) - 1; j >= 0; --j) {
			data[data_index++] = static_cast<uint8_t>(num >> (j * 8));
		}
	}

	m_prefix = data[0];

	switch (m_prefix)
	{
	case valid_prefixes[0]: m_type = NetworkType::Mainnet;  break;
	case valid_prefixes[1]: m_type = NetworkType::Testnet;  break;
	case valid_prefixes[2]: m_type = NetworkType::Stagenet; break;

	case valid_prefixes_subaddress[0]: m_type = NetworkType::Mainnet;  m_subaddress = true; break;
	case valid_prefixes_subaddress[1]: m_type = NetworkType::Testnet;  m_subaddress = true; break;
	case valid_prefixes_subaddress[2]: m_type = NetworkType::Stagenet; m_subaddress = true; break;

	default:
		return false;
	}

	memcpy(m_keys[0].h, data + 1, HASH_SIZE);
	memcpy(m_keys[1].h, data + 1 + HASH_SIZE, HASH_SIZE);
	memcpy(&m_checksum, data + 1 + HASH_SIZE * 2, sizeof(m_checksum));

	uint8_t md[200];
	keccak(data, sizeof(data) - sizeof(m_checksum), md);

	if (memcmp(&m_checksum, md, sizeof(m_checksum)) != 0) {
		m_type = NetworkType::Invalid;
	}

	ge_p3 point;
	if ((ge_frombytes_vartime(&point, m_keys[0].h) != 0) || (ge_frombytes_vartime(&point, m_keys[1].h) != 0)) {
		m_type = NetworkType::Invalid;
	}

	// Informational FCMP torsion warning omitted in this isolated probe.

	return valid();
}
// Local source-slice experiment. This is not linked into a pool or daemon.
// PROFILE_GENESIS, PROFILE_SHARE_ID and subsidy are generated from pinned inputs.
// Only regular mainnet payout addresses are in scope. No FCMP torsion claim.
static const char* quote(const std::string& genesis, const std::string& share_id,
    const std::string& address, uint64_t supply, uint64_t height, uint64_t version,
    uint64_t median, uint64_t weight, uint64_t fees, uint64_t& reward)
{
    if (genesis != PROFILE_GENESIS) return "genesis";
    if (share_id != PROFILE_SHARE_ID) return "sharechain";
    Wallet wallet;
    if (!wallet.decode(address.c_str()) || wallet.m_type != NetworkType::Mainnet ||
        wallet.m_subaddress) return "address";
    if (height == 0) return "genesis-mining";
    if (version != SideChain::network_major_version(height)) return "fork";
    median = std::max(median, PROFILE_WEIGHT_FLOOR);
    // The unchanged pinned penalty routine multiplies median by itself in u64.
    if (median >= (uint64_t{1} << 32)) return "median-domain";
    if (weight > 2 * median) return "weight";
    const uint64_t subsidy = get_block_reward(get_base_reward(supply), median, 0, weight);
    if (fees > UINT64_MAX - subsidy) return "fee-overflow";
    reward = subsidy + fees;
    return "ok";
}

int main()
{
    std::string genesis, share_id, address;
    uint64_t supply, height, version, median, weight, fees;
    while (std::cin >> genesis >> share_id >> address >> supply >> height >> version >> median >> weight >> fees) {
        uint64_t reward = 0;
        const char* status = quote(genesis, share_id, address, supply, height, version,
            median, weight, fees, reward);
        std::cout << status << ' ' << reward << ' ' << SideChain::network_major_version(height) << '\n';
    }
    return std::cin.eof() ? 0 : 2;
}

} // namespace p2pool
int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "floor") {
        uint64_t amount;
        while (std::cin >> amount) std::cout << (p2pool::stock_share_reward_guard(amount) == 0) << '\n';
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
            std::cout << '\n';
        }
        return 0;
    }
    return p2pool::main();
}
