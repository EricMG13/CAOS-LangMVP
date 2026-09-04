// WebKit rejects a same-origin fetch that is still in flight when the
// document navigates away with `TypeError: <url> due to access control
// checks.` (Chromium and Firefox never settle those promises). Next's
// segment-cache prefetches and HEAD route probes are unawaited, so on a slow
// runner every navigation can leave a few of them in flight and the rejection
// surfaces as an unhandled-rejection page error with the URL printed without
// its scheme (`/127.0.0.1:8000/cases/ due to access control checks.`).
// Reproduced on CI run 33863698677 (every flagged URL answered 200 in the
// retained trace) and locally by holding responses for two seconds.
//
// The predicate drops such a rejection only with evidence: WebKit, the URL is
// same-origin with the server under test, and this page saw the server answer
// that exact URL 2xx/3xx. A cross-origin fetch, a CSP-blocked fetch or a
// refused URL never meets all three, so a genuine access-control failure still
// fails the run. Callers retain every dropped entry in the report.
const TEARDOWN = /^(?<url>\S+) due to access control checks\.$/;

export function webkitTeardownRejection(message, { browserName, baseURL, responded }) {
  if (browserName !== "webkit") return null;
  const match = TEARDOWN.exec(message);
  if (!match) return null;
  const base = new URL(baseURL);
  const raw = match.groups.url;
  const withScheme = raw.startsWith("/") && !raw.startsWith("//") ? `${base.protocol}/${raw}` : raw;
  let url;
  try {
    url = new URL(withScheme);
  } catch {
    return null;
  }
  if (url.origin !== base.origin) return null;
  const status = responded.get(url.href);
  if (!(status >= 200 && status < 400)) return null;
  return { url: url.href, status };
}
