export type FreezeChecklistInput = {
  canWrite: boolean;
  exactSavedRevision: boolean;
  currentModelSelection: boolean;
  requiredModelAvailable: boolean;
  currentOpinion: boolean;
};

export function freezeChecklist(input: FreezeChecklistInput) {
  return [
    { id: "write-access", label: "Write access", ready: input.canWrite },
    { id: "saved-revision", label: "Exact saved revision", ready: input.exactSavedRevision },
    { id: "model-selection", label: "Current model selection", ready: input.currentModelSelection },
    { id: "model-availability", label: "Required model availability", ready: input.requiredModelAvailable },
    { id: "opinion-signoff", label: "Current opinion sign-off", ready: input.currentOpinion },
  ] as const;
}

export type FreezeJobStatus = "QUEUED" | "RENDERING" | "PUBLISHED" | "FAILED";

/** Freeze polling: keep asking while the worker owes a render; stop on a terminal state. */
export function freezeJobIsPending(status: string): boolean {
  return status === "QUEUED" || status === "RENDERING";
}

/** Separation of duties, mirrored from the server: the opinion signer and the
 * freeze actor never see a File control for their own output. */
export function canFileFrozen(role: string, subject: string, frozen: { signed_by?: string | null; frozen_by?: string | null }): boolean {
  if (role !== "APPROVER" && role !== "ADMIN") return false;
  if (!subject) return false;
  return subject !== frozen.signed_by && subject !== frozen.frozen_by;
}
