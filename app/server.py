#!/usr/bin/env python3
"""Small local web server for the reviewer-facing MVP app."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

APP_DIR = Path(__file__).resolve().parent

ROUTES = {
    "/": "/index.html",
    "/asreview-explainer": "/asreview-explainer.html",
    "/methods-results": "/methods-results.html",
    "/why-more-review": "/why-more-review.html",
    "/how-many-more": "/how-many-more.html",
}


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ROUTES:
            target = ROUTES[path]
            if target in ROUTES:
                self.send_response(302)
                self.send_header("Location", ROUTES[target])
                self.end_headers()
                return
            self.path = target

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
