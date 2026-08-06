# Fails fast with a clear error if `node` isn't on PATH. Source this and
# call require_node before any script that shells out to a node helper (see
# lib/find-status.js, lib/vitest-pass-rate.js).
#
# GitHub-hosted runners (ubuntu-latest) ship Node.js preinstalled, and the
# jobs that use these scripts either rely on that or already run
# actions/setup-node — so this should never actually fire. It's a guard
# against the runner image changing under us: better a clear
# "::error::node is required" than node's own opaque "command not found"
# buried mid-script after other side effects have already happened.
require_node() {
  if ! command -v node >/dev/null 2>&1; then
    echo "::error::node is required but was not found on PATH — check the runner image / actions/setup-node step"
    exit 1
  fi
}
