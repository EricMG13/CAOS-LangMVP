import type { DocumentChartSection } from "../report/documentTypes.ts";

export type ChartTheme = "workspace" | "paper";
export type ChartRecipeKind = "line" | "bar" | "stacked_bar" | "scatter";
export type ChartFallbackReason = "LEGACY_RECIPE" | "INVALID_RECIPE" | "TABLE_MISMATCH";

export type ChartDatum = {
  category: string;
  value: number;
  rawValue: string;
  display: string;
  series: string;
  sourceIds: string[];
  xValue?: number;
};

export type ClosedChartOptions = {
  type: "line" | "interval" | "point";
  data: ChartDatum[];
  encode: { x: "category" | "xValue"; y: "value"; color: "series" };
  transform?: [{ type: "stackY" | "dodgeX" }];
  scale: { color: { domain: string[]; range: string[] } };
  axis: Record<string, unknown>;
  style: Record<string, unknown>;
  paddingTop: number;
  paddingRight: number;
  paddingBottom: number;
  paddingLeft: number;
  tooltip: false;
  legend: false;
  animate: false;
};

export type AdaptedChart = {
  ok: true;
  recipeId: string;
  kind: ChartRecipeKind;
  unit: string;
  data: ChartDatum[];
  series: string[];
  sourceIds: string[];
  options: ClosedChartOptions;
};

export type ChartFallback = {
  ok: false;
  reason: ChartFallbackReason;
  message: string;
};

const FAILURE_MESSAGES: Record<ChartFallbackReason, string> = {
  LEGACY_RECIPE: "This saved chart uses the legacy table format; its original values are shown below.",
  INVALID_RECIPE: "Chart recipe is malformed; the exact supplied table remains available.",
  TABLE_MISMATCH: "Chart and table values do not match; only the exact supplied table is shown.",
};

// Iris leads both contexts, matching the workbench's selection language. The
// remaining categorical hues are chart-only distinctions, never status colors.
const WORKSPACE_COLORS = ["#8b93f8", "#c4a7ff", "#76a9fa", "#cbd5e1", "#f0abfc", "#93c5fd", "#a5b4fc", "#d8b4fe"];
const PAPER_COLORS = ["#2f54c9", "#6741a5", "#315b96", "#5d5d68", "#8a3b8f", "#2d6682", "#4755a0", "#70498d"];
const RECIPE_KEYS = new Set(["schema_version", "recipe_id", "kind", "unit", "points"]);
const POINT_KEYS = new Set(["x", "y", "display", "series", "source_ids", "x_value"]);
const KINDS = new Set<ChartRecipeKind>(["line", "bar", "stacked_bar", "scatter"]);
const CANONICAL_NUMBER = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$/;
const BIDI_CONTROLS = /[\u202a-\u202e\u2066-\u2069]/u;
const CONTROL_CHARACTERS = /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/u;
const LONE_SURROGATE = /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/u;
const UNSAFE_CHART_TEXT = /<[a-z!/]|https?:\/\/|java\x73cript:/iu;

function fallback(reason: ChartFallbackReason): ChartFallback {
  return { ok: false, reason, message: FAILURE_MESSAGES[reason] };
}

function exactKeys(value: Record<string, unknown>, expected: Set<string>, optional?: string): boolean {
  const keys = Object.keys(value);
  return keys.every((key) => expected.has(key))
    && [...expected].every((key) => key === optional || Object.hasOwn(value, key));
}

function safeText(value: unknown, maxLength: number): value is string {
  if (typeof value !== "string" || value.length < 1 || value.length > maxLength || !value.trim()) return false;
  if (CONTROL_CHARACTERS.test(value) || BIDI_CONTROLS.test(value) || LONE_SURROGATE.test(value) || UNSAFE_CHART_TEXT.test(value)) return false;
  try {
    return value.normalize("NFC") === value && new TextEncoder().encode(value).length > 0;
  } catch {
    return false;
  }
}

function chartNumber(value: unknown): number | null {
  if (typeof value !== "string" || value.length > 128 || !CANONICAL_NUMBER.test(value) || value === "-0") return null;
  const converted = Number(value);
  return Number.isFinite(converted) ? converted : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isLegacyRecipe(recipe: Record<string, unknown>): boolean {
  return Object.hasOwn(recipe, "fields")
    && !Object.hasOwn(recipe, "points")
    && !Object.hasOwn(recipe, "recipe_id");
}

/**
 * Converts the server's closed point grammar into the only G2 options the host
 * permits. The accessible table is independently reconstructed and must match
 * byte-for-byte before any value is allowed into the chart runtime.
 */
export function adaptChartSection(section: DocumentChartSection, theme: ChartTheme): AdaptedChart | ChartFallback {
  const recipe = section.recipe;
  if (!isRecord(recipe)) return fallback("INVALID_RECIPE");
  if (isLegacyRecipe(recipe)) return fallback("LEGACY_RECIPE");
  if (!exactKeys(recipe, RECIPE_KEYS)) return fallback("INVALID_RECIPE");
  if (recipe.schema_version !== "caos.chart.v1" || !safeText(recipe.recipe_id, 120)
    || !safeText(recipe.unit, 120) || typeof recipe.kind !== "string" || !KINDS.has(recipe.kind as ChartRecipeKind)
    || !Array.isArray(recipe.points) || recipe.points.length < 1 || recipe.points.length > 500) {
    return fallback("INVALID_RECIPE");
  }

  const kind = recipe.kind as ChartRecipeKind;
  const isScatter = kind === "scatter";
  const data: ChartDatum[] = [];
  const expectedRows: string[][] = [];
  for (const rawPoint of recipe.points) {
    if (!isRecord(rawPoint) || !exactKeys(rawPoint, POINT_KEYS, "x_value")
      || !safeText(rawPoint.x, 240) || !safeText(rawPoint.display, 240) || !safeText(rawPoint.series, 240)
      || !Array.isArray(rawPoint.source_ids) || rawPoint.source_ids.length > 200
      || !rawPoint.source_ids.every((sourceId) => safeText(sourceId, 120))) {
      return fallback("INVALID_RECIPE");
    }
    const value = chartNumber(rawPoint.y);
    if (value === null) return fallback("INVALID_RECIPE");
    if (isScatter !== Object.hasOwn(rawPoint, "x_value")) return fallback("INVALID_RECIPE");
    const xValue = isScatter ? chartNumber(rawPoint.x_value) : undefined;
    if (isScatter && xValue === null) return fallback("INVALID_RECIPE");

    const sourceIds = [...rawPoint.source_ids] as string[];
    data.push({
      category: rawPoint.x,
      value,
      rawValue: rawPoint.y as string,
      display: rawPoint.display,
      series: rawPoint.series,
      sourceIds,
      ...(isScatter ? { xValue: xValue as number } : {}),
    });
    expectedRows.push([
      rawPoint.x,
      rawPoint.series,
      rawPoint.display,
      recipe.unit,
      sourceIds.join(", "),
      ...(isScatter ? [rawPoint.x_value as string] : []),
    ]);
  }

  const expectedColumns = ["Category / period", "Series", "Value", "Unit", "Sources", ...(kind === "scatter" ? ["X value"] : [])];
  if (JSON.stringify(section.accessible_columns) !== JSON.stringify(expectedColumns)
    || JSON.stringify(section.accessible_rows) !== JSON.stringify(expectedRows)) {
    return fallback("TABLE_MISMATCH");
  }

  const series = [...new Set(data.map(({ series }) => series))];
  const sourceIds = [...new Set(data.flatMap(({ sourceIds }) => sourceIds))];
  // G2 5.4.8 reverses negative stack inputs. Order only its copied render
  // data so both signs stack global first-seen series outward from zero,
  // matching native XLSX/PDF without changing reviewed/table/category order.
  const categories = [...new Set(data.map(({ category }) => category))];
  const renderData = kind === "stacked_bar" ? [...data].sort((a, b) => {
    const categoryOrder = categories.indexOf(a.category) - categories.indexOf(b.category);
    const aSeriesOrder = series.indexOf(a.series) * (a.value < 0 ? -1 : 1);
    const bSeriesOrder = series.indexOf(b.series) * (b.value < 0 ? -1 : 1);
    return categoryOrder || aSeriesOrder - bSeriesOrder;
  }) : data;
  const paper = theme === "paper";
  const options: ClosedChartOptions = {
    type: kind === "line" ? "line" : isScatter ? "point" : "interval",
    data: renderData,
    encode: { x: isScatter ? "xValue" : "category", y: "value", color: "series" },
    ...(kind === "stacked_bar" ? { transform: [{ type: "stackY" as const }] }
      : kind === "bar" ? { transform: [{ type: "dodgeX" as const }] } : {}),
    scale: { color: { domain: series, range: paper ? PAPER_COLORS : WORKSPACE_COLORS } },
    axis: paper
      ? { x: { title: false, labelAutoHide: true, labelAutoRotate: { optionalAngles: [0, 90] }, labelFill: "#5d5d68", labelOpacity: 1, lineStroke: "#a8a498" }, y: { title: false, labelFill: "#5d5d68", labelOpacity: 1, gridStroke: "#d9d5ca" } }
      : { x: { title: false, labelAutoHide: true, labelAutoRotate: { optionalAngles: [0, 90] }, labelFill: "#99a3b4", labelOpacity: 1, lineStroke: "#606b7e" }, y: { title: false, labelFill: "#99a3b4", labelOpacity: 1, gridStroke: "#242b38" } },
    style: isScatter ? { r: 4 } : kind === "line" ? { lineWidth: 2 } : {},
    paddingTop: 20,
    paddingRight: 32,
    paddingBottom: 80,
    paddingLeft: 56,
    tooltip: false,
    legend: false,
    animate: false,
  };
  return { ok: true, recipeId: recipe.recipe_id, kind, unit: recipe.unit, data, series, sourceIds, options };
}
