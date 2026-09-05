// WCAG 2.1 contrast for every text-on-surface pair globals.css composes.
// color-mix(in srgb, A p%, B) = per-channel linear interpolation in sRGB (CSS Color 5
// §2.4 with premultiplied alpha); "transparent" is rgba(0,0,0,0), so mixing A p% with
// transparent yields A at alpha p, composited over the surface beneath.
const T = {
  bg: "#0a0c10", panel: "#101319", elevated: "#181d28", subtle: "#202632", border: "#242b38", borderStrong: "#606b7e",
  text: "#e9edf4", muted: "#99a3b4", accent: "#8b93f8", accentStrong: "#a5abfa", warning: "#fbbf24", critical: "#f87171", success: "#34d399",
  paper: "#f7f4ec", ink: "#191922", paperMeta: "#5d5d68", paperRule: "#a8a498", paperRuleStrong: "#6f6c62", paperLink: "#2f54c9", paperSoft: "#6a6a72",
  paperSuccess: "#166534", paperWarning: "#a24310", paperWatermark: "#be5410", paperCritical: "#b91c1c",
};
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const toHex = (rgb) => "#" + rgb.map((c) => Math.round(c).toString(16).padStart(2, "0")).join("");
// color-mix(in srgb, a p%, b) — both opaque
const mix = (a, p, b) => hex(a).map((ca, i) => ca * p + hex(b)[i] * (1 - p));
// color-mix(in srgb, a p%, transparent) over surface s  → a·p + s·(1-p)
const over = (a, p, s) => mix(a, p, s);
const lum = (rgb) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; const [r, g, b] = rgb.map(f); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (fg, bg) => { const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x); return (a + 0.05) / (b + 0.05); };
// opacity .55 on a button: text and background both composite over the parent surface
const fade = (c, alpha, s) => hex(c).map((cc, i) => cc * alpha + hex(s)[i] * (1 - alpha));

const pairs = [
  // [label, fg rgb, bg rgb, size class, css lines]
  ["body text on bg", hex(T.text), hex(T.bg), "14px normal", "globals.css:53"],
  ["body text on panel", hex(T.text), hex(T.panel), "14px normal", ":53/:120"],
  ["body text on elevated", hex(T.text), hex(T.elevated), "14px normal", ":80/:137"],
  ["body text on subtle (button hover)", hex(T.text), hex(T.subtle), "14px normal", ":138"],
  ["muted on bg", hex(T.muted), hex(T.bg), "10–11px labels", ":75/:108"],
  ["muted on panel", hex(T.muted), hex(T.panel), "10px panel-meta", ":126"],
  ["muted on elevated", hex(T.muted), hex(T.elevated), "10px worksheet heads", ":432/:451"],
  ["muted on rail (panel 82% bg)", hex(T.muted), mix(T.panel, 0.82, T.bg), "14px nav-link, 10px nav-label", ":68/:79"],
  ["accent on bg", hex(T.accent), hex(T.bg), "10px dag-node-open, 12px+", ":275"],
  ["accent on panel", hex(T.accent), hex(T.panel), "22px proof-register strong", ":379"],
  ["accent on elevated (nav active shortcut / history strong)", hex(T.accent), hex(T.elevated), "10px shortcut", ":86/:487"],
  ["accent-strong on elevated (active nav)", hex(T.accentStrong), hex(T.elevated), "14px nav-link", ":81/:82"],
  ["accent-strong on bg (lineage-code)", hex(T.accentStrong), hex(T.bg), "14px mono", ":454"],
  ["accent-strong on chip (accent 7% over panel)", hex(T.accentStrong), over(T.accent, 0.07, T.panel), "10px mono chip", ":190"],
  ["accent-strong on chip (accent 7% over bg)", hex(T.accentStrong), over(T.accent, 0.07, T.bg), "10px mono chip", ":190"],
  ["text on linked chip (accent 16% over panel)", hex(T.text), mix(T.accent, 0.16, T.panel), "10px mono", ":192"],
  ["bg on accent (primary button)", hex(T.bg), hex(T.accent), "14px bold", ":142"],
  ["bg on accent-strong (primary hover)", hex(T.bg), hex(T.accentStrong), "14px bold", ":143"],
  ["primary button disabled .55 (bg text over accent, both over panel)", fade(T.bg, 0.55, T.panel), fade(T.accent, 0.55, T.panel), "14px bold", ":140/:142"],
  ["secondary button disabled .55 (text over elevated, both over panel)", fade(T.text, 0.55, T.panel), fade(T.elevated, 0.55, T.panel), "14px", ":140/:137"],
  ["warning on bg", hex(T.warning), hex(T.bg), "10px flag / 14px status", ":337/:175"],
  ["warning on panel", hex(T.warning), hex(T.panel), "14px status", ":175"],
  ["warning on elevated", hex(T.warning), hex(T.elevated), "14px status", ":175"],
  ["critical on bg", hex(T.critical), hex(T.bg), "14px error", ":261"],
  ["critical on panel", hex(T.critical), hex(T.panel), "14px error", ":261"],
  ["critical on elevated", hex(T.critical), hex(T.elevated), "14px", ":175"],
  ["critical on global-error (critical 8% over bg)", hex(T.critical), mix(T.critical, 0.08, T.bg), "14px", ":115"],
  ["success on bg", hex(T.success), hex(T.bg), "14px status", ":175"],
  ["success on panel", hex(T.success), hex(T.panel), "14px status", ":175"],
  ["success on receipt (success 8% over bg)", hex(T.success), mix(T.success, 0.08, T.bg), "12px mono bold", ":116/:117"],
  ["text on callout (accent 6% over elevated)", hex(T.text), mix(T.accent, 0.06, T.elevated), "14px", ":177"],
  ["muted on callout (accent 6% over elevated)", hex(T.muted), mix(T.accent, 0.06, T.elevated), "14px", ":177/:332"],
  ["text on callout.warning (warning 6% over elevated)", hex(T.text), mix(T.warning, 0.06, T.elevated), "14px", ":178"],
  ["muted on report-recovery (warning 7% over bg)", hex(T.muted), mix(T.warning, 0.07, T.bg), "14px", ":491/:493"],
  ["text on worksheet cell (panel)", hex(T.text), hex(T.panel), "10px mono", ":436"],
  ["text on worksheet-fill-section (accent 28% over panel)", hex(T.text), mix(T.accent, 0.28, T.panel), "10px mono", ":444"],
  ["text on worksheet-fill-header (accent 20% over panel)", hex(T.text), mix(T.accent, 0.20, T.panel), "10px mono", ":445"],
  ["text on worksheet-fill-subheader (accent 10% over elevated)", hex(T.text), mix(T.accent, 0.10, T.elevated), "10px mono", ":446"],
  ["text on worksheet-fill-input (warning 15% over panel)", hex(T.text), mix(T.warning, 0.15, T.panel), "10px mono", ":448"],
  ["text on worksheet-fill-positive (success 13% over panel)", hex(T.text), mix(T.success, 0.13, T.panel), "10px mono", ":449"],
  ["text on worksheet-fill-negative (critical 13% over panel)", hex(T.text), mix(T.critical, 0.13, T.panel), "10px mono", ":450"],
  ["muted on worksheet-fill-muted (elevated)", hex(T.muted), hex(T.elevated), "10px mono", ":451"],
  ["loan positive (success) on panel", hex(T.success), hex(T.panel), "10px mono", ":324"],
  ["loan negative (critical) on panel", hex(T.critical), hex(T.panel), "10px mono", ":325"],
  ["muted on evidence-match (accent 9% over panel)", hex(T.muted), over(T.accent, 0.09, T.panel), "14px", ":277"],
  ["text on dropzone focus (accent 6% over bg)", hex(T.text), mix(T.accent, 0.06, T.bg), "12px", ":345"],
  ["border-strong on bg (input border, non-text)", hex(T.borderStrong), hex(T.bg), "UI border (3:1 target)", ":150"],
  ["border on panel (hairline, non-text)", hex(T.border), hex(T.panel), "UI border (3:1 target)", ":120"],
  ["accent focus ring on bg", hex(T.accent), hex(T.bg), "focus outline (3:1 target)", ":66"],
  ["accent focus ring on panel", hex(T.accent), hex(T.panel), "focus outline (3:1 target)", ":66"],
  // paper
  ["ink on paper", hex(T.ink), hex(T.paper), "12px rd-body", ":211/:543"],
  ["paper-meta on paper", hex(T.paperMeta), hex(T.paper), "8–10px mono meta", ":520/:535/:546"],
  ["paper-link on paper", hex(T.paperLink), hex(T.paper), "14px button", ":213"],
  ["paper on paper-link (paper primary button)", hex(T.paper), hex(T.paperLink), "14px bold", ":216"],
  ["paper on ink (rd-mark)", hex(T.paper), hex(T.ink), "10px mono bold", ":534"],
  ["paper-soft on paper (token, unused by a rule)", hex(T.paperSoft), hex(T.paper), "n/a", ":27"],
  ["paper-success on paper", hex(T.paperSuccess), hex(T.paper), "14px status", ":218"],
  ["paper-warning on paper", hex(T.paperWarning), hex(T.paper), "14px status", ":220"],
  ["paper-critical on paper", hex(T.paperCritical), hex(T.paper), "14px error", ":217"],
  ["paper-watermark 16% over paper (decorative)", over(T.paperWatermark, 0.16, T.paper), hex(T.paper), "26px mono, aria-hidden", ":522"],
  ["paper-rule on paper (border, non-text)", hex(T.paperRule), hex(T.paper), "UI border (3:1 target)", ":211/:469"],
  ["paper-rule-strong on paper (paper .button border)", hex(T.paperRuleStrong), hex(T.paper), "UI border (3:1 target)", ":213"],
  ["ink 8% over paper (rd-table row rule, non-text)", over(T.ink, 0.08, T.paper), hex(T.paper), "UI border", ":547"],
];
const rows = pairs.map(([label, fg, bg, size, where]) => {
  const r = ratio(fg, bg);
  const small = r >= 4.5 ? "AA" : r >= 3 ? "AA-large only" : "FAIL";
  return `| ${label} | ${toHex(fg)} | ${toHex(bg)} | ${r.toFixed(2)}:1 | ${small} | ${size} | ${where} |`;
});
console.log("| Pair | Foreground | Surface | Ratio | 4.5:1 | Where used | globals.css |");
console.log("|---|---|---|---|---|---|---|");
console.log(rows.join("\n"));
