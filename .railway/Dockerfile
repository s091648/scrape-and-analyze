# .railway/Dockerfile
#
# Lightweight Linux box for Railway IaC operations against .railway/railway.ts:
#   railway login | railway link | railway config plan | ... apply | ... pull | ... migrate
#
# Why a dedicated container (not one of the existing tool images):
#   - `railway config` evaluates .railway/railway.ts via Node type-stripping and
#     the Windows CLI build trips on it. app/job_service/test_service are Python
#     (no Node, no railway CLI); frontend is locked to `npx next dev`.
#
# Two moving parts, both needed for `railway config plan`:
#   1. The genuine Rust CLI (>= 5.42.1) — from Railway's OFFICIAL standalone
#      installer, NOT `npm i -g @railway/cli` (its postinstall binary has shipped
#      too old for the IaC engine even at @latest).
#   2. The `railway` npm SDK — .railway/railway.ts does `import "railway/iac"` and
#      the CLI requires the package present ("The Railway TypeScript SDK is not
#      installed"). Installed at /node_modules so ESM resolution from
#      /work/.railway/railway.ts walks up and finds it — no volume, and nothing
#      written into the /work bind mount.
#
# The SDK's own `assertMinimumIacCliVersion()` shells out to `$_  --version`,
# which under `make`/`sh` is not `railway` — so the `make railway-config-*`
# targets run `env _=/usr/local/bin/railway railway ...` to pin it.
#
# Usage: `docker compose run --rm -it railway_cli ...` (profile: tools) or the
# `make railway-*` targets. See .railway/README.md.  (amd64 only — an arm64 host
# has no -linux-gnu CLI release; use an amd64 Docker context.)

FROM node:24-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git make tar gzip \
    && rm -rf /var/lib/apt/lists/*

# 1. Genuine CLI -> /usr/local/bin/railway (NOT ~/.railway/bin, a mounted volume
#    at runtime; --bin-dir avoids that collision). Installer always fetches the
#    latest release — rebuild to move it: docker compose --profile tools build railway_cli
RUN curl -fsSL https://railway.com/install.sh | bash -s -- --yes --bin-dir /usr/local/bin \
    && railway --version

# 2. The IaC SDK in its own dir, with /node_modules symlinked to it — a
#    parent-dir walk from /work/.railway/railway.ts ends at /node_modules and
#    follows the link. (npm can't `--prefix /` — it errors "Tracker idealTree
#    already exists".) Verified by resolving from / , the real runtime path.
RUN mkdir -p /opt/railway-sdk && cd /opt/railway-sdk \
    && npm init -y >/dev/null 2>&1 \
    && npm install --no-audit --no-fund railway@latest \
    && ln -sfn /opt/railway-sdk/node_modules /node_modules \
    && cd / && node --input-type=module -e "import('railway/iac').then(m => console.log('railway/iac loads:', typeof m.defineRailway))"

# /work is a bind mount owned by the host user — keep git from refusing it.
RUN git config --global --add safe.directory /work

WORKDIR /work
CMD ["sleep", "infinity"]
