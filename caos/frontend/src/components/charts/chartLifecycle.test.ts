import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

import { startChartLifecycle, type ChartInstance, type ChartLifecycleEnvironment } from "./chartLifecycle.ts";

const require = createRequire(import.meta.url);
const { Chart } = require("@antv/g2") as { Chart: { prototype: object } };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((onResolve, onReject) => { resolve = onResolve; reject = onReject; });
  return { promise, resolve, reject };
}

const flush = () => new Promise<void>((resolve) => setImmediate(resolve));

function harness(render: Promise<unknown>, resize: Promise<unknown> = Promise.resolve()) {
  const events: string[] = [];
  let onWidth: ((width: number) => void) | null = null;
  let renderCount = 0;
  const instance: ChartInstance = {
    options: () => { events.push("options"); },
    attr: (key, value) => { events.push(`attr:${key}:${value}`); },
    render: () => { events.push("render"); return renderCount++ === 0 ? render : resize; },
    destroy: () => { events.push("destroy"); },
  };
  const environment: ChartLifecycleEnvironment = {
    load: async () => class { constructor() { return instance; } } as unknown as new () => ChartInstance,
    observe: (callback) => { onWidth = callback; return { observe: () => events.push("observe"), disconnect: () => events.push("disconnect") }; },
    requestFrame: (callback) => { callback(); return 1; },
    cancelFrame: () => { events.push("cancel"); },
  };
  const host = {
    dataset: {},
    getBoundingClientRect: () => ({ width: 640 }),
    querySelectorAll: () => [],
  } as unknown as HTMLElement;
  return { environment, events, host, width: (value: number) => onWidth?.(value) };
}

test("cleanup while the lazy runtime import is pending never creates a chart", async () => {
  const fixture = harness(Promise.resolve());
  const pendingLoad = deferred<new () => ChartInstance>();
  fixture.environment.load = () => pendingLoad.promise;
  const cleanup = startChartLifecycle(fixture.host, {}, (status) => fixture.events.push(status), fixture.environment);
  cleanup();
  pendingLoad.resolve(class { constructor() { fixture.events.push("construct"); } } as unknown as new () => ChartInstance);
  await flush();
  assert.deepEqual(fixture.events.filter((event) => ["construct", "render", "ready", "failed", "destroy"].includes(event)), []);
  assert.equal(fixture.host.dataset.chartLifecycle, "destroyed");
});

test("cleanup waits for a pending render and destroys the owned chart exactly once", async () => {
  const pending = deferred<unknown>();
  const fixture = harness(pending.promise);
  const cleanup = startChartLifecycle(fixture.host, {}, () => fixture.events.push("ready"), fixture.environment);
  await flush();
  cleanup();
  assert.equal(fixture.events.filter((event) => event === "destroy").length, 0);
  pending.resolve(undefined);
  await flush();
  assert.equal(fixture.events.filter((event) => event === "destroy").length, 1);
  assert.equal(fixture.events.includes("ready"), false);
});

test("render and resize rejection fail visibly and release the runtime", async () => {
  const renderFailure = harness(Promise.reject(new Error("render failed")));
  startChartLifecycle(renderFailure.host, {}, (status) => renderFailure.events.push(status), renderFailure.environment);
  await flush();
  assert.deepEqual(renderFailure.events.filter((event) => ["failed", "destroy"].includes(event)), ["destroy", "failed"]);

  const rejectedResize = deferred<unknown>();
  const resizeFailure = harness(Promise.resolve(), rejectedResize.promise);
  startChartLifecycle(resizeFailure.host, {}, (status) => resizeFailure.events.push(status), resizeFailure.environment);
  await flush();
  resizeFailure.width(720);
  rejectedResize.reject(new Error("resize failed"));
  await flush();
  assert.equal(resizeFailure.events.includes("failed"), true);
  assert.equal(resizeFailure.events.filter((event) => event === "destroy").length, 1);
});

test("cleanup waits for an in-flight resize before destroying", async () => {
  const pendingResize = deferred<unknown>();
  const fixture = harness(Promise.resolve(), pendingResize.promise);
  const cleanup = startChartLifecycle(fixture.host, {}, () => fixture.events.push("ready"), fixture.environment);
  await flush();
  fixture.width(720);
  cleanup();
  assert.equal(fixture.events.filter((event) => event === "destroy").length, 0);
  pendingResize.resolve(undefined);
  await flush();
  assert.equal(fixture.events.filter((event) => event === "destroy").length, 1);
});

test("a rejected resize disarms a queued resize before releasing the chart", async () => {
  const firstResize = deferred<unknown>();
  const fixture = harness(Promise.resolve(), firstResize.promise);
  startChartLifecycle(fixture.host, {}, (status) => fixture.events.push(status), fixture.environment);
  await flush();
  fixture.width(640);
  fixture.width(720);
  assert.equal(fixture.events.filter((event) => event === "render").length, 2, "resizes were not serialized");
  firstResize.reject(new Error("first resize failed"));
  await flush();
  assert.equal(fixture.events.filter((event) => event === "render").length, 2, "a queued resize started after failure");
  assert.equal(fixture.events.filter((event) => event === "destroy").length, 1);
  assert.equal(fixture.events.filter((event) => event === "failed").length, 1);
  assert.equal(fixture.host.hidden, true, "failed chart canvas remained visible");
});

test("a synchronous resize throw follows the same failed fallback boundary", async () => {
  const fixture = harness(Promise.resolve());
  fixture.environment.load = async () => class {
    options() {}
    async render() {}
    attr(): void { throw new Error("sync resize failure"); }
    destroy() { fixture.events.push("destroy"); }
  } as unknown as new () => ChartInstance;
  startChartLifecycle(fixture.host, {}, (status) => fixture.events.push(status), fixture.environment);
  await flush();
  fixture.width(640);
  await flush();
  assert.deepEqual(fixture.events.filter((event) => ["failed", "destroy"].includes(event)), ["failed", "destroy"]);
});

test("installed G2 attr plus owned render contains resize rejection", async () => {
  const events: string[] = [];
  let onWidth: ((width: number) => void) | null = null;
  let renders = 0;
  const instance = Object.create(Chart.prototype) as ChartInstance & { value: Record<string, unknown> };
  instance.value = {};
  Object.assign(instance, { _width: 640, _height: 300, emit: () => instance });
  instance.options = () => { events.push("options"); };
  instance.render = () => {
    events.push("render");
    return renders++ === 0 ? Promise.resolve() : Promise.reject(new Error("native resize rejected"));
  };
  instance.destroy = () => { events.push("destroy"); };
  const environment: ChartLifecycleEnvironment = {
    load: async () => class { constructor() { return instance; } } as unknown as new () => ChartInstance,
    observe: (callback) => { onWidth = callback; return { observe: () => {}, disconnect: () => {} }; },
    requestFrame: (callback) => { callback(); return 1; },
    cancelFrame: () => {},
  };
  const host = {
    hidden: false,
    dataset: {},
    getBoundingClientRect: () => ({ width: 640 }),
    querySelectorAll: () => [],
  } as unknown as HTMLElement;
  const unhandled: unknown[] = [];
  const onUnhandled = (error: unknown) => { unhandled.push(error); };
  process.on("unhandledRejection", onUnhandled);
  try {
    startChartLifecycle(host, {}, (status) => events.push(status), environment);
    await flush();
    (onWidth as unknown as (width: number) => void)(720);
    await flush();
    await flush();
    assert.deepEqual(unhandled, []);
    assert.equal(instance.value.width, 720);
    assert.equal(instance.value.height, 300);
    assert.deepEqual(events.filter((event) => ["ready", "failed", "destroy"].includes(event)), ["ready", "failed", "destroy"]);
  } finally {
    process.off("unhandledRejection", onUnhandled);
  }
});

test("a successful lifecycle recovers visibility and loading state on the same host", async () => {
  const failedResize = deferred<unknown>();
  const failed = harness(Promise.resolve(), failedResize.promise);
  const firstCleanup = startChartLifecycle(failed.host, {}, (status) => failed.events.push(status), failed.environment);
  await flush();
  failed.width(720);
  failedResize.reject(new Error("resize failed"));
  await flush();
  assert.equal(failed.host.hidden, true);
  firstCleanup();

  const recoveredEvents: string[] = [];
  const recovered = harness(Promise.resolve());
  startChartLifecycle(failed.host, {}, (status) => recoveredEvents.push(status), recovered.environment);
  assert.equal(failed.host.hidden, false);
  assert.equal(failed.host.dataset.chartLifecycle, "loading");
  await flush();
  assert.deepEqual(recoveredEvents, ["ready"]);
  assert.equal(failed.host.hidden, false);
  assert.equal(failed.host.dataset.chartLifecycle, "ready");
});
