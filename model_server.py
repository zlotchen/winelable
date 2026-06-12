"""
TTB Label Review — Model Inference Server
Loads SmolVLM-500M-Instruct locally and serves GET requests for image analysis.

NOTE: The specification listed port 990099, which exceeds the maximum valid TCP port
(65535). This implementation uses port 9009 as the nearest valid interpretation.

Usage:
    python model_server.py            # uses TTB_ENV (default: dev)
    TTB_ENV=stage python model_server.py

GET /?file_path=<path>&file_type=<IMG|TXT>
    file_path  : relative path from project root; comma-separated for multiple files
    file_type  : IMG  — image inference with label extraction prompt
                 TXT  — text/PDF analysis (stub, ready for spec)
Returns: JSON
"""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import config as cfg

_cfg = cfg.load()
_ms_cfg = _cfg.get("model_server", {})
_model_cfg = _cfg.get("model", {})

HOST = _ms_cfg.get("host", "localhost")
PORT = _ms_cfg.get("port", 9009)
WORK_DIR = Path(__file__).parent
MODELS_DIR = WORK_DIR / _model_cfg.get("models_dir", "models")
MODEL_NAME = _model_cfg.get("name", "SmolVLM-500M-Instruct")
MAX_NEW_TOKENS = _model_cfg.get("max_new_tokens", 512)

# Exact prompt as specified
IMG_PROMPT = (
    "You are reader of images.  Try to find the following text and data in the image: "
    "Wine_Name or Fanciful_Name, Brand_Name, Total_bottle_capacity or Volume, "
    "Grape_Variety or Grape_Name, Vendor_Name or Distributor_name, Vintage or Year, "
    "Alchohol_concentration, GOVERNMENT_WARNING.  Extract text metadata from this image "
    "in JSON format. Include Name, Vintage year, Producer Name, Beverage or Wine type, "
    "Alcohol content, Volume in milliliters, Country of Origin.  Include all fields even "
    "if unable or unsure of the values and put empty values.  If unsure of the value, "
    "include numeric attribute of the probability the value is correct or missing. "
    "Ignore watermarks in the images. Note that vintage is the year of the wine making. "
    "If you find two candidates for the value, create an array of the values."
)

_model = None
_processor = None
_model_lock = threading.Lock()


def load_model():
    global _model, _processor
    model_path = MODELS_DIR / MODEL_NAME

    from transformers import AutoProcessor, AutoModelForVision2Seq
    import torch

    print(f"[model_server] Loading {MODEL_NAME} from {model_path} ...")
    _processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True)

    device = _model_cfg.get("device", "cpu")
    dtype = torch.float16 if device == "cuda" else torch.float32
    _model = AutoModelForVision2Seq.from_pretrained(
        str(model_path),
        local_files_only=True,
        torch_dtype=dtype,
    )
    if device == "cuda":
        _model = _model.to("cuda")
    _model.eval()
    print(f"[model_server] Model ready on {device}.")


def infer_images(file_paths: list) -> dict:
    from PIL import Image
    import torch

    images = []
    for p in file_paths:
        full = WORK_DIR / p
        if not full.is_file():
            return {"error": f"File not found: {p}"}
        images.append(Image.open(full).convert("RGB"))

    # Build messages with one {"type":"image"} per image
    content = [{"type": "image"} for _ in images]
    content.append({"type": "text", "text": IMG_PROMPT})
    messages = [{"role": "user", "content": content}]

    with _model_lock:
        prompt = _processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = _processor(text=prompt, images=images, return_tensors="pt")

        if next(_model.parameters()).is_cuda:
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        import torch
        with torch.no_grad():
            generated_ids = _model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)

        raw = _processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # Strip echoed prompt if present (some models repeat it)
    if IMG_PROMPT in raw:
        raw = raw[raw.rfind(IMG_PROMPT) + len(IMG_PROMPT):]

    # Attempt to parse JSON from the output
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find a JSON array
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            return {"items": json.loads(raw[start:end])}
    except (json.JSONDecodeError, ValueError):
        pass

    return {"raw_output": raw.strip()}


class ModelHandler(BaseHTTPRequestHandler):
    timeout = 60  # medium throughput timeout

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/", ""):
            self._send_json({"error": "Not found"}, 404)
            return

        params = parse_qs(parsed.query)
        file_path_raw = params.get("file_path", [None])[0]
        file_type = params.get("file_type", [None])[0]

        if not file_path_raw or not file_type:
            self._send_json({"error": "Missing required parameters: file_path, file_type"}, 400)
            return

        file_paths = [unquote(p.strip()) for p in file_path_raw.split(",") if p.strip()]

        try:
            if file_type == "IMG":
                result = infer_images(file_paths)
            elif file_type == "TXT":
                result = {"message": "TXT/PDF inference not yet implemented", "file_paths": file_paths}
            else:
                self._send_json({"error": f"Unknown file_type '{file_type}'. Use IMG or TXT."}, 400)
                return
            self._send_json(result)
        except Exception as exc:
            self._send_json({"error": str(exc)}, 500)

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[model_server] {self.address_string()} — {fmt % args}")


def run():
    load_model()
    server = ThreadingHTTPServer((HOST, PORT), ModelHandler)
    server.request_queue_size = 10  # medium throughput queue depth
    print(f"[model_server] Inference server at http://{HOST}:{PORT}")
    print(f"[model_server] Example: http://{HOST}:{PORT}/?file_path=data/input/20260612/vendorid_111/01/label.jpg&file_type=IMG")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[model_server] Stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
