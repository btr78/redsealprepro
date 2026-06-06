#!/usr/bin/env python3
"""MixCheck AI — Local server with Anthropic proxy"""
import json, os, sys, socketserver, urllib.request, urllib.error
from http.server import SimpleHTTPRequestHandler

PORT = 8742
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/models":
            api_key = self.headers.get("X-Api-Key", "").strip()
            if not api_key:
                self._json(400, {"error": "No API key"}); return
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self._json(200, json.loads(resp.read()))
            except urllib.error.HTTPError as e:
                self._json(e.code, json.loads(e.read()))
            except Exception as e:
                self._json(500, {"error": str(e)})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/api/analyze":
            self.send_response(404); self.end_headers(); return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            api_key = body.get("apiKey", "").strip()
            payload = body.get("payload", {})

            if not api_key:
                self._json(400, {"error": "No API key provided"})
                return

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type":       "application/json",
                    "x-api-key":          api_key,
                    "anthropic-version":  "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                self._json(200, json.loads(resp.read()))

        except urllib.error.HTTPError as e:
            self._json(e.code, json.loads(e.read()))
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if self.path == "/api/analyze":
            print(f"[MixCheck] {fmt % args}", flush=True)

class ReusableTCP(socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    with ReusableTCP(("127.0.0.1", PORT), Handler) as httpd:
        print(f"MixCheck AI running → http://127.0.0.1:{PORT}/index.html", flush=True)
        httpd.serve_forever()
