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
