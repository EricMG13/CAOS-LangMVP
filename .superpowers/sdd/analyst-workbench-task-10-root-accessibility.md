# Task 10 independent controller accessibility verification

Status: **PASS** for the bounded standalone suite in Chromium, Firefox and WebKit. All root-owned browser processes finished before timing-sensitive smoke was released.

## Scope and source

- Worktree: `codex/analyst-workbench-capabilities`, Task 10 base `90403c7ce94e6384fd1f4595eff893935e5530f9`, with owner-controlled Task 10 WIP.
- Runtime: Node `v24.16.0`, npm `11.13.0`, existing Playwright browsers and `@axe-core/playwright`.
- Combined disposable app: `http://127.0.0.1:19276`, opt-in scanner/report fixtures, data `/private/tmp/caos-task10-definitive.oTpXik/harness-data-escalated`; the harness owns its worker. No extra worker or live-provider execution.
- Root owns only standalone axe execution and this record; task owner retains script fixes, other browser gates and implementation commit. Timing-sensitive smoke must wait until these processes finish.
- Original output directory: `/private/tmp/caos-task10-root-axe.MO0LkI`; durable copy: `.superpowers/sdd/evidence/task10/accessibility-all-engines/`.

## Preflight

Root read the complete existing `caos/frontend/scripts/a11y-axe.mjs` before execution. It retains route/forwarder checks, page-overflow assertions, Model/Report keyboard checks and explicit review, filed, loading, error and intake-refusal states. Its current fixtures do not substitute for the separately required loaded canonical Analysis/Report chart checks or the requested 1024px views.

The historical `frozenPayload` fixture omitted the required `evidence` array; selecting it would pass `undefined` to `reportEvidenceRefs`, which iterates the validated field. Root referred the exact fixture correction to the owner before running the sweep. Production authority/validation behavior is unchanged.

The accessibility-audit skill's verification/checklist/report guidance is used with the project's installed axe tooling. This is a bounded automated/browser qualification, not a full WCAG certification, screen-reader audit or PDF/UA claim.

## Results

Invocation from `caos/frontend`: `CAOS_URL=http://127.0.0.1:19276 CAOS_EDGE_SECRET=<disposable fixture value> CAOS_BROWSER=<engine> npm run a11y`. Commands use shell `pipefail`, preserve combined stdout/stderr through `tee`, and record shell wall timing.

- Chromium attempt 1: exit 1, 0.678s, sandbox blocked the browser's Mach-port registration before page execution. This is not a product-test failure; full output is `chromium-attempt-1.log`.
- Chromium attempt 2 with approved browser execution: **PASS**, exit 0, **115.50s**, browser `151.0.7922.34`, zero violations. Full output is `chromium-attempt-2.log`.
- Firefox attempt 1: **PASS**, exit 0, **138.15s**, browser `153.0`, zero violations. Full output is `firefox-attempt-1.log`.
- WebKit attempt 1: exit 1, **123.08s**. The Report selector-to-section keyboard assertion failed because plain Tab followed WebKit's macOS control-navigation convention. This was a concrete test failure, not an axe pass; preserved in `webkit-attempt-1.log`.
- Root's focused faithful-fixture diagnostic: plain Tab selected `<summary>Optional composition</summary>`, while resetting focus and using Option-Tab selected the exact first Credit Thesis section button. `webkit-focus-probe-1.log` and PNG retain the actual state. The existing main browser suite already uses this engine-specific chord (`workbench-smoke.mjs`). The owner reused it while preserving the same section-navigation assertion; no global OS preference, application tab index or production code was changed. This agrees with [Apple's Safari keyboard guidance](https://support.apple.com/en-afri/guide/safari/cpsh003/mac).
- WebKit attempt 2 after that test-only correction: **PASS**, exit 0, **135.04s**, browser `26.5`, zero violations. Full output is `webkit-attempt-2.log`.

Source SHA-256 at Chromium execution: `app/globals.css` = `94d2f1de24ef5fbf11f9cb673c4e439895bd1bf5c889763910e30cb059faf084`; `scripts/a11y-axe.mjs` = `d6a8397ea9ff103941a8ecbbdcef801443462e6d13cc0529ce13b1b65eec3b78`.

Count calibration: the inherited script's summary prints 125 combinations and 12 Model axe checks. Reading the complete loops gives **122 actual axe invocations**: 17 routes × 6 widths = 102, pending plan 1, Admin 2, Model 3 widths × 3 tabs = 9, Report 3, material states 5. Model and Report each also assert keyboard interaction at 3 widths; those are not extra axe invocations. Root notified the owner; do not propagate the inherited metadata overcount as observed scan coverage.

The owner corrected those two summary constants before the final WebKit run, whose log reports 122/9. Chromium/Firefox logs retain their original metadata; their executed scan/assertion branches are unchanged. The final axe script SHA-256 is `65a5bab3886af469485c4c2ce9212ba1d361bc8307caf724c0e33cd397028ffc`. Total observed scope is **366 axe scans across three engines**, plus the described keyboard checks; no violations in any successful full run. The dedicated current-module/current-v2 chart and 1024px assertions remain separately recorded in the actual-journey evidence.

The existing Node `MODULE_TYPELESS_PACKAGE_JSON` warning appears in stdout and does not change the successful Chromium exit status.
