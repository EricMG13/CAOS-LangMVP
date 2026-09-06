type Props = {
  evidenceId: string;
  linkedId: string;
  // The chip passes itself as the drawer's opener: WebKit does not focus a
  // button on click, so an opener inferred from document.activeElement would
  // return focus to whatever the analyst touched before the chip.
  onOpen: (evidenceId: string, opener: HTMLElement) => void;
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
    onClick={(event) => onOpen(evidenceId, event.currentTarget)}
    onFocus={() => onPreview(evidenceId)}
    onMouseEnter={() => onPreview(evidenceId)}
    onMouseLeave={onPreviewEnd}
  >
    {evidenceId}
  </button>;
}
