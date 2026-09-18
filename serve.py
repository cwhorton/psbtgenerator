#!/usr/bin/env python3
"""Optional local server for the PSBT Generator.

index.html works when opened directly from disk as long as the explorer sends CORS
headers on every endpoint. Some explorers (mempool.guide at the time of writing) only
send them on part of their API, so the browser refuses those requests. This script
serves index.html on localhost and forwards explorer requests with CORS headers added.
The page detects the proxy automatically and routes all explorer calls through it.

Usage:  python3 serve.py [port]      (default port 8765)
Then open http://127.0.0.1:8765/ in a browser.

Standard library only. Binds to 127.0.0.1 only. Forwards GET requests only, to
https://<host>/api/... for hostnames that look like DNS names.
"""
import http.server
import os
import re
import socketserver
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?)+(:\d{1,5})?$")
PING = b"psbtgenerator-proxy"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        if self.path == "/proxy/ping":
            return self._send(200, "text/plain", PING)
        if self.path.startswith("/proxy/"):
            return self._proxy(self.path[len("/proxy/"):])
        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _proxy(self, rest):
        host, _, path = rest.partition("/")
        host = host.lower()
        if not HOST_RE.match(host) or not path.startswith("api/"):
            return self._send(400, "text/plain", b"bad proxy path; expected /proxy/<host>/api/...")
        url = f"https://{host}/{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "psbtgenerator/1.0", "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
                ctype = r.headers.get("Content-Type", "application/octet-stream")
                return self._send(r.status, ctype, body)
        except urllib.error.HTTPError as e:
            body = e.read() if hasattr(e, "read") else b""
            return self._send(e.code, e.headers.get("Content-Type", "text/plain") if e.headers else "text/plain", body)
        except Exception as e:  # DNS failure, timeout, TLS error
            return self._send(502, "text/plain", f"proxy could not reach {host}: {e}".encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def _send(self, status, ctype, body):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    with Server(("127.0.0.1", port), Handler) as httpd:
        print(f"PSBT Generator: open http://127.0.0.1:{port}/  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
