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

#include <cstddef>
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
static constexpr uint64_t BASE_BLOCK_REWARD = 600000000000ULL;
static FORCEINLINE uint64_t get_base_reward(uint64_t already_generated_coins)
{
	const uint64_t result = ~already_generated_coins >> 19;
	return (result < BASE_BLOCK_REWARD) ? BASE_BLOCK_REWARD : result;
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
int main(int argc, char** argv) {
    if (argc != 4) return 2;
    SideChain::s_networkType = static_cast<NetworkType>(std::strtoull(argv[3], nullptr, 10));
    std::cout << "{\"reward\":" << get_base_reward(std::strtoull(argv[1], nullptr, 10))
              << ",\"major_version\":" << SideChain::network_major_version(std::strtoull(argv[2], nullptr, 10))
              << "}\n";
}
