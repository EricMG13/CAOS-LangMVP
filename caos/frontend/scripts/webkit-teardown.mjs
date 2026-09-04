// WebKit rejects a same-origin fetch that is still in flight when the
// document navigates away with `TypeError: <url> due to access control
// checks.` (Chromium and Firefox never settle those promises). Next's
// segment-cache prefetches and HEAD route probes are unawaited, so on a slow
// runner every navigation can leave a few of them in flight and the rejection
// surfaces as an unhandled-rejection page error with the URL printed without
// its scheme (`/127.0.0.1:8000/cases/ due to access control checks.`).
// Reproduced on CI run 33863698677 (every flagged URL answered 200 in the
// retained trace, eleven requests aborted at navigation) and locally by
// holding responses for two seconds.
//
// The predicate drops such a rejection only with evidence: WebKit, the URL is
// same-origin with the server under test, and either this page saw the server
// answer that exact URL 2xx/3xx, or the request for that exact URL ended
// without any response (the browser abandoned it) while the server had
// answered the same path 2xx/3xx to an earlier non-document request on this
// page (a prefetch's `_rsc` query changes per navigation, so the first request
// for a fresh query can be the abandoned one). A cross-origin fetch fails the
// origin check; a CSP- or CORS-blocked fetch never has a 2xx answer for its
// path from a non-document request; a refused URL has neither. Callers retain
// every dropped entry in the report.
const TEARDOWN = /^(?<url>\S+) due to access control checks\.$/;

const pathOf = (href) => {
  const url = new URL(href);
  return `${url.origin}${url.pathname}`;
};

export function webkitTeardownRejection(message, { browserName, baseURL, responded, abandoned = new Set() }) {
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
  const ok = (status) => status >= 200 && status < 400;
  const status = responded.get(url.href);
  if (ok(status)) return { url: url.href, status, evidence: "answered" };
  if (!abandoned.has(url.href)) return null;
  const path = pathOf(url.href);
  const pathStatus = [...responded].find(([href, seen]) => ok(seen) && pathOf(href) === path)?.[1];
  if (pathStatus === undefined) return null;
  return { url: url.href, status: pathStatus, evidence: "abandoned; path answered" };
}
