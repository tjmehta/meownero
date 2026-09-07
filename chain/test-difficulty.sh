#!/usr/bin/env bash
# Run the real DAA + core callers with the shipped floor and a separately compiled 150M floor.
# Usage: bash chain/test-difficulty.sh <patched-source-with-built-tests>
set -euo pipefail
SRC=$(realpath "$1")
docker run --rm -v "$SRC:/src:ro" -w /tmp \
  "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" bash -ec '
    timeout 180 /src/build/release/tests/unit_tests/unit_tests --gtest_filter="meow_difficulty.*:difficulty.*"
    timeout 180 /src/build/release/tests/unit_tests/meow_difficulty_floor_tests --gtest_filter="meow_difficulty.*:difficulty.*"
  '
