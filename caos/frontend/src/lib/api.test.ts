import assert from "node:assert/strict";
import test from "node:test";
import { ApiRequestError, NETWORK_UNAVAILABLE, NetworkError, UNEXPECTED_RESPONSE, UnexpectedResponseError, api, firstErrorMessage, isUnavailableRoute, listCases } from "./api.ts";

test("api returns parsed JSON from successful responses", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({ id: "case_1" }), { status: 200 });

  assert.deepEqual(await api<{ id: string }>("/api/cases/case_1"), { id: "case_1" });
});

test("listCases follows stable id cursors until the server returns a short page", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  const firstPage = Array.from({ length: 100 }, (_, index) => ({ id: `case_${String(index).padStart(3, "0")}` }));
  const secondPage = [{ id: "case_100" }, { id: "case_101" }];
  const calls: { input: string; signal: AbortSignal | null | undefined }[] = [];
  const controller = new AbortController();
  globalThis.fetch = async (input, init) => {
    calls.push({ input: String(input), signal: init?.signal });
    return new Response(JSON.stringify(calls.length === 1 ? firstPage : secondPage), { status: 200 });
  };

  const cases = await listCases(controller.signal);

  assert.equal(cases.length, 102);
  assert.deepEqual(calls.map(({ input }) => input), [
    "/api/cases?limit=100",
    "/api/cases?limit=100&cursor=case_099",
  ]);
  assert.deepEqual(calls.map(({ signal }) => signal), [controller.signal, controller.signal]);
});

test("listCases rejects a full page whose cursor cannot advance", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  const page = Array.from({ length: 100 }, () => ({ id: "case_same" }));
  globalThis.fetch = async () => new Response(JSON.stringify(page), { status: 200 });

  const caught = await listCases().then(() => null, (rejection: unknown) => rejection);

  assert.ok(caught instanceof UnexpectedResponseError);
  assert.equal(caught.message, UNEXPECTED_RESPONSE);
  assert.match(String(caught.cause), /cursor did not advance/);
});

test("api wraps a successful response with no JSON body", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(null, { status: 204 });

  const caught = await api("/api/cases/case_1").then(() => null, (rejection: unknown) => rejection);
  assert.ok(caught instanceof UnexpectedResponseError);
  assert.equal(caught.message, UNEXPECTED_RESPONSE);
  assert.ok(caught.cause instanceof SyntaxError);
});

test("api wraps malformed JSON from a successful response", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response("not-json", { status: 200 });

  const caught = await api("/api/cases/case_1").then(() => null, (rejection: unknown) => rejection);
  assert.ok(caught instanceof UnexpectedResponseError);
  assert.equal(caught.message, UNEXPECTED_RESPONSE);
  assert.ok(caught.cause instanceof SyntaxError);
});

test("api extracts stable error details", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Case access denied" }), { status: 403 });

  await assert.rejects(api("/api/cases/case_1"), new Error("Case access denied"));
});

test("api failures classify a private 404 only as ambiguous unavailability", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });

  const caught = await api("/api/admin/bundle").then(() => null, (rejection: unknown) => rejection);
  assert.ok(caught instanceof ApiRequestError, "api did not reject with the typed request error");
  assert.equal(caught.status, 404);
  assert.equal(caught.message, "Not Found");
  assert.equal(isUnavailableRoute(caught), true);
});

test("api never serves a raw object or validation detail as its message", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: { code: "DELIVERABLE_VERSION_CONFLICT", current: null } }), { status: 409 });

  const caught = await api("/api/cases/case_1/deliverables/FULL_CREDIT/draft").then(() => null, (rejection: unknown) => rejection);
  assert.ok(caught instanceof ApiRequestError, "api did not reject with the typed request error");
  // A bare code is the whole sentence the analyst reads, so it arrives humanized.
  assert.equal(caught.message, "DELIVERABLE VERSION CONFLICT");
  assert.notEqual(caught.message, "[object Object]");
  // The raw served value stays on the error so a caller can still branch on it.
  assert.deepEqual(caught.detail, { code: "DELIVERABLE_VERSION_CONFLICT", current: null });
});

test("firstErrorMessage unwraps every served detail shape before the fallback", () => {
  // Object detail: the refusal sentence wins over the code.
  assert.equal(firstErrorMessage(new ApiRequestError(422, { detail: "Focus questions must be NFC-normalized." }), "fallback"), "Focus questions must be NFC-normalized.");
  // Object detail carrying only a typed code — humanized, because it is the sentence.
  assert.equal(firstErrorMessage(new ApiRequestError(409, { code: "MODEL_REVISION_CONFLICT" }), "fallback"), "MODEL REVISION CONFLICT");
  // 422 validation array: the served messages, joined, never "[object Object]".
  assert.equal(firstErrorMessage(new ApiRequestError(422, [{ loc: ["body", "depth"], msg: "Input should be 'screen' or 'full'" }]), "fallback"), "Input should be 'screen' or 'full'");
  assert.equal(firstErrorMessage(new ApiRequestError(422, [{ msg: "field required" }, { msg: "value is not a valid integer" }]), "fallback"), "field required; value is not a valid integer");
  // String detail.
  assert.equal(firstErrorMessage(new ApiRequestError(403, "Case access denied"), "fallback"), "Case access denied");
  // A plain Error keeps its own message.
  assert.equal(firstErrorMessage(new Error("network down"), "fallback"), "network down");
  // A detail carrying nothing readable falls through to Error.message.
  assert.equal(firstErrorMessage(new ApiRequestError(500, { trace_id: "abc" }), "fallback"), "Request failed (500)");
  // Non-Error rejections and empty messages take the caller's fallback.
  assert.equal(firstErrorMessage("boom", "fallback"), "fallback");
  assert.equal(firstErrorMessage(null, "fallback"), "fallback");
  assert.equal(firstErrorMessage(undefined, "fallback"), "fallback");
  assert.equal(firstErrorMessage({ detail: "not an Error" }, "fallback"), "fallback");
  assert.equal(firstErrorMessage(new Error(""), "fallback"), "fallback");
});

test("only an observed 404 or static catch-all 405 reads as unavailable", () => {
  assert.equal(isUnavailableRoute(new ApiRequestError(404, "Not Found")), true);
  // 405: this server mounts StaticFiles(html=True) at "/" as the catch-all for every
  // unrouted path; a non-GET request to an absent path reaches that catch-all and
  // Starlette's StaticFiles answers any non-GET method with 405, not 404. A capability
  // POST therefore observes 405, not 404, when its route isn't served here.
  assert.equal(isUnavailableRoute(new ApiRequestError(405, "Method Not Allowed")), true);
  assert.equal(isUnavailableRoute(new ApiRequestError(403, "Case access denied")), false);
  assert.equal(isUnavailableRoute(new ApiRequestError(503, "authority unavailable")), false);
  assert.equal(isUnavailableRoute(new Error("network down")), false);
  assert.equal(isUnavailableRoute(new SyntaxError("Unexpected token")), false);
  assert.equal(isUnavailableRoute(null), false);
  assert.equal(isUnavailableRoute({ status: 404 }), false);
});

test("a request that never reaches the server reads as the network state, never as engine text", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  // Chromium, Firefox and WebKit each word the rejection differently; none of
  // those words may reach the analyst (DESIGN.md §5 `offline`, FE-A0 F7).
  for (const engineText of ["Failed to fetch", "NetworkError when attempting to fetch resource.", "Load failed"]) {
    globalThis.fetch = async () => { throw new TypeError(engineText); };
    const caught = await api("/api/cases").then(() => null, (rejection: unknown) => rejection);
    assert.ok(caught instanceof NetworkError, `fetch rejection "${engineText}" was not typed as a network failure`);
    assert.equal(caught.message, NETWORK_UNAVAILABLE);
    assert.equal(firstErrorMessage(caught, "fallback"), NETWORK_UNAVAILABLE);
    assert.doesNotMatch(firstErrorMessage(caught, "fallback"), new RegExp(engineText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.equal(isUnavailableRoute(caught), false, "a network failure is not an absent route");
    assert.equal((caught as NetworkError).cause instanceof TypeError, true, "the engine rejection is retained as the cause");
  }
  // An abort is the caller's own doing and keeps its identity.
  const abort = new DOMException("The user aborted a request.", "AbortError");
  globalThis.fetch = async () => { throw abort; };
  const aborted = await api("/api/cases").then(() => null, (rejection: unknown) => rejection);
  assert.strictEqual(aborted, abort);
  // A served refusal is still a served refusal.
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Case access denied" }), { status: 403 });
  await assert.rejects(api("/api/cases/case_1"), new Error("Case access denied"));
});

test("api preserves abort identity while reading a successful response body", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  const abort = new DOMException("The response body was aborted.", "AbortError");
  globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) { controller.error(abort); } }));
  await assert.rejects(api("/api/cases"), (caught: unknown) => caught === abort);
});
