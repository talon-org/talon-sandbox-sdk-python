#!/usr/bin/env bash
# Regenerate SDK types from OpenAPI spec.
# Requires: datamodel-code-generator
#   pip install datamodel-code-generator
set -euo pipefail

SPEC="${1:-/Users/dark/WebstormProjects/agent-sandbox-platform/api/openapi.yaml}"
OUT="src/talon_sandbox/_generated_types.py"

echo "Regenerating types from $SPEC -> $OUT"
datamodel-codegen \
  --input "$SPEC" \
  --input-file-type openapi \
  --output "$OUT" \
  --output-model-type pydantic_v2.BaseModel

echo "Done. Review $OUT before committing."
