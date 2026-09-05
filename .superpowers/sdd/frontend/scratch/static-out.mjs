// Serves caos/frontend/out with no API at all, on the port given as argv[2].
// Used to show what the a11y sweep proves when the backend is dead.
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = fileURLToPath(new URL("../../../../caos/frontend/out/", import.meta.url));
const types = { ".css": "text/css", ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".txt": "text/plain", ".svg": "image/svg+xml" };
let apiHits = 0;
createServer(async (request, response) => {
  const pathname = decodeURIComponent(new URL(request.url || "/", "http://x").pathname);
  if (pathname.startsWith("/api/")) { apiHits += 1; response.writeHead(404, { "content-type": "application/json" }).end('{"detail":"dead backend"}'); return; }
  try {
    let target = join(outDir, normalize(pathname.replace(/^\/+/, "")) || "index.html");
    if ((await stat(target)).isDirectory()) target = join(target, "index.html");
    response.writeHead(200, { "content-type": types[extname(target)] || "application/octet-stream" }).end(await readFile(target));
  } catch { response.writeHead(404).end(); }
}).listen(Number(process.argv[2]), "127.0.0.1", () => console.log(`static out on ${process.argv[2]}`));
process.on("SIGTERM", () => { console.log(JSON.stringify({ apiHits })); process.exit(0); });
