// WEB-002: the workbench journey in every supported engine, one after another,
// each writing its own test-results/<browser>/ report. Exits non-zero on the
// first engine that fails; the later engines still run so one report per
// engine exists either way.
import { spawnSync } from "node:child_process";

const browsers = (process.env.CAOS_BROWSERS || "chromium,firefox,webkit").split(",").map((name) => name.trim()).filter(Boolean);
let failed = 0;
for (const browser of browsers) {
  console.log(`\n=== workbench journey: ${browser} ===`);
  const result = spawnSync(process.execPath, ["scripts/workbench-smoke.mjs"], { stdio: "inherit", env: { ...process.env, CAOS_BROWSER: browser } });
  if (result.status !== 0) failed += 1;
}
if (failed) {
  console.error(`${failed} of ${browsers.length} engines failed`);
  process.exit(1);
}
