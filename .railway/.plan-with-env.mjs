// Local helper for T6-08c plan verification: load a `KEY=value` file (as
// produced by `scripts/tfvars_to_env.py --env <env>`) into process.env, then
// exec `railway config …` with the rest of the args. `railway config` has no
// --env-file, and `source`-ing the file in a shell mangles `${{ }}` refs and
// trailing `=`. Run inside the railway_cli container. See .railway/README.md.
import fs from "fs";
import { spawnSync } from "child_process";
const [, , envFile, ...cfgArgs] = process.argv;
const env = { ...process.env, _: "/usr/local/bin/railway" };
for (const line of fs.readFileSync(envFile, "utf8").split("\n")) {
  const i = line.indexOf("=");
  if (i > 0) env[line.slice(0, i)] = line.slice(i + 1);
}
process.exit(
  spawnSync("/usr/local/bin/railway", ["config", ...cfgArgs], { stdio: "inherit", env }).status ?? 1,
);
