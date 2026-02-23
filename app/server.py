#!/usr/bin/env python3
"""Small local web server for the reviewer-facing MVP app."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

APP_DIR = Path(__file__).resolve().parent

REWRITES = {
    "/": "/index.html",
    "/index": "/index.html",
    "/projects": "/index.html",
    "/projects/e5cr7": "/projects-e5cr7.html",
    "/lab": "/lab.html",
}

REDIRECTS = {
    "/asreview-explainer": "/projects/e5cr7#overview",
    "/methods-results": "/projects/e5cr7#methods-results",
    "/why-more-review": "/projects/e5cr7#why-more-review",
    "/how-many-more": "/projects/e5cr7#how-many-more",
    "/lab/e5cr7": "/projects/e5cr7#lab-access",
}


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in REDIRECTS:
            self.send_response(302)
            self.send_header("Location", REDIRECTS[path])
            self.end_headers()
            return

        if path in REWRITES:
            self.path = REWRITES[path]

        return super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reviewer-facing MVP app server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Serving app on http://{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
