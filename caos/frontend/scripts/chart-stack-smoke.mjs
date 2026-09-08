import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { adaptChartSection } from "../src/components/charts/chartRecipe.ts";

// Local native-G2 proof only: no server, cases, provider or external network.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.resolve(process.env.CAOS_STACK_EVIDENCE_DIR || path.join(root, "../../qa/evidence/task9/stack-browser"));
mkdirSync(output, { recursive: true });
const cases = {
  positive: [["Q1", "A", 1], ["Q1", "B", 2], ["Q2", "B", 2], ["Q2", "A", 1]],
  negative: [["Q1", "A", -1], ["Q1", "B", -2], ["Q2", "B", -2], ["Q2", "A", -1]],
  mixed: [["Q1", "A", 1], ["Q1", "B", -2], ["Q1", "C", 0], ["Q2", "C", -3], ["Q2", "B", 2], ["Q2", "A", -1],
    ["Q3", "B", 0], ["Q3", "C", -4], ["Q3", "A", -2]],
};
const browser = await chromium.launch({ headless: true });
const report = {};
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 560 } });
  await page.route("**/*", (route) => route.abort());
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const [name, rows] of Object.entries(cases)) {
    const points = rows.map(([x, series, y]) => ({ x, series, y: String(y), display: String(y), source_ids: ["SRC-1"] }));
    const section = { kind: "chart", section_id: name, title: name, page: "Financials", editable: false,
      origin: { kind: "ARTIFACT", authority_id: "artifact-stack-proof", block_ids: ["b00001"] },
      recipe: { schema_version: "caos.chart.v1", recipe_id: name, kind: "stacked_bar", unit: "USD m", points },
      accessible_columns: ["Category / period", "Series", "Value", "Unit", "Sources"],
      accessible_rows: points.map((p) => [p.x, p.series, p.display, "USD m", "SRC-1"]) };
    const original = structuredClone(section);
    const adapted = adaptChartSection(section, "paper");
    assert.equal(adapted.ok, true);
    await page.setContent(`<body style="margin:24px;background:#f7f4ec;color:#191922;font:14px system-ui"><h1>${name} signed stacks</h1><div id="chart"></div><p>A blue · B purple · C steel blue. Source: SRC-1; values: ${JSON.stringify(rows)}</p></body>`);
    await page.addScriptTag({ path: path.join(root, "node_modules/@antv/g2/dist/g2.min.js") });
    report[name] = await page.evaluate(async (options) => {
      const chart = new window.G2.Chart({ container: "chart", width: 940, height: 380 });
      chart.options(options);
      await chart.render();
      const view = chart.getContext().views[0];
      const marks = [...view.markState.values()].flatMap((state) => state.data).map((datum) => ({
        category: datum.data.category, series: datum.data.series, value: datum.data.value,
        start: view.scale.y.invert(datum.y1), end: view.scale.y.invert(datum.y),
        y: datum.y, y1: datum.y1, points: datum.points,
      }));
      return { marks, yDomain: view.scale.y.getOptions().domain };
    }, adapted.options);
    assert.equal(report[name].marks.length, rows.length, "native marks include zero-valued rows");
    for (const category of new Set(rows.map(([x]) => x))) {
      let positive = 0, negative = 0;
      for (const series of adapted.series) {
        const mark = report[name].marks.find((d) => d.category === category && d.series === series);
        if (!mark) continue;
        const start = mark.value < 0 ? negative : positive;
        assert.ok(Math.abs(mark.start - start) < 1e-9, `${name}/${category}/${series} baseline`);
        assert.ok(Math.abs(mark.end - start - mark.value) < 1e-9, `${name}/${category}/${series} endpoint`);
        assert.equal(mark.points.length, 4);
        const coordinates = mark.points.flat();
        assert.ok(coordinates.length > 0 && coordinates.every(Number.isFinite));
        if (mark.value < 0) negative += mark.value; else positive += mark.value;
      }
    }
    await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true });
    assert.deepEqual(section, original);
  }
  assert.deepEqual(errors, []);
  writeFileSync(path.join(output, "geometry.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
