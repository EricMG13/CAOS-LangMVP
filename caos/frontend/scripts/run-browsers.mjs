// WEB-002: the workbench journey in every supported engine, one after another,
// each writing its own test-results/<browser>/ report. Exits non-zero on the
// first engine that fails; the later engines still run so one report per
// engine exists either way.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const browsers = (process.env.CAOS_BROWSERS ?? "chromium,firefox,webkit").split(",").map((name) => name.trim()).filter(Boolean);
if (!browsers.length) throw new Error("CAOS_BROWSERS must select at least one browser");
let failed = 0;
for (const browser of browsers) {
  console.log(`\n=== workbench journey: ${browser} ===`);
  const result = spawnSync(process.execPath, [fileURLToPath(new URL("workbench-smoke.mjs", import.meta.url))], {
    stdio: "inherit",
    env: { ...process.env, CAOS_BROWSER: browser },
    timeout: 25 * 60_000,
  });
  if (result.status !== 0) failed += 1;
}
if (failed) {
  console.error(`${failed} of ${browsers.length} engines failed`);
  process.exit(1);
}
