export type FreezeChecklistInput = {
  canWrite: boolean;
  exactSavedRevision: boolean;
  currentModelSelection: boolean;
  requiredModelAvailable: boolean;
};

export function freezeChecklist(input: FreezeChecklistInput) {
  return [
    { id: "write-access", label: "Write access", ready: input.canWrite },
    { id: "saved-revision", label: "Exact saved revision", ready: input.exactSavedRevision },
    { id: "model-selection", label: "Current model selection", ready: input.currentModelSelection },
    { id: "model-availability", label: "Required model availability", ready: input.requiredModelAvailable },
  ] as const;
}
