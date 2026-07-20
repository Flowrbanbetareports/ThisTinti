#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export COVERAGE_FILE="${COVERAGE_FILE:-$ROOT/.coverage}"
rm -f "$COVERAGE_FILE" "$COVERAGE_FILE".*

mapfile -t TEST_FILES < <(find tests -maxdepth 1 -type f -name 'test_*.py' | sort)
if [[ ${#TEST_FILES[@]} -eq 0 ]]; then
  echo "No tests found" >&2
  exit 2
fi

# Run each test module in a fresh interpreter. This prevents resources opened by
# one integration-heavy module from accumulating across the whole release gate.
for index in "${!TEST_FILES[@]}"; do
  test_file="${TEST_FILES[$index]}"
  echo "Coverage module $((index + 1))/${#TEST_FILES[@]}: $test_file"
  timeout 120s python scripts/coverage_pytest_module.py "$test_file"
done

python -m coverage combine
python -m coverage report --skip-covered --fail-under=90
