"""Serve the judge-stage status log on port 7860 (the Space health check needs a web server).

The page shows progress lines only. It shows no benchmark items, model responses or judge
results.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

STATUS_LOG = Path(sys.argv[1])
HEADER = (
    "LiverSWAT-Bench Milestone 5 judge stage.\n"
    "REAL MODEL RESULTS - EXPERIMENTAL RESULTS, SOURCE EVIDENCE PENDING HUMAN REVIEW.\n\n"
)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            lines = STATUS_LOG.read_text(encoding="utf-8").splitlines()[-200:]
        except OSError:
            lines = ["starting"]
        body = (HEADER + "\n".join(lines) + "\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


HTTPServer(("0.0.0.0", 7860), Handler).serve_forever()
