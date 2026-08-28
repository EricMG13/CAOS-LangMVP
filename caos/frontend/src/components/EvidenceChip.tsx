type Props = {
  evidenceId: string;
  linkedId: string;
  onOpen: (evidenceId: string) => void;
  onPreview: (evidenceId: string) => void;
  onPreviewEnd: () => void;
};

export default function EvidenceChip({ evidenceId, linkedId, onOpen, onPreview, onPreviewEnd }: Props) {
  const linked = linkedId === evidenceId;
  return <button
    type="button"
    className={`evidence-chip${linked ? " is-linked" : ""}`}
    data-evidence-id={evidenceId}
    aria-label={`Open evidence ${evidenceId}`}
    onBlur={onPreviewEnd}
    onClick={() => onOpen(evidenceId)}
    onFocus={() => onPreview(evidenceId)}
    onMouseEnter={() => onPreview(evidenceId)}
    onMouseLeave={onPreviewEnd}
  >
    {evidenceId}
  </button>;
}
