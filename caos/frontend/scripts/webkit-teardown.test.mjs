// WebKit rejects a same-origin fetch that is still in flight when the document
// navigates away with `TypeError: <url> due to access control checks.`; an
// unawaited prefetch turns that into a page error. The predicate drops such a
// rejection only with evidence that the server answered that exact URL, so a
// genuine cross-origin or blocked request still fails the run.
import assert from "node:assert/strict";
import { test } from "node:test";

import { webkitTeardownRejection } from "./webkit-teardown.mjs";

const baseURL = "http://127.0.0.1:8000";
const responded = new Map([
  ["http://127.0.0.1:8000/cases/", 200],
  ["http://127.0.0.1:8000/cases/__next.$d$destination.__PAGE__.txt?case=case-1&_rsc=abc", 200],
  ["http://127.0.0.1:8000/api/refused", 403],
]);

test("a same-origin URL the server answered 2xx is a teardown rejection under WebKit", () => {
  const result = webkitTeardownRejection("/127.0.0.1:8000/cases/ due to access control checks.", { browserName: "webkit", baseURL, responded });
  assert.deepEqual(result, { url: "http://127.0.0.1:8000/cases/", status: 200, evidence: "answered" });
});

test("an abandoned request for a fresh prefetch query is dropped when its path was answered before", () => {
  const abandoned = new Set(["http://127.0.0.1:8000/cases/__next.$d$destination.__PAGE__.txt?case=case-2&_rsc=zzz"]);
  const result = webkitTeardownRejection("/127.0.0.1:8000/cases/__next.$d$destination.__PAGE__.txt?case=case-2&_rsc=zzz due to access control checks.", { browserName: "webkit", baseURL, responded, abandoned });
  assert.deepEqual(result, { url: "http://127.0.0.1:8000/cases/__next.$d$destination.__PAGE__.txt?case=case-2&_rsc=zzz", status: 200, evidence: "abandoned; path answered" });
});

test("an abandoned request whose path was never answered stays a page error", () => {
  const abandoned = new Set(["http://127.0.0.1:8000/api/blocked?x=1"]);
  assert.equal(webkitTeardownRejection("/127.0.0.1:8000/api/blocked?x=1 due to access control checks.", { browserName: "webkit", baseURL, responded, abandoned }), null);
  const unanswered = new Set(["http://127.0.0.1:8000/cases/__next.$d$destination.__PAGE__.txt?case=case-9&_rsc=q"]);
  assert.equal(webkitTeardownRejection("/127.0.0.1:8000/cases/__next.$d$destination.__PAGE__.txt?case=case-9&_rsc=q due to access control checks.", { browserName: "webkit", baseURL, responded: new Map(), abandoned: unanswered }), null);
});

test("the scheme-bearing form and query strings resolve to the same evidence", () => {
  const result = webkitTeardownRejection("http://127.0.0.1:8000/cases/__next.$d$destination.__PAGE__.txt?case=case-1&_rsc=abc due to access control checks.", { browserName: "webkit", baseURL, responded });
  assert.equal(result?.status, 200);
});

test("a URL the server never answered 2xx or 3xx stays a page error", () => {
  assert.equal(webkitTeardownRejection("/127.0.0.1:8000/api/refused due to access control checks.", { browserName: "webkit", baseURL, responded }), null);
  assert.equal(webkitTeardownRejection("/127.0.0.1:8000/api/never-seen due to access control checks.", { browserName: "webkit", baseURL, responded }), null);
});

test("a cross-origin URL stays a page error even when something answered it", () => {
  const foreign = new Map([["http://evil.invalid/cases/", 200]]);
  assert.equal(webkitTeardownRejection("http://evil.invalid/cases/ due to access control checks.", { browserName: "webkit", baseURL, responded: foreign }), null);
});

test("other engines and other messages are never filtered", () => {
  assert.equal(webkitTeardownRejection("/127.0.0.1:8000/cases/ due to access control checks.", { browserName: "chromium", baseURL, responded }), null);
  assert.equal(webkitTeardownRejection("TypeError: Load failed", { browserName: "webkit", baseURL, responded }), null);
});
