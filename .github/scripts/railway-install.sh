#!/usr/bin/env bash
# Installs both halves the Railway IaC engine needs to evaluate .railway/railway.ts:
#
#   1. The genuine Rust `railway` CLI, from Railway's OFFICIAL standalone
#      installer. `npm i -g @railway/cli` ships a binary too old for the IaC
#      engine even at @latest (see .railway/Dockerfile / .railway/README.md), so
#      it is installed the same way the `railway_cli` compose container does.
#   2. The `railway` npm SDK at the repo root — railway.ts does
#      `import "railway/iac"` and the CLI hard-errors without the package
#      present. The gutted SDK ("the engine ships in the CLI now") still has to be
#      importable; an ESM parent-dir walk from .railway/railway.ts finds it in the
#      repo-root node_modules.
#
# Called unconditionally by .github/workflows/railway-config.yml. On `mode: plan`
# that workflow uses railwayapp/config@v1 (which brings its own CLI copy) for the
# sticky PR-diff comment, so only the SDK is load-bearing there; `mode: apply`
# uses the standalone CLI installed here.
#
# Env:  GITHUB_PATH  - provided by Actions (PATH additions for later steps)
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
curl -fsSL https://railway.com/install.sh | bash -s -- --yes --bin-dir "$BIN_DIR"
echo "$BIN_DIR" >> "$GITHUB_PATH"
"$BIN_DIR/railway" --version

# --no-save / --no-package-lock: the repo root has no package.json; this is a
# throwaway install just to satisfy railway.ts's runtime `import "railway/iac"`.
npm install --no-save --no-package-lock railway@latest
