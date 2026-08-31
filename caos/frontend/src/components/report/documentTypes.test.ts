import assert from "node:assert/strict";
import test from "node:test";

import {
  canEditDocumentSection,
  draftTextSections,
  groupDocumentPages,
  overlayAnalystText,
  type DocumentSection,
} from "./documentTypes.ts";

const origin = (kind: "ANALYST" | "MODEL", authorityId: string) => ({
  kind,
  authority_id: authorityId,
  block_ids: [],
});

test("document pages retain first-seen page order and section order", () => {
  const sections: DocumentSection[] = [
    { kind: "text", section_id: "snapshot", title: "Snapshot", page: "Decision", editable: true, origin: origin("ANALYST", "snapshot-block"), body: "Draft" },
    { kind: "table", section_id: "model", title: "Model", page: "Financials", editable: false, origin: origin("MODEL", "model-1"), columns: ["Metric", "Value"], rows: [["Leverage", "4.2x"]], note: null },
    { kind: "text", section_id: "risk", title: "Risk", page: "Decision", editable: true, origin: origin("ANALYST", "risk-block"), body: "Risk" },
  ];

  assert.deepEqual(groupDocumentPages(sections).map((page) => [page.name, page.sections.map((section) => section.section_id)]), [
    ["Decision", ["snapshot", "risk"]],
    ["Financials", ["model"]],
  ]);
});

test("only analyst-owned editable text can be overlaid by draft blocks", () => {
  const sections: DocumentSection[] = [
    {
      kind: "columns",
      section_id: "model-view",
      title: "Base and Downside Model",
      page: "Financials",
      editable: false,
      origin: origin("MODEL", "model-1"),
      items: [
        [{ kind: "text", section_id: "commentary", title: "Analyst View", page: "Financials", editable: true, origin: origin("ANALYST", "commentary-block"), body: "Saved view" }],
        [{ kind: "table", section_id: "outputs", title: "Calculated Outputs", page: "Financials", editable: false, origin: origin("MODEL", "model-1"), columns: ["Metric", "Value"], rows: [["Leverage", "4.2x"]], note: "Locked" }],
      ],
    },
    { kind: "text", section_id: "limitations", title: "Limitations", page: "Appendix", editable: true, origin: origin("ANALYST", "limitations-block"), body: "Saved limitations" },
  ];

  const overlaid = overlayAnalystText(sections, [
    { kind: "NARRATIVE", block_id: "commentary-block", text: "Unsaved analyst view" },
    { kind: "NARRATIVE", block_id: "model-1", text: "Attempted model overwrite" },
    { kind: "LIMITATIONS", block_id: "limitations-block", text: "Unsaved limitations" },
  ]);
  const columns = overlaid[0];
  assert.equal(columns.kind, "columns");
  if (columns.kind !== "columns") return;
  assert.equal(columns.items[0][0].kind, "text");
  assert.equal(columns.items[0][0].kind === "text" ? columns.items[0][0].body : "", "Unsaved analyst view");
  assert.deepEqual(columns.items[1][0], sections[0].kind === "columns" ? sections[0].items[1][0] : null);
  assert.equal(canEditDocumentSection(columns.items[0][0]), true);
  assert.equal(canEditDocumentSection(columns.items[1][0]), false);
  assert.equal(overlaid[1].kind === "text" ? overlaid[1].body : "", "Unsaved limitations");
});

test("an unsaved first draft previews only its analyst narrative leaves", () => {
  const sections = draftTextSections(
    [
      { kind: "NARRATIVE", block_id: "recommendation", text: "" },
      { kind: "GENERATED_TABLE", block_id: "model", text: "Client copy" },
    ],
    [
      { block_id: "recommendation", title: "Recommendation" },
      { block_id: "model", title: "Calculated Model" },
    ],
  );

  assert.deepEqual(sections.map((section) => [section.section_id, section.title, section.kind === "text" ? section.body : ""]), [
    ["recommendation", "Recommendation", "Not yet drafted."],
  ]);
  assert.equal(sections[0].origin.kind, "ANALYST");
});
