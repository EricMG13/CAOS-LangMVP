// The observed-404 presentation: a capability whose route this deployment does not
// serve. Same idiom as the shell's QA drawer state block (state-block unavailable).
// Deliberately no Retry — a route that is absent cannot succeed on retry.
export default function Unavailable({ title, context }: { title: string; context?: string }) {
  return <div className="state-block unavailable">
    <strong>{title}</strong>
    <p>Not available in this deployment.</p>
    {context ? <p className="muted">{context}</p> : null}
  </div>;
}
