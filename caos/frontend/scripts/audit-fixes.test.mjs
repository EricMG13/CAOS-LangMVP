import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

const source = (name) => readFileSync(new URL(name, import.meta.url), "utf8");

test("browser runner rejects an empty engine selection", () => {
  for (const selection of ["", ",", "   "]) {
    const result = spawnSync(process.execPath, [fileURLToPath(new URL("run-browsers.mjs", import.meta.url))], {
      encoding: "utf8",
      env: { ...process.env, CAOS_BROWSERS: selection },
      timeout: 5_000,
    });
    assert.notEqual(result.status, 0, result.stderr);
    assert.match(result.stderr, /CAOS_BROWSERS must select at least one browser/);
  }
});

test("axe results retain incomplete checks for review", () => {
  const axe = source("a11y-axe.mjs");
  assert.match(axe, /result\.incomplete/);
  assert.match(axe, /incomplete: incomplete\.length/);
});

test("fixture browser regressions have bounded observation points", () => {
  const fault = source("fault-regressions.mjs");
  const inventory = source("production-inventory.mjs");
  assert.doesNotMatch(fault, /await waiting(?:Tornado|Save);/);
  assert.doesNotMatch(inventory, /await seen;/);
  assert.match(inventory, /finally\(\(\) => clearTimeout\(timer\)\)/);
});

test("auxiliary workbench pages retain console, page, and controlled request failures", () => {
  const workbench = source("workbench-smoke.mjs");
  assert.match(workbench, /watchPageErrors\(await actualChartContext\.newPage\(\), actualChartErrors\)/);
  assert.match(workbench, /page\.on\("requestfailed"[\s\S]+pathname === "\/api\/me"/);
  assert.match(workbench, /watchPageErrors\(await reduced\.newPage\(\)\)/);
  assert.match(workbench, /watchPageErrors\(await zoomed\.newPage\(\)\)/);
  assert.match(workbench, /watchPageErrors\(await reader\.newPage\(\)\)/);
  assert.ok(
    workbench.indexOf("actualChartPage.screenshot") < workbench.indexOf("assert.deepEqual(actualChartErrors"),
    "the actual-chart error assertion runs before the page's final interaction",
  );
});

test("every observed page uses provenance before ignoring Playwright's exact WebKit style", () => {
  const workbench = source("workbench-smoke.mjs");
  assert.match(workbench, /const watchPageErrors = async \(page, targetErrors = errors\)/);
  assert.match(workbench, /await installCspProvenance\(page\)/);
  assert.match(workbench, /browserName === "webkit"[\s\S]+item\.text\.trim\(\) === "body \{\}" && !item\.stack/);
  assert.match(workbench, /const details = window\.__caosCspViolations \|\| \[\];[\s\S]+window\.__caosCspViolations = \[\];[\s\S]+return details;/);
  assert.match(workbench, /recordPageConsoleError\(page, errors, message\)/);
  assert.match(workbench, /await settlePageErrorAttribution\(actualChartPage\)/);
});

test("unique fixture browser regressions are wired into the Chromium gate", () => {
  const scripts = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")).scripts;
  const ci = readFileSync(new URL("../../../.github/workflows/ci.yml", import.meta.url), "utf8");
  for (const name of ["test:chart-stack", "test:draft-history", "test:fault-regressions", "test:run-graph"]) {
    assert.ok(scripts[name], `${name} has no npm command`);
    assert.match(ci, new RegExp(`npm run ${name}`));
  }
});
