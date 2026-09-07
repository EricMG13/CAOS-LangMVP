export type ChartInstance = {
  options: (options: Record<string, unknown>) => void;
  render: () => Promise<unknown>;
  changeSize: (width: number, height: number) => Promise<unknown>;
  destroy: () => void;
};

type ChartConstructor = new (options: Record<string, unknown>) => ChartInstance;
type SizeObserver = { observe: (host: HTMLElement) => void; disconnect: () => void };

export type ChartLifecycleEnvironment = {
  load: () => Promise<ChartConstructor>;
  observe: (onWidth: (width: number) => void) => SizeObserver;
  requestFrame: (callback: () => void) => number;
  cancelFrame: (frame: number) => void;
};

const HEIGHT = 300;

const browserEnvironment: ChartLifecycleEnvironment = {
  load: async () => (await import("@antv/g2")).Chart as unknown as ChartConstructor,
  observe: (onWidth) => {
    const observer = new ResizeObserver((entries) => onWidth(Math.floor(entries[0]?.contentRect.width ?? 0)));
    return observer;
  },
  requestFrame: (callback) => window.requestAnimationFrame(callback),
  cancelFrame: (frame) => window.cancelAnimationFrame(frame),
};

/** Owns exactly one lazy G2 instance, its observer and pending resize frame. */
export function startChartLifecycle(
  host: HTMLElement,
  options: Record<string, unknown>,
  onStatus: (status: "ready" | "failed") => void,
  environment: ChartLifecycleEnvironment = browserEnvironment,
) {
  let active = true;
  let failed = false;
  let pendingOperations = 0;
  let instance: ChartInstance | null = null;
  let observer: SizeObserver | null = null;
  let resizeFrame = 0;
  let resizeRunning = false;
  let queuedWidth = 0;
  const destroy = () => {
    observer?.disconnect();
    observer = null;
    const owned = instance;
    instance = null;
    owned?.destroy();
  };
  const destroyIfIdle = () => {
    if (pendingOperations === 0 && (!active || failed)) destroy();
  };
  const fail = () => {
    if (!active || failed) return;
    failed = true;
    observer?.disconnect();
    observer = null;
    environment.cancelFrame(resizeFrame);
    queuedWidth = 0;
    host.hidden = true;
    destroyIfIdle();
    onStatus("failed");
  };
  const operationSettled = () => {
    pendingOperations -= 1;
    destroyIfIdle();
  };
  const runResize = () => {
    if (!active || failed || !instance || queuedWidth < 1) return;
    const width = queuedWidth;
    queuedWidth = 0;
    resizeRunning = true;
    pendingOperations += 1;
    let resizing: Promise<unknown>;
    try {
      resizing = instance.changeSize(Math.max(240, width), HEIGHT);
    } catch {
      resizeRunning = false;
      fail();
      operationSettled();
      return;
    }
    void Promise.resolve(resizing).catch(fail).finally(() => {
      resizeRunning = false;
      operationSettled();
      if (active && !failed && queuedWidth > 0) resizeFrame = environment.requestFrame(runResize);
    });
  };
  const queueResize = (width: number) => {
    if (!active || failed || !instance || width < 1) return;
    queuedWidth = width;
    if (resizeRunning) return;
    environment.cancelFrame(resizeFrame);
    resizeFrame = environment.requestFrame(runResize);
  };

  void environment.load().then(async (Chart) => {
    if (!active) return;
    const width = Math.max(240, Math.floor(host.getBoundingClientRect().width));
    instance = new Chart({ container: host, width, height: HEIGHT, autoFit: false });
    instance.options(options);
    pendingOperations += 1;
    try {
      await instance.render();
    } finally {
      operationSettled();
    }
    if (!active) {
      destroy();
      return;
    }
    host.querySelectorAll("canvas, svg").forEach((node) => {
      node.setAttribute("aria-hidden", "true");
      node.setAttribute("tabindex", "-1");
    });
    host.dataset.chartLifecycle = "ready";
    onStatus("ready");
    observer = environment.observe(queueResize);
    observer.observe(host);
  }).catch(() => {
    if (active) fail();
    else destroy();
  });

  return () => {
    active = false;
    queuedWidth = 0;
    environment.cancelFrame(resizeFrame);
    observer?.disconnect();
    // G2 render and changeSize both own the canvas while their promises are in
    // flight; release the runtime after the last operation settles.
    if (pendingOperations === 0) destroy();
    host.dataset.chartLifecycle = "destroyed";
  };
}
