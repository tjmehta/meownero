# Vanguard V1 harness (TJS-356). Copied by vanguard/build.sh into the pinned scratch
# clone as tests/vanguard and added after tests/unit_tests, so upstream targets
# (fcmp_pp, carrot_core, carrot_impl, unit_tests_utils, gtest) are reused unchanged.
# curve_trees.cpp is compiled from the pinned upstream tree for its test-tree helpers.

monero_add_minimal_executable(vanguard_tests
  vanguard_tests.cpp
  "${CMAKE_SOURCE_DIR}/tests/unit_tests/curve_trees.cpp")

target_include_directories(vanguard_tests
  PRIVATE
    "${CMAKE_SOURCE_DIR}/tests/unit_tests")

target_link_libraries(vanguard_tests
  PRIVATE
    unit_tests_utils
    carrot_impl
    carrot_core
    fcmp_pp
    cryptonote_basic
    ringct
    cncrypto
    common
    epee
    ${Boost_FILESYSTEM_LIBRARY}
    ${Boost_THREAD_LIBRARY}
    gtest
    ${CMAKE_THREAD_LIBS_INIT}
    ${EXTRA_LIBRARIES})

set_property(TARGET vanguard_tests
  APPEND_STRING
  PROPERTY
    COMPILE_FLAGS " -Wno-undef -Wno-sign-compare")
