import assert from "node:assert/strict";
import test from "node:test";
import { ApiRequestError, api, isUnavailableRoute } from "./api.ts";

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
