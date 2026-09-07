import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

import { adaptChartSection } from "./chartRecipe.ts";
import type { DocumentChartSection } from "../report/documentTypes.ts";

const origin = { kind: "ARTIFACT" as const, authority_id: "artifact-1", block_ids: ["block-1"] };
const { StackY } = createRequire(import.meta.url)("@antv/g2/lib/transform/stackY");

function section(kind: string, points: Record<string, unknown>[], unit = "USD millions"): DocumentChartSection {
  const columns = ["Category / period", "Series", "Value", "Unit", "Sources"];
  if (kind === "scatter") columns.push("X value");
  return {
    kind: "chart", section_id: `chart-${kind}`, title: `${kind} exhibit`, page: "Financial performance",
    editable: false, origin,
    recipe: { schema_version: "caos.chart.v1", recipe_id: `chart-${kind}`, kind, unit, points },
    accessible_columns: columns,
    accessible_rows: points.map((point) => [
      String(point.x), String(point.series), String(point.display), unit,
      (point.source_ids as string[]).join(", "), ...(kind === "scatter" ? [String(point.x_value)] : []),
    ]),
  };
}

const points = [
  { x: "FY2023", y: "-2.5", display: "-2.5", series: "Base", source_ids: ["SRC-1"] },
  { x: "FY2024", y: "0", display: "0", series: "Base", source_ids: ["SRC-1", "SRC-2"] },
  { x: "FY2025", y: "3.25", display: "3.25", series: "Downside", source_ids: ["SRC-2"] },
];

test("line and bar recipes preserve exact points and use closed encodings", () => {
  for (const [kind, mark] of [["line", "line"], ["bar", "interval"]] as const) {
    const result = adaptChartSection(section(kind, points), "workspace");
    assert.equal(result.ok, true);
    if (!result.ok) continue;
    assert.equal(result.options.type, mark);
    assert.deepEqual(result.options.encode, { x: "category", y: "value", color: "series" });
    assert.deepEqual(result.data.map(({ category, value, rawValue }) => ({ category, value, rawValue })), [
      { category: "FY2023", value: -2.5, rawValue: "-2.5" },
      { category: "FY2024", value: 0, rawValue: "0" },
      { category: "FY2025", value: 3.25, rawValue: "3.25" },
    ]);
    assert.equal(result.options.tooltip, false);
    assert.equal(result.options.legend, false);
    assert.equal(result.options.animate, false);
    assert.deepEqual({
      top: result.options.paddingTop,
      right: result.options.paddingRight,
      bottom: result.options.paddingBottom,
      left: result.options.paddingLeft,
    }, { top: 20, right: 32, bottom: 80, left: 56 });
    assert.deepEqual(result.options.axis.x, { title: false, labelAutoHide: true, labelAutoRotate: { optionalAngles: [0, 90] }, labelFill: "#99a3b4", labelOpacity: 1, lineStroke: "#606b7e" });
    assert.deepEqual(result.options.axis.y, { title: false, labelFill: "#99a3b4", labelOpacity: 1, gridStroke: "#242b38" });
  }
});

test("stacked bars use G2's diverging stackY and retain negative and zero values", () => {
  const result = adaptChartSection(section("stacked_bar", points), "paper");
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.options.type, "interval");
  assert.deepEqual(result.options.transform, [{ type: "stackY" }]);
  assert.deepEqual(result.data.map((point) => point.value), [-2.5, 0, 3.25]);
});

test("installed G2 stacks each sign outward in global series order without changing reviewed data", () => {
  for (const rows of [
    [["Q1", "A", 1], ["Q1", "B", 2], ["Q2", "B", 2], ["Q2", "A", 1]],
    [["Q1", "A", -1], ["Q1", "B", -2], ["Q2", "B", -2], ["Q2", "A", -1]],
    [["Q1", "A", 1], ["Q1", "B", -2], ["Q1", "C", 0], ["Q2", "C", -3], ["Q2", "B", 2], ["Q2", "A", -1],
      ["Q3", "B", 0], ["Q3", "C", -4], ["Q3", "A", -2]],
  ] as [string, string, number][][]) {
    const input = section("stacked_bar", rows.map(([x, series, y]) => ({ x, series, y: String(y), display: String(y), source_ids: ["SRC-1"] })));
    const original = structuredClone(input);
    const result = adaptChartSection(input, "paper");
    assert.equal(result.ok, true);
    if (!result.ok) continue;
    assert.deepEqual(result.data.map((d) => [d.category, d.series, d.value]), rows);
    const rendered = result.options.data;
    assert.deepEqual([...new Set(rendered.map((d) => d.category))], [...new Set(rows.map(([x]) => x))]);
    const encode = Object.fromEntries(["x", "y", "color"].map((key) => [key, { type: "column", value: rendered.map((d) =>
      key === "x" ? d.category : key === "y" ? d.value : d.series) }]));
    const [, stacked] = StackY()(rendered.map((_, i) => i), { data: rendered, encode });
    for (const category of new Set(rows.map(([x]) => x))) {
      let positive = 0, negative = 0;
      for (const name of result.series) {
        const index = rendered.findIndex((d) => d.category === category && d.series === name);
        if (index < 0) continue;
        const value = rendered[index].value;
        const start = value < 0 ? negative : positive;
        assert.equal(stacked.encode.y1.value[index], start, `${category}/${name} baseline`);
        assert.equal(stacked.encode.y.value[index], start + value, `${category}/${name} endpoint`);
        if (value < 0) negative += value; else positive += value;
      }
    }
    assert.deepEqual(input, original);
  }
});

test("ordinary bars dodge same-period series instead of drawing overlapping intervals", () => {
  const grouped = [
    { x: "FY2024", y: "-2.5", display: "-2.5", series: "Debt", source_ids: ["SRC-1"] },
    { x: "FY2024", y: "0", display: "0", series: "Cash", source_ids: ["SRC-1"] },
    { x: "FY2024", y: "3.25", display: "3.25", series: "Add-backs", source_ids: ["SRC-2"] },
  ];
  const result = adaptChartSection(section("bar", grouped), "workspace");
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.deepEqual(result.options.transform, [{ type: "dodgeX" }]);
  assert.deepEqual(result.data.map(({ category, series, value }) => ({ category, series, value })), [
    { category: "FY2024", series: "Debt", value: -2.5 },
    { category: "FY2024", series: "Cash", value: 0 },
    { category: "FY2024", series: "Add-backs", value: 3.25 },
  ]);
});

test("scatter uses only supplied numeric x coordinates", () => {
  const scatter = points.map((point, index) => ({ ...point, x_value: ["-1.5", "0", "2.25"][index] }));
  const result = adaptChartSection(section("scatter", scatter, "turns"), "workspace");
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.options.type, "point");
  assert.deepEqual(result.options.encode, { x: "xValue", y: "value", color: "series" });
  assert.deepEqual(result.data.map((point) => point.xValue), [-1.5, 0, 2.25]);
});

test("missing, noncanonical, negative-zero, overflowing, and mixed-unit values never become zero", () => {
  for (const value of [null, 1, "01", "1.0", "1e2", "-0", "9".repeat(400)]) {
    const malformed = section("line", [{ ...points[0], y: value }]);
    malformed.accessible_rows[0][2] = String(value);
    assert.deepEqual(adaptChartSection(malformed, "workspace"), {
      ok: false, reason: "INVALID_RECIPE", message: "Chart recipe is malformed; the exact supplied table remains available.",
    });
  }
  const mixed = section("line", points);
  mixed.accessible_rows[1][3] = "EUR millions";
  assert.deepEqual(adaptChartSection(mixed, "workspace"), {
    ok: false, reason: "TABLE_MISMATCH", message: "Chart and table values do not match; only the exact supplied table is shown.",
  });
});

test("unsupported kinds and provider configuration fields fail closed", () => {
  const unsupported = section("pie", points);
  assert.equal(adaptChartSection(unsupported, "workspace").ok, false);
  const configured = section("line", points);
  configured.recipe = { ...configured.recipe, data: "https://attacker.invalid/data", tooltip: { render: "<script>" } };
  assert.equal(adaptChartSection(configured, "workspace").ok, false);
  const configuredPoint = section("line", [{ ...points[0], transform: "javascript:alert(1)" }]);
  assert.equal(adaptChartSection(configuredPoint, "workspace").ok, false);
});

test("unsafe labels are rejected and never reach tooltip, legend, or executable paths", () => {
  for (const label of ["<script>alert(1)</script>", "https://attacker.invalid", "javascript:alert(1)", "bad\u202etxt", "bad\ud800", "bad\u0001txt"]) {
    const malicious = section("line", [{ ...points[0], series: label }]);
    malicious.accessible_rows[0][1] = label;
    assert.equal(adaptChartSection(malicious, "workspace").ok, false);
  }
  const punctuation = section("line", [{ ...points[0], series: "Secured < 5x & O'Brien" }]);
  punctuation.accessible_rows[0][1] = "Secured < 5x & O'Brien";
  const safe = adaptChartSection(punctuation, "workspace");
  assert.equal(safe.ok, true);
  if (safe.ok) assert.deepEqual(safe.series, ["Secured < 5x & O'Brien"]);
});

test("old field recipes remain table-only even when they claim the current schema label", () => {
  const legacy = section("line", points);
  legacy.recipe = { schema_version: "caos.chart.v1", fields: ["period", "value"], kind: "line" };
  assert.deepEqual(adaptChartSection(legacy, "paper"), {
    ok: false, reason: "LEGACY_RECIPE", message: "This saved chart uses the legacy table format; its original values are shown below.",
  });
  const ambiguous = section("line", points);
  ambiguous.recipe = { ...ambiguous.recipe, fields: ["period", "value"] };
  const result = adaptChartSection(ambiguous, "paper");
  assert.equal(result.ok, false);
  if (!result.ok) assert.notEqual(result.reason, "LEGACY_RECIPE");
});

test("point recipes must reproduce the authoritative accessible table byte for byte", () => {
  const mismatched = section("bar", points);
  mismatched.accessible_rows[0][2] = "2.5";
  assert.deepEqual(adaptChartSection(mismatched, "workspace"), {
    ok: false, reason: "TABLE_MISMATCH", message: "Chart and table values do not match; only the exact supplied table is shown.",
  });
});
