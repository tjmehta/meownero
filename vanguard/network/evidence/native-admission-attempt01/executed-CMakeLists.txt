# Add this directory only to a disposable copy of the pinned upstream tree,
# after its normal tests. No shared cache or package build file is edited.
monero_add_minimal_executable(vanguard_network_genesis genesis.cpp)
target_link_libraries(vanguard_network_genesis PRIVATE cryptonote_core)
monero_add_minimal_executable(vanguard_network_admission admission.cpp)
target_link_libraries(vanguard_network_admission PRIVATE cryptonote_core)
