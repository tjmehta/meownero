# Register only in an exported task-owned source tree as tests/vanguard-policy.
monero_add_minimal_executable(vanguard_network_policy policy.cpp)
target_link_libraries(vanguard_network_policy PRIVATE cryptonote_core)
