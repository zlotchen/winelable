"""
TTB Label Review — Main Application Server
Serves the frontend and exposes the review API.

Usage:
    python src/server.py               # dev environment
    TTB_ENV=stage python src/server.py

Requires src/model_server.py to be running separately on the configured port (default 9009).
"""

import json
import mimetypes
import os
import re
import shutil
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import config as cfg

_cfg = cfg.load()
_server_cfg = _cfg.get("server", {})
_data_cfg = _cfg.get("data", {})
_ms_cfg = _cfg.get("model_server", {})
_sub_cfg = _cfg.get("submissions", {})

WORK_DIR = Path(__file__).parent.parent
FRONTEND_DIR = WORK_DIR / "frontend"
DATA_DIR = WORK_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
PROCESSED_DIR = DATA_DIR / "processed"
QUARANTINE_DIR = DATA_DIR / "quaranteen"
STATUSES_FILE = WORK_DIR / "conf" / "statuses.json"

HOST = _server_cfg.get("host", "localhost")
PORT = _server_cfg.get("port", 8080)
MODEL_SERVER_HOST = _ms_cfg.get("host", "localhost")
MODEL_SERVER_PORT = _ms_cfg.get("port", 9009)
DEFAULT_LIMIT = _sub_cfg.get("default_limit", 10)

FOLDER_TYPE_MAP = {
    "input":      INPUT_DIR,
    "processed":  PROCESSED_DIR,
    "quaranteen": QUARANTINE_DIR,
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_statuses() -> dict:
    with open(STATUSES_FILE) as f:
        return json.load(f)


def _date_folders(base: Path, date_from: str, date_to: str, limit: int) -> list:
    if not base.exists():
        return []
    folders = sorted(
        [d for d in os.listdir(base) if (base / d).is_dir() and re.match(r"^\d{8}$", d)],
        reverse=True,
    )
    if date_from:
        folders = [d for d in folders if d >= date_from.replace("-", "")]
    if date_to:
        folders = [d for d in folders if d <= date_to.replace("-", "")]
    if not date_from and not date_to:
        folders = folders[:limit]
    return folders


def discover_submissions(
    folder_type: str = "input",
    date_from: str = None,
    date_to: str = None,
    vendor: str = None,
    status: str = None,
    limit: int = None,
) -> list:
    """
    Walk data/<folder_type>/YYYYMMDD/vendorid_X/NN
    For each date+vendor pair keep only the highest (current) index subfolder.
    """
    limit = limit or DEFAULT_LIMIT
    base = FOLDER_TYPE_MAP.get(folder_type)
    if base is None or not base.exists():
        return []

    submissions = []

    for date_folder in _date_folders(base, date_from, date_to, limit):
        date_path = base / date_folder

        for vendor_folder in sorted(os.listdir(date_path)):
            vendor_path = date_path / vendor_folder
            if not vendor_path.is_dir():
                continue
            if vendor and vendor.lower() not in vendor_folder.lower():
                continue

            # Highest lexicographic index = current submission
            index_folders = sorted(
                [f for f in os.listdir(vendor_path) if (vendor_path / f).is_dir()]
            )
            if not index_folders:
                continue

            current = vendor_path / index_folders[-1]
            app_json = current / "application.json"
            if not app_json.exists():
                continue

            with open(app_json) as f:
                meta = json.load(f)

            if status and meta.get("status") != status:
                continue

            # Runtime-only navigation fields (never persisted)
            meta["_folder_path"] = str(current.relative_to(WORK_DIR))
            meta["_folder_type"] = folder_type
            submissions.append(meta)

    return submissions


def get_status_counts() -> dict:
    counts = {}
    for ft in FOLDER_TYPE_MAP:
        for sub in discover_submissions(folder_type=ft, limit=10_000):
            s = sub.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
    return counts


def call_model_server(file_paths: list, file_type: str) -> dict:
    joined = ",".join(file_paths)
    url = (
        f"http://{MODEL_SERVER_HOST}:{MODEL_SERVER_PORT}/?"
        f"file_path={urllib.parse.quote(joined)}&file_type={file_type}"
    )
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        return {"error": f"Model server unreachable: {exc}"}


def move_submission(folder_path: str, target_type: str) -> str:
    """Move entire submission folder to target bucket, preserving date/vendor/index structure."""
    src = WORK_DIR / folder_path
    rel_parts = list(Path(folder_path).parts)   # e.g. ['data','input','20260612','vendorid_111','01']
    rel_parts[1] = target_type                   # replace folder type segment
    dest = WORK_DIR / Path(*rel_parts)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return str(dest.relative_to(WORK_DIR))


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class TTBHandler(BaseHTTPRequestHandler):
    timeout = 60  # medium throughput timeout

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        def p(key, default=None):
            v = params.get(key, [default])
            return unquote(v[0]) if v[0] is not None else default

        if path in ("/", "/index.html"):
            self._file(FRONTEND_DIR / "index.html", "text/html")
        elif path == "/style.css":
            self._file(FRONTEND_DIR / "style.css", "text/css")
        elif path == "/app.js":
            self._file(FRONTEND_DIR / "app.js", "application/javascript")
        elif path.startswith("/data/"):
            self._data_file(path[1:])
        elif path == "/api/submissions":
            self._api_submissions(params)
        elif path == "/api/application":
            self._api_application(p("folder"))
        elif path == "/api/statuses":
            self._api_statuses()
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/save":
            self._api_save()
        else:
            self._json({"error": "Not found"}, 404)

    # ------------------------------------------------------------------
    # API: GET /api/submissions
    # ------------------------------------------------------------------
    def _api_submissions(self, params):
        def p(key):
            v = params.get(key, [None])
            return unquote(v[0]) if v[0] else None

        subs = discover_submissions(
            folder_type=p("folder_type") or "input",
            date_from=p("date_from"),
            date_to=p("date_to"),
            vendor=p("vendor"),
            status=p("status"),
        )
        self._json(subs)

    # ------------------------------------------------------------------
    # API: GET /api/application?folder=<rel_path>
    # ------------------------------------------------------------------
    def _api_application(self, folder_path):
        if not folder_path:
            self._json({"error": "Missing folder parameter"}, 400)
            return

        app_json_path = WORK_DIR / folder_path / "application.json"
        if not app_json_path.exists():
            self._json({"error": "application.json not found"}, 404)
            return

        with open(app_json_path) as f:
            submitted = json.load(f)

        # Determine folder type from path
        path_parts = Path(folder_path).parts
        folder_type = path_parts[1] if len(path_parts) > 1 else "input"

        # Collect image relative paths and build browser-accessible URLs
        image_paths = []
        image_urls = []
        for entry in submitted.get("images", []):
            loc = entry.get("image", {}).get("location")
            if loc:
                image_paths.append(loc)
                image_urls.append(f"/{loc}")

        # Call model server for input / quarantined submissions
        extracted = {}
        if folder_type in ("input", "quaranteen") and image_paths:
            extracted = call_model_server(image_paths, "IMG")

        self._json({
            "submitted_metadata": submitted,
            "extracted_metadata": extracted,
            "image_urls": image_urls,
            "folder_path": folder_path,
            "folder_type": folder_type,
        })

    # ------------------------------------------------------------------
    # API: GET /api/statuses
    # ------------------------------------------------------------------
    def _api_statuses(self):
        statuses = load_statuses()
        counts = get_status_counts()
        for s in statuses.get("statuses", []):
            s["count"] = counts.get(s["value"], 0)
        self._json(statuses)

    # ------------------------------------------------------------------
    # API: POST /api/save
    # ------------------------------------------------------------------
    def _api_save(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._json({"error": "Invalid JSON body"}, 400)
            return

        folder_path = body.get("folder_path")
        new_status = body.get("status", "reviewed")
        metadata = body.get("metadata", {})

        if not folder_path:
            self._json({"error": "Missing folder_path"}, 400)
            return

        src = WORK_DIR / folder_path
        if not src.exists():
            self._json({"error": f"Folder not found: {folder_path}"}, 404)
            return

        now = datetime.now().isoformat()

        # Move folder when status demands it
        if new_status == "quarantine":
            new_rel = move_submission(folder_path, "quaranteen")
            app_json_path = WORK_DIR / new_rel / "application.json"
        elif new_status == "processed":
            new_rel = move_submission(folder_path, "processed")
            app_json_path = WORK_DIR / new_rel / "application.json"
        else:
            new_rel = folder_path
            app_json_path = src / "application.json"

        # Load → merge → write application.json
        if app_json_path.exists():
            with open(app_json_path) as f:
                existing = json.load(f)
        else:
            existing = {}

        # Strip runtime-only keys before persisting
        metadata.pop("_folder_path", None)
        metadata.pop("_folder_type", None)

        existing.update(metadata)
        existing["status"] = new_status
        existing["date_processed"] = now

        with open(app_json_path, "w") as f:
            json.dump(existing, f, indent=2)

        self._json({
            "success": True,
            "new_folder_path": new_rel,
            "date_processed": now,
            "status": new_status,
        })

    # ------------------------------------------------------------------
    # Static file helpers
    # ------------------------------------------------------------------
    def _file(self, filepath: Path, content_type: str):
        if not filepath.is_file():
            self._json({"error": f"File not found: {filepath.name}"}, 404)
            return
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _data_file(self, rel_path: str):
        filepath = WORK_DIR / rel_path
        if not filepath.is_file():
            self._json({"error": "File not found"}, 404)
            return
        mime, _ = mimetypes.guess_type(str(filepath))
        mime = mime or "application/octet-stream"
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload, status: int = 200):
        data = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"[server] {self.address_string()} — {fmt % args}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    server = ThreadingHTTPServer((HOST, PORT), TTBHandler)
    server.request_queue_size = 10
    print(f"[server] TTB Label Review at http://{HOST}:{PORT}")
    print(f"[server] Environment: {_cfg.get('environment', 'dev')}")
    print(f"[server] Model server expected at http://{MODEL_SERVER_HOST}:{MODEL_SERVER_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
