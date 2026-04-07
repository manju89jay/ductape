#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "=== Pre-push CI check ==="

echo "--- Installing package in dev mode ---"
pip install -e ".[dev]" -q

echo "--- Running tests ---"
pytest tests/ -v

echo "--- Generating adapters ---"
ductape generate --config variants/reference_project/config.yaml --output build/

echo "--- Checking field_provenance.json ---"
test -f build/field_provenance.json

echo "--- Compiling generated C++ ---"
if command -v g++ &> /dev/null; then
  g++ -c build/converters/generated/*.cpp -Ibuild -Iruntime_reference -Ibuild/converters/generated -std=c++17
else
  echo "SKIP: g++ not found — C++ compile check will run in GitLab CI"
fi

echo "--- Verifying golden files ---"
ductape verify --config variants/reference_project/config.yaml --expected variants/reference_project/expected_output/

echo "=== All checks passed ==="
