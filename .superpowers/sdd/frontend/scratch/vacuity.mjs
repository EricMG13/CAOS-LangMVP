// Test-vacuity harness (FE-A0). Copies caos/frontend's unit-test inputs to a
// scratch tree, applies one behaviour-removing mutation at a time that keeps the
// literal strings the source-reading tests pin, and runs the named test file.
// A PASS after a mutation means the test would not catch that behaviour going.
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import path from "node:path";

const root = path.resolve(new URL("../../../../caos/frontend", import.meta.url).pathname);
const mutations = [
  { id: "M1", file: "src/components/model/ModelBuilder.tsx", test: "src/components/model/ModelBuilder.test.ts",
    behaviour: "worksheet arrow-key navigation is disconnected (handler never wired)",
    find: 'onKeyDown={(event) => onCellKeyDown(event, row, column, cell)}', replace: "" },
  { id: "M3", file: "src/components/model/ModelBuilder.tsx", test: "src/components/model/ModelBuilder.test.ts",
    behaviour: "READER can edit every per-period forecast assumption",
    find: 'disabled={!canWrite || row.status !== "READY"}', replace: 'disabled={row.status !== "READY"}' },
  { id: "M4", file: "src/components/Workspace.tsx", test: "src/lib/workbench.test.ts",
    behaviour: "beforeunload never protects a dirty draft (listener kept, body inert)",
    find: "const guardUnload = (event: BeforeUnloadEvent) => {\n      protectDirtyDraftUnload(", replace: "const guardUnload = (event: BeforeUnloadEvent) => {\n      if (event) return;\n      protectDirtyDraftUnload(" },
  { id: "M4b", file: "src/components/Workspace.tsx", test: "src/components/model/ModelBuilder.test.ts",
    behaviour: "beforeunload never protects a dirty draft (same mutation, ModelBuilder test)",
    find: "const guardUnload = (event: BeforeUnloadEvent) => {\n      protectDirtyDraftUnload(", replace: "const guardUnload = (event: BeforeUnloadEvent) => {\n      if (event) return;\n      protectDirtyDraftUnload(" },
  { id: "M5", file: "src/components/Workspace.tsx", test: "src/components/model/ModelBuilder.test.ts",
    behaviour: "identity fails OPEN: every write control renders until /api/me answers",
    find: 'const [role, setRole] = useState("READER");', replace: 'const [role, setRole] = useState("ANALYST");' },
  { id: "M6", file: "src/components/report/ReportStudio.tsx", test: "src/components/report/ReportStudio.test.ts",
    behaviour: "the browser recovery copy is never written",
    find: "function storeBrowserRecovery(copy: ReportRecovery) {\n  try {", replace: "function storeBrowserRecovery(copy: ReportRecovery) {\n  if (copy) return true;\n  try {" },
  { id: "M7", file: "src/components/Workspace.tsx", test: "src/lib/workspaceAuthority.test.ts",
    behaviour: "case authority is never refreshed (effect keeps its deps, body returns early)",
    find: "if (!caseId || !caseIsAuthorized) return;\n    const controller = new AbortController();\n    void refreshCase(", replace: "if (!caseId || !caseIsAuthorized || caseId) return;\n    const controller = new AbortController();\n    void refreshCase(" },
  { id: "M8", file: "app/globals.css", test: "src/lib/workbench.test.ts",
    behaviour: "success, warning and critical status glyphs removed: status is colour alone",
    find: ".status.success::before { width: 7px; height: 7px; border-radius: 50%; background: var(--caos-success); }", replace: ".status.success::before { content: none; }" },
  { id: "M9", file: "src/components/Workspace.tsx", test: "ALL",
    behaviour: "artifact markdown paragraphs rendered as raw HTML (dangerouslySetInnerHTML in the reader)",
    find: '<p key={`block:${index}`}>{block.text}</p>', replace: '<p key={`block:${index}`} dangerouslySetInnerHTML={{ __html: block.text }} />' },
  { id: "M10", file: "src/components/WorkbenchShell.tsx", test: "ALL",
    behaviour: "evidence drawer never restores focus to its trigger on close",
    find: "const closeDrawer = () => {\n    onDrawerChange(null);\n    const trigger = drawerTriggerRef.current;\n    window.requestAnimationFrame(() => trigger?.focus());", replace: "const closeDrawer = () => {\n    onDrawerChange(null);" },
  { id: "M11", file: "src/components/Workspace.tsx", test: "ALL",
    behaviour: "cross-case run guard removed: a run from another case is shown and acceptable",
    find: "if (next.case_id !== context.caseId) {\n        setRun(null);", replace: "if (false) {\n        setRun(null);" },
  { id: "M12", file: "src/components/Workspace.tsx", test: "ALL",
    behaviour: "SSE tail never subscribes to any run event (progress stops after the first fetch)",
    find: '].forEach((name) => source.addEventListener(name, refresh));', replace: '].forEach((name) => void name);' },
];

const allTests = ["src/lib/workbench.test.ts", "src/lib/workspaceAuthority.test.ts", "src/components/model/ModelBuilder.test.ts", "src/components/report/ReportStudio.test.ts", "src/lib/api.test.ts", "src/lib/artifactReader.test.ts", "src/components/model/modelBuilderState.test.ts", "src/components/report/documentTypes.test.ts", "src/components/report/reportRecovery.test.ts", "src/components/report/reportStudioState.test.ts"];
const results = [];
for (const mutation of mutations) {
  const scratch = mkdtempSync(path.join(tmpdir(), "caos-vacuity-"));
  for (const entry of ["src", "app", "scripts", "package.json", "next.config.js"]) cpSync(path.join(root, entry), path.join(scratch, entry), { recursive: true });
  const target = path.join(scratch, mutation.file);
  const before = readFileSync(target, "utf8");
  if (!before.includes(mutation.find)) throw new Error(`${mutation.id}: needle not found in ${mutation.file}`);
  writeFileSync(target, before.replace(mutation.find, mutation.replace));
  const tests = mutation.test === "ALL" ? allTests : [mutation.test];
  const run = spawnSync(process.execPath, ["--test", ...tests], { cwd: scratch, encoding: "utf8" });
  const summary = /ℹ pass (\d+)[\s\S]*?ℹ fail (\d+)/.exec(run.stdout) || [];
  const failing = [...run.stdout.matchAll(/^✖ (.+?) \(/gm)].map((match) => match[1]);
  results.push({ id: mutation.id, file: mutation.file, behaviour: mutation.behaviour, tests: mutation.test, exit: run.status, pass: Number(summary[1]), fail: Number(summary[2]), failing });
  rmSync(scratch, { recursive: true, force: true });
}
for (const result of results) {
  console.log(`${result.id} ${result.exit === 0 ? "SURVIVES (vacuous)" : "CAUGHT"} — ${result.behaviour} [${result.file} → ${result.tests}] pass=${result.pass} fail=${result.fail}${result.failing.length ? ` failing: ${result.failing.join(" | ")}` : ""}`);
}
