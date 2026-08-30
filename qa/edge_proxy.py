"""Trusted-edge simulator for local production-mode QA.

Production puts Caddy -> oauth2-proxy in front of the app: the proxy
authenticates against OIDC and injects `x-forwarded-user`/`-email`/`-groups`
plus the shared `x-edge-authorization` secret. `identity.py` derives the role
from the groups and refuses anything that does not carry the secret.

A browser cannot set those headers, so testing the *production* identity edge
by hand is impossible without something in front. This is that something — the
same header contract, none of the OIDC. It is a QA harness, never deployed:
`/_qa/role/<ROLE>` swaps which persona the edge asserts, so one browser can
exercise READER / ANALYST / APPROVER / ADMIN against a production-mode app.

ponytail: stdlib http.server, no framework. Streams responses chunk by chunk so
the run-events SSE tail stays live.

    python qa/edge_proxy.py            # listens on 8100, forwards to 8099
"""

from __future__ import annotations

import http.client
import os
import sys
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM_HOST = os.getenv("CAOS_UPSTREAM_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.getenv("CAOS_UPSTREAM_PORT", "8099"))
LISTEN_PORT = int(os.getenv("CAOS_EDGE_PORT", "8100"))
try:
    EDGE_SECRET = os.environ["EDGE_PROXY_SECRET"]
except KeyError:
    raise SystemExit("EDGE_PROXY_SECRET is unset — run `source qa/env.sh` first.") from None

# The personas an OIDC issuer would hand us. Group -> role mapping lives in
# identity.py; these are the group memberships, not the roles themselves.
PERSONAS = {
    "ANALYST": ("analyst.qa@caos.invalid", "caos-analyst"),
    "APPROVER": ("approver.qa@caos.invalid", "caos-approver"),
    "ADMIN": ("admin.qa@caos.invalid", "caos-admin"),
    "READER": ("reader.qa@caos.invalid", "caos-reader"),
    # A signed-in user in no CAOS group at all: identity.py floors them to READER.
    "NOGROUP": ("stranger.qa@caos.invalid", ""),
}
COOKIE = "caos_qa_persona"

# Hop-by-hop headers must not be forwarded (RFC 7230 6.1). `host` is rewritten,
# and every identity header is stripped from the client so a browser cannot
# forge the edge's assertion — which is the whole point of the trusted edge.
DROP_REQUEST = {
    "host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
    "x-edge-authorization", "x-forwarded-user", "x-forwarded-email",
    "x-forwarded-groups", "x-caos-role",
}
DROP_RESPONSE = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "content-length",
}


class EdgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "caos-qa-edge"

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        pass  # the app already logs; a second access log just doubles the noise

    def _persona(self) -> str:
        jar = SimpleCookie(self.headers.get("cookie", ""))
        name = (jar[COOKIE].value if COOKIE in jar else "ANALYST").upper()
        return name if name in PERSONAS else "ANALYST"

    def _switch_persona(self, name: str) -> None:
        name = name.upper()
        if name not in PERSONAS:
            self.send_error(404, "unknown persona")
            return
        body = f"persona now {name}\n".encode()
        self.send_response(303)
        self.send_header("location", "/cases/")
        self.send_header("set-cookie", f"{COOKIE}={name}; Path=/; SameSite=Lax")
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forward(self) -> None:
        if self.path.startswith("/_qa/role/"):
            self._switch_persona(self.path.rsplit("/", 1)[-1])
            return
        persona = self._persona()
        email, groups = PERSONAS[persona]
        headers = {k: v for k, v in self.headers.items() if k.lower() not in DROP_REQUEST}
        headers["x-edge-authorization"] = EDGE_SECRET
        headers["x-forwarded-user"] = email
        headers["x-forwarded-email"] = email
        headers["x-forwarded-groups"] = groups
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else None

        upstream = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=300)
        try:
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in DROP_RESPONSE:
                    self.send_header(name, value)
            # A HEAD (Next prefetches with them) and a 204/304 carry no body at
            # all, so framing one — even an empty chunked one — is a protocol
            # wart that shows up later as an unexplained aborted request.
            bodiless = self.command == "HEAD" or response.status in (204, 304)
            if bodiless:
                self.send_header("content-length", "0")
                self.end_headers()
                return
            # Chunk everything else: an SSE tail has no length, and re-framing one
            # response shape is simpler than branching on two.
            self.send_header("transfer-encoding", "chunked")
            self.end_headers()
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser closed an SSE tail; nothing to report
        except OSError as exc:
            try:
                self.send_error(502, f"upstream unreachable: {exc}")
            except OSError:
                pass
        finally:
            upstream.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _forward


def main() -> None:
    # This process mints any identity it is asked for, signed with the real edge
    # secret. Loopback on both ends is what keeps that a test fixture rather than
    # an authentication bypass, so refuse anything else instead of trusting the
    # operator to notice.
    if UPSTREAM_HOST not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit(
            f"refusing to forge identities to a non-loopback upstream ({UPSTREAM_HOST}). "
            "This is a local QA fixture, not an edge."
        )
    server = ThreadingHTTPServer(("127.0.0.1", LISTEN_PORT), EdgeHandler)
    server.daemon_threads = True
    print(
        f"qa edge on http://127.0.0.1:{LISTEN_PORT} -> {UPSTREAM_HOST}:{UPSTREAM_PORT}; "
        f"personas: {', '.join(PERSONAS)} via /_qa/role/<NAME>",
        file=sys.stderr,
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
