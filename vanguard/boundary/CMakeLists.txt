monero_add_minimal_executable(vanguard_boundary_tests boundary_tests.cpp verify.cpp)
target_link_libraries(vanguard_boundary_tests PRIVATE
  fcmp_pp cryptonote_basic ringct cncrypto common epee
  ${Boost_FILESYSTEM_LIBRARY} ${Boost_THREAD_LIBRARY}
  ${CMAKE_THREAD_LIBS_INIT} ${EXTRA_LIBRARIES})
