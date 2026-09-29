monero_add_minimal_executable(vanguard_sync_tests
  sync_tests.cpp
  ../core_tests/chaingen.cpp
  ../core_tests/fcmp_pp.cpp)
target_include_directories(vanguard_sync_tests PRIVATE ../core_tests)
target_link_libraries(vanguard_sync_tests PRIVATE
  multisig cryptonote_core p2p version epee device wallet blockchain_db fcmp_pp
  ${Boost_CHRONO_LIBRARY} ${CMAKE_THREAD_LIBS_INIT} ${EXTRA_LIBRARIES})
