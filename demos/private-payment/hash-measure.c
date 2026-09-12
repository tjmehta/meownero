#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Link the preserved current15 objects; do not substitute SHA3 for Keccak. */
void cn_fast_hash(const void *, size_t, char *);
static volatile unsigned char sink;

static uint64_t now(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts)) exit(2);
  return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + ts.tv_nsec;
}

static int unhex(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  exit(2);
}

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *vectors = fopen(argv[1], "r");
  if (!vectors) return 2;
  char expected[65], hex[9000], digest[32];
  unsigned char input[16384];
  unsigned count = 0;
  int fields;
  while ((fields = fscanf(vectors, "%64s %8999s", expected, hex)) == 2) {
    size_t n = strcmp(hex, "x") ? strlen(hex) / 2 : 0;
    if (strlen(expected) != 64 || (n && strlen(hex) % 2)) return 2;
    for (size_t i = 0; i < n; ++i) input[i] = (unhex(hex[2*i]) << 4) | unhex(hex[2*i+1]);
    cn_fast_hash(input, n, digest);
    for (size_t i = 0; i < 32; ++i)
      if ((unsigned char)digest[i] != ((unhex(expected[2*i]) << 4) | unhex(expected[2*i+1]))) return 1;
    ++count;
  }
  if (fields != EOF || ferror(vectors) || count != 321) return 2;
  fclose(vectors);
  printf("{\"vectors_passed\":%u,\"samples\":[", count);
  const size_t lengths[] = {32, 16384};
  for (unsigned k = 0; k < 2; ++k) {
    size_t n = lengths[k];
    unsigned loops = n == 32 ? 100000 : 1000;
    for (size_t i = 0; i < n; ++i) input[i] = (unsigned char)(i * 131 + 17);
    for (unsigned i = 0; i < 1000; ++i) cn_fast_hash(input, n, digest);
    for (unsigned sample = 0; sample < 9; ++sample) {
      uint64_t start = now();
      for (unsigned i = 0; i < loops; ++i) {
        cn_fast_hash(input, n, digest);
        sink ^= (unsigned char)digest[0];
      }
      uint64_t elapsed = now() - start;
      printf("%s{\"bytes\":%zu,\"iterations\":%u,\"elapsed_ns\":%" PRIu64 "}",
             k || sample ? "," : "", n, loops, elapsed);
    }
  }
  puts("]}");
  return 0;
}
