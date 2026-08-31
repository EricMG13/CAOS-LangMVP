import assert from "node:assert/strict";
import test from "node:test";
import { parseReportRecovery, reportRecoveryKey } from "./reportRecovery.ts";

const valid = { caseId: "case/1", pathway: "FULL_CREDIT", savedAt: 1, expectedVersion: 2, templateId: "full-credit", templateVersion: "1", modelSelection: null, blocks: [{ kind: "NARRATIVE", block_id: "summary", slot_id: "summary", text: "Draft", content_mode: "ANALYST_JUDGMENT", citations: [] }] };

test("report recovery is scope-bound and rejects malformed draft blocks", () => {
  assert.equal(reportRecoveryKey("case/1", "FULL_CREDIT"), "caos:report-recovery:case%2F1:FULL_CREDIT");
  assert.deepEqual(parseReportRecovery(JSON.stringify(valid), "case/1", "FULL_CREDIT"), valid);
  assert.equal(parseReportRecovery(JSON.stringify(valid), "case/2", "FULL_CREDIT"), null);
  assert.equal(parseReportRecovery(JSON.stringify({ ...valid, blocks: [{ kind: "NARRATIVE" }] }), "case/1", "FULL_CREDIT"), null);
  assert.equal(parseReportRecovery(JSON.stringify({ ...valid, savedAt: 9e15 }), "case/1", "FULL_CREDIT"), null);
  assert.equal(parseReportRecovery(JSON.stringify({ ...valid, blocks: [{ ...valid.blocks[0], content_mode: ["EVIDENCE"] }] }), "case/1", "FULL_CREDIT"), null);
  assert.equal(parseReportRecovery(JSON.stringify({ ...valid, blocks: [{ kind: "SCENARIO_EXHIBIT", block_id: "scenario", slot_id: "scenario", title: "Stress", shocks: [1], scenario: {}, scenario_digest: "digest" }] }), "case/1", "FULL_CREDIT"), null);
  assert.equal(parseReportRecovery('{"caseId":"case/1","pathway":"FULL_CREDIT","savedAt":1e309}', "case/1", "FULL_CREDIT"), null);
  assert.equal(parseReportRecovery("not-json", "case/1", "FULL_CREDIT"), null);
});

test("report recovery rejects values outside the server draft contract", () => {
  const parse = (patch: Record<string, unknown>) => parseReportRecovery(JSON.stringify({ ...valid, ...patch }), "case/1", "FULL_CREDIT");
  assert.equal(parse({ expectedVersion: Number.MAX_SAFE_INTEGER + 1 }), null);
  assert.equal(parse({ blocks: Array.from({ length: 121 }, () => valid.blocks[0]) }), null);
  assert.equal(parse({ blocks: [{ ...valid.blocks[0], text: "x".repeat(20_001) }] }), null);
  assert.equal(parse({ blocks: [{ ...valid.blocks[0], citations: [{ source_id: "source", block_ids: [], claim: "Claim" }] }] }), null);
  assert.equal(parse({ blocks: [{ ...valid.blocks[0], citations: [{ source_id: "x".repeat(121), block_ids: ["block"], claim: "Claim" }] }] }), null);
});

test("scenario recovery is case-bound and validates exact shocks and digests", () => {
  const scenario = {
    kind: "SCENARIO_EXHIBIT", block_id: "scenario", slot_id: "scenario", title: "Stress",
    shocks: [{ assumption_id: "growth", case: "DOWNSIDE", period_id: "FY2027", value: -0.1 }],
    scenario: {
      case_id: "case/1", build_id: "build-1", base_revision_id: null, registry_version: "1",
      registry_digest: "a".repeat(64), draft_generation: 1, effective_assumptions: [{}],
      assumptions_digest: "b".repeat(64), outputs: {}, outputs_digest: "c".repeat(64), deltas: {},
    },
    scenario_digest: "d".repeat(64),
  };
  const parse = (block: Record<string, unknown>) => parseReportRecovery(JSON.stringify({ ...valid, blocks: [block] }), "case/1", "FULL_CREDIT");
  assert.ok(parse(scenario));
  assert.equal(parse({ ...scenario, shocks: [{ ...scenario.shocks[0], value: "-0.1" }] }), null);
  assert.equal(parse({ ...scenario, shocks: [{ ...scenario.shocks[0], period_id: "2027" }] }), null);
  assert.equal(parse({ ...scenario, scenario: { ...scenario.scenario, case_id: "case/2" } }), null);
  assert.equal(parse({ ...scenario, scenario_digest: "not-a-digest" }), null);
});
