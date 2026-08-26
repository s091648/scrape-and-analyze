#!/bin/bash
# 025-iac-provisioning US5 / FR-019: every Python service must read env vars
# through its own centralized config module; the frontend must read them
# through lib/env.server.ts / lib/env.client.ts. This catches a new direct
# os.environ/process.env call added outside those designated modules.
set -euo pipefail

fail=0

check_python() {
  local dir="$1"
  local allowed_pattern="$2" # extended-regex of file paths allowed to read os.environ directly
  local hits
  hits=$(grep -rlE 'os\.environ' "$dir" --include='*.py' 2>/dev/null | grep -vE "$allowed_pattern" || true)
  if [ -n "$hits" ]; then
    echo "::error::Direct os.environ access found outside the designated config module in $dir:"
    echo "$hits"
    fail=1
  fi
}

# Each service's own config.py/settings.py is the designated module; test files are
# exempt. search_service.py/bootstrap.py are a narrow, legitimate exception: they read
# os.environ.get(RAG_DENSE_API_KEY_ENV/cfg['api_key_env'], "") — a DATA-DRIVEN redirect
# whose target env-var NAME isn't statically known (it comes from config.py / the
# llm_providers DB table), so it can't be expressed as a static config.py constant.
check_python "backend" '(^backend/config\.py$|^backend/tests/|^backend/services/search_service\.py$)'
check_python "src" '(^src/config/settings\.py$|^src/tests/|^src/bootstrap\.py$)'
check_python "chatbot-plugin/src" '^chatbot-plugin/src/chatbot_plugin/config\.py$'
check_python "fastembed/src" '^fastembed/src/fastembed_service/config\.py$'
check_python "shared" '^$' # shared/ must NEVER read os.environ directly — no exceptions

hits=$(grep -rlE 'process\.env\.[A-Z0-9_]+' frontend --include='*.ts' --include='*.tsx' --include='*.mjs' --exclude-dir=node_modules --exclude-dir=.next 2>/dev/null \
  | grep -vE '(^frontend/lib/env\.(server|client)\.ts$|^frontend/next\.config\.ts$|^frontend/playwright\.config\.ts$|^frontend/scripts/|^frontend/tests/|\.test\.)' || true)
if [ -n "$hits" ]; then
  echo "::error::Direct process.env access found outside lib/env.server.ts / lib/env.client.ts:"
  echo "$hits"
  fail=1
fi

if [ "$fail" -eq 1 ]; then
  echo "::error::Env-var centralization check failed — see 025-iac-provisioning spec.md FR-015/FR-017/FR-018."
  exit 1
fi
echo "Env-var centralization check passed."
