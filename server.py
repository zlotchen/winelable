"""
TTB Label Review — backend server
Serves the frontend and exposes a JSON API for label review requests.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import config as cfg

_server_cfg = cfg.get("server", {})
_data_cfg = cfg.get("data", {})

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
DATA_DIR = os.path.join(os.path.dirname(__file__), _data_cfg.get("input_dir", "data/input").split("/")[0])
HOST = _server_cfg.get("host", "localhost")
PORT = _server_cfg.get("port", 8080)


class TTBHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_file(os.path.join(FRONTEND_DIR, "index.html"), "text/html")
        elif path.endswith(".css"):
            self._serve_file(os.path.join(FRONTEND_DIR, path.lstrip("/")), "text/css")
        elif path.endswith(".js"):
            self._serve_file(os.path.join(FRONTEND_DIR, path.lstrip("/")), "application/javascript")
        elif path == "/api/submissions":
            self._handle_submissions()
        else:
            self._not_found()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/review":
            self._handle_review()
        else:
            self._not_found()

    # ------------------------------------------------------------------
    # API handlers (stubs — to be implemented as specs arrive)
    # ------------------------------------------------------------------

    def _handle_submissions(self):
        """Return list of pending submissions from data/input."""
        submissions = []
        input_dir = os.path.join(DATA_DIR, "input")
        for date_folder in sorted(os.listdir(input_dir)):
            date_path = os.path.join(input_dir, date_folder)
            if not os.path.isdir(date_path):
                continue
            for vendor_folder in sorted(os.listdir(date_path)):
                vendor_path = os.path.join(date_path, vendor_folder)
                if not os.path.isdir(vendor_path):
                    continue
                for seq_folder in sorted(os.listdir(vendor_path)):
                    seq_path = os.path.join(vendor_path, seq_folder)
                    app_json = os.path.join(seq_path, "application.json")
                    if os.path.isfile(app_json):
                        with open(app_json) as f:
                            submissions.append(json.load(f))
        self._json_response(submissions)

    def _handle_review(self):
        """Accept a review request, run model inference, return result."""
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        # TODO: call model.review(body) once model module is ready
        result = {"status": "pending", "message": "Model inference not yet wired up", "input": body}
        self._json_response(result)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serve_file(self, filepath, content_type):
        if not os.path.isfile(filepath):
            self._not_found()
            return
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json_response(self, payload, status=200):
        data = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _not_found(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")


def run():
    server = HTTPServer((HOST, PORT), TTBHandler)
    print(f"TTB Label Review server running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    run()
