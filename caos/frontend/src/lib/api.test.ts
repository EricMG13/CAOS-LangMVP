import assert from "node:assert/strict";
import test from "node:test";
import { ApiRequestError, api, firstErrorMessage, isUnavailableRoute } from "./api.ts";

test("api returns parsed JSON from successful responses", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({ id: "case_1" }), { status: 200 });

  assert.deepEqual(await api<{ id: string }>("/api/cases/case_1"), { id: "case_1" });
});

test("api parses empty 204 responses without a special case", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(null, { status: 204 });

  await assert.rejects(api("/api/cases/case_1"), SyntaxError);
});

test("api extracts stable error details", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Case access denied" }), { status: 403 });

  await assert.rejects(api("/api/cases/case_1"), new Error("Case access denied"));
});

test("api failures carry the HTTP status for observed-404 capability gating", async (t) => {
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

test("only an observed 404 or 405 reads as an unavailable route", () => {
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
