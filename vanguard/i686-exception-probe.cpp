// Native Windows acceptance must execute this cleanup/unwind probe before
// accepting the compiled x86 ABI adaptation. Cross linking is not execution.
#include "fcmp++.h"
#include <cstdio>
#include <stdexcept>

static volatile unsigned cleanups = 0;
struct Guard { ~Guard() { cleanups = cleanups + 1; } };

__attribute__((noinline)) static void unwind_through_cleanup() {
  Guard guard;
  throw std::runtime_error("owned exception probe");
}

int main() {
  volatile auto ffi = &fcmp_pp_verify;
  try {
    unwind_through_cleanup();
    return 1;
  } catch (const std::runtime_error&) {
    if (!ffi || cleanups != 1) return 2;
    std::puts("PASS_NATIVE_I686_EXCEPTION_PROBE");
    return 0;
  }
}
