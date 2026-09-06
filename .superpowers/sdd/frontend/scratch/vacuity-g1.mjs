// FE-G1 mutation harness: applies each FE-A0 §4 mutation to the real tree, runs the
// unit suite, and — for the mutations only a browser can catch — rebuilds the export
// and runs the Chromium smoke against CAOS_URL. Every file is restored from git
// afterwards. Run sequentially; never beside another smoke on the same server.
//   CAOS_URL=http://127.0.0.1:8769 node .superpowers/sdd/frontend/scratch/vacuity-g1.mjs [M1 M3 ...]
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "../../../../caos/frontend");
const git = (...args) => execFileSync("/usr/bin/git", args, { cwd: root, encoding: "utf8" });
const mutations = [
  { id: "M1", file: "src/components/model/ModelBuilder.tsx", smoke: true, behaviour: "worksheet arrow-key navigation is disconnected",
    find: "onKeyDown={(event) => onCellKeyDown(event, row, column, cell)}", replace: "" },
  { id: "M3", file: "src/components/model/ModelBuilder.tsx", smoke: true, behaviour: "READER can edit every per-period forecast assumption",
    find: 'disabled={!canWrite || row.status !== "READY"}', replace: 'disabled={row.status !== "READY"}' },
  { id: "M4", file: "src/components/Workspace.tsx", smoke: true, behaviour: "beforeunload never protects a dirty draft (listener kept, body inert)",
    find: "const guardUnload = (event: BeforeUnloadEvent) => {\n      protectDirtyDraftUnload(", replace: "const guardUnload = (event: BeforeUnloadEvent) => {\n      if (event) return;\n      protectDirtyDraftUnload(" },
  { id: "M5", file: "src/components/Workspace.tsx", smoke: true, behaviour: "identity fails OPEN: every write control renders until /api/me answers",
    find: 'const [role, setRole] = useState("READER");', replace: 'const [role, setRole] = useState("ANALYST");' },
  { id: "M6", file: "src/components/report/ReportStudio.tsx", smoke: true, behaviour: "the browser recovery copy is never written",
    find: "function storeBrowserRecovery(copy: ReportRecovery) {\n  try {", replace: "function storeBrowserRecovery(copy: ReportRecovery) {\n  if (Date.now() > 0) return true;\n  try {" },
  { id: "M7", file: "src/components/Workspace.tsx", smoke: true, behaviour: "case authority is never refreshed (effect keeps its deps, body returns early)",
    find: "if (!caseId || !caseIsAuthorized) return;\n    const controller = new AbortController();\n    void refreshCase(", replace: "if (!caseId || !caseIsAuthorized || caseId) return;\n    const controller = new AbortController();\n    void refreshCase(" },
  { id: "M8", file: "app/globals.css", smoke: false, behaviour: "success status glyph removed: status is colour alone",
    find: ".status.success::before { width: 7px; height: 7px; border-radius: 50%; background: var(--caos-success); }", replace: ".status.success::before { content: none; }" },
  { id: "M9", file: "src/components/Workspace.tsx", smoke: false, behaviour: "artifact markdown paragraphs rendered as raw HTML in the reader",
    find: "<p key={`block:${index}`}>{block.text}</p>", replace: "<p key={`block:${index}`} dangerouslySetInnerHTML={{ __html: block.text }} />" },
  { id: "M10", file: "src/components/WorkbenchShell.tsx", smoke: true, behaviour: "evidence drawer never restores focus to its trigger on close",
    find: "const closeDrawer = () => {\n    onDrawerChange(null);\n    const trigger = drawerTriggerRef.current;\n    window.requestAnimationFrame(() => trigger?.focus());", replace: "const closeDrawer = () => {\n    onDrawerChange(null);" },
  { id: "M11", file: "src/components/Workspace.tsx", smoke: true, behaviour: "cross-case run guard never fires (kept, condition made unsatisfiable)",
    find: "if (next.case_id !== context.caseId) {\n        setRun(null);", replace: "if (next.case_id !== context.caseId && !next.case_id) {\n        setRun(null);" },
  { id: "M12", file: "src/components/Workspace.tsx", smoke: true, behaviour: "SSE tail never subscribes to any run event",
    find: "].forEach((name) => source.addEventListener(name, refresh));", replace: "].forEach((name) => void name);" },
  { id: "M13", file: "src/components/EvidenceChip.tsx", smoke: true, behaviour: "the drawer opener is no longer passed from the click (F11 regression)",
    find: "onClick={(event) => onOpen(evidenceId, event.currentTarget)}", replace: "onClick={() => onOpen(evidenceId, document.activeElement as HTMLElement)}" },
];
const wanted = new Set(process.argv.slice(2));
const selected = wanted.size ? mutations.filter((item) => wanted.has(item.id)) : mutations;
const results = [];
for (const mutation of selected) {
  const target = path.join(root, mutation.file);
  const before = readFileSync(target, "utf8");
  if (!before.includes(mutation.find)) { results.push({ id: mutation.id, outcome: "needle-missing" }); continue; }
  writeFileSync(target, before.replace(mutation.find, mutation.replace));
  const unit = spawnSync("npm", ["run", "test:unit"], { cwd: root, encoding: "utf8" });
  const unitSummary = /ℹ pass (\d+)[\s\S]*?ℹ fail (\d+)/.exec(unit.stdout) || [];
  const unitFailing = [...unit.stdout.matchAll(/^✖ (.+?) \(/gm)].map((match) => match[1]);
  const record = { id: mutation.id, behaviour: mutation.behaviour, unit: { exit: unit.status, pass: Number(unitSummary[1]), fail: Number(unitSummary[2]), failing: unitFailing } };
  if (mutation.smoke && unit.status === 0) {
    // The per-subject request ceiling (300/min): let the bucket refill between smokes.
    spawnSync("sleep", ["70"]);
    const build = spawnSync("npm", ["run", "build"], { cwd: root, encoding: "utf8" });
    if (build.status !== 0) record.smoke = { exit: build.status, error: "build failed: " + ((build.stderr || "") + (build.stdout || "")).split("\n").filter(Boolean).slice(-4).join(" | ").slice(0, 400) };
    else {
      const reportPath = path.join(root, "test-results/chromium/workbench-report.json");
      rmSync(reportPath, { force: true });
      const smoke = spawnSync(process.execPath, ["scripts/workbench-smoke.mjs"], { cwd: root, encoding: "utf8", timeout: 480000, killSignal: "SIGKILL", env: { ...process.env, CAOS_BROWSER: "chromium", CAOS_TRACE: "0" } });
      const report = existsSync(reportPath) ? JSON.parse(readFileSync(reportPath, "utf8")) : { status: "no report (" + (smoke.error ? smoke.error.code : "killed") + ")", error: (smoke.stdout || "").split("\n").filter(Boolean).slice(-3).join(" | ") };
      record.smoke = { exit: smoke.status, status: report.status, error: (report.error || "").split("\n").slice(0, 3).join(" | ").slice(0, 400) };
    }
  }
  record.outcome = record.unit.exit !== 0 ? "CAUGHT by unit" : record.smoke ? (record.smoke.exit !== 0 ? "CAUGHT by smoke" : "SURVIVES") : "SURVIVES unit (smoke not run)";
  results.push(record);
  git("checkout", "--", mutation.file);
  console.log(JSON.stringify(record));
}
console.log("SUMMARY " + results.map((item) => `${item.id}:${item.outcome}`).join(" "));
