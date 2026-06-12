# TTB COLA Label Review

A proof-of-concept application for reviewing wine and alcohol product label submissions against TTB (Alcohol and Tobacco Tax and Trade Bureau) COLA requirements. It uses a locally-hosted SmolVLM vision-language model to extract label metadata from submitted images and presents reviewers with a side-by-side comparison UI for adjudication.

---

## Assumptions

### Submission Files

- Each submission consists of a set of files — one or two label images and a PDF text file — uploaded by a separate upstream application into a dedicated folder. One folder per submission.
- File validation (size limits, allowed file types, and binary safety scanning) is assumed to have been performed by the upstream upload process **before** files are placed into the input folders. Files that fail validation are routed to the Quarantine or Invalid buckets by that upstream process and are not the responsibility of this application.
- Each submission folder contains a system-generated metadata file (`application.json`) with the fields `TTB_ID`, `status`, `vendor_code`, and `date_submission`. These fields are trusted as accurate and do not require re-validation by this application.

### Permissions

- This application has **read** access to all files within input, processed, and quarantine folders, and **write** access limited to the `application.json` metadata file within each submission folder.
- When a **Save** action is performed, the application appends or updates only the `application.json` metadata file with the new field values and an automatically generated `date_reviewed` timestamp. All updated metadata fields, including `status`, are written in JSON format to that file.
- The application is authorised to **move** an entire submission folder (all contained files) from the input folder tree to either the processed or quarantine bucket when the corresponding status action is taken.
- Read, write, and list access to the folder buckets is intended to be limited to authorised roles in production. **Security hardening and session token issuance are explicitly out of scope for this initial proof-of-concept**, per stakeholder agreement.

---

## Project Structure

```
winelabel/
├── src/
│   ├── config.py          # Environment-aware config loader
│   ├── model.py           # SmolVLM model wrapper
│   ├── model_server.py    # Inference HTTP server (port 9009)
│   └── server.py          # Main application server (port 8080)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── conf/
│   ├── statuses.json      # Configurable status values
│   ├── dev/config.json
│   ├── stage/config.json
│   └── prod/config.json
├── data/
│   ├── input/             # Incoming submissions
│   ├── processed/         # Approved submissions
│   └── quaranteen/        # Quarantined submissions
└── models/                # Locally downloaded HuggingFace models
```

---

## Prerequisites

- Python 3.9 or later
- pip

Install Python dependencies from the project root:

```bash
pip install -r requirements.txt
```

---

## Starting the Application (Local Linux)

The application runs as two separate processes. Open two terminal windows from the project root directory.

### Terminal 1 — Model Inference Server

```bash
python src/model_server.py
```

This loads the SmolVLM model into memory (may take a minute on first run) and starts listening on `http://localhost:9009`. Wait for the message:

```
[model_server] Model ready on cpu.
[model_server] Inference server at http://localhost:9009
```

### Terminal 2 — Main Application Server

```bash
python src/server.py
```

Expected output:

```
[config] Loaded 'dev' configuration from conf/dev/config.json
[server] TTB Label Review at http://localhost:8080
[server] Environment     : dev
[server] Thread pool     : min=2  max=8
[server] Model server    : http://localhost:9009  timeout=600s
```

Open a browser and navigate to **http://localhost:8080**.

### One-command startup with public URL (ngrok)

`start.sh` launches both servers and an ngrok HTTPS tunnel in a single command. Requires a free ngrok account.

**One-time ngrok setup:**

```bash
# 1. Get your free authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken <your-token>
```

**Start everything:**

```bash
./start.sh          # dev environment (default)
./start.sh stage    # stage environment
```

The script will:
1. Start `model_server.py` and wait for the model to finish loading
2. Start `server.py`
3. Open an ngrok HTTPS tunnel on port 8080
4. Print the public URL in the terminal

```
┌──────────────────────────────────────────────────────────────┐
│  TTB COLA Label Review is running                            │
├──────────────────────────────────────────────────────────────┤
│  Public URL  : https://abc123.ngrok-free.app                 │
│  Local URL   : http://localhost:8080                         │
│  Environment : dev                                           │
│  ngrok UI    : http://localhost:4040                         │
├──────────────────────────────────────────────────────────────┤
│  Logs        : logs/model_server.log                         │
│                logs/server.log                               │
│                logs/ngrok.log                                │
├──────────────────────────────────────────────────────────────┤
│  Press Ctrl+C to stop all processes                          │
└──────────────────────────────────────────────────────────────┘
```

Press **Ctrl+C** to cleanly shut down all three processes.

> **Note:** The free ngrok tier provides one persistent tunnel with a randomly assigned URL that remains stable as long as the process is running. Restarting ngrok assigns a new URL unless you have a paid plan with a reserved domain.

### Switching Environments

```bash
TTB_ENV=stage python src/model_server.py
TTB_ENV=stage python src/server.py
```

Available environments: `dev`, `stage`, `prod`.

---

## Configuration — `dev` Environment

Configuration is stored in `conf/dev/config.json`. The `dev` environment is the default when `TTB_ENV` is not set.

```json
{
  "environment": "dev",

  "server": {
    "host": "localhost",   // bind address for the main app server
    "port": 8080,          // browser-accessible port
    "debug": true
  },

  "model_server": {
    "host": "localhost",   // bind address for the inference server
    "port": 9009,          // inference server port
    "timeout_ms": 600000   // max wait for model response (10 min, in milliseconds)
  },

  "thread_pool": {
    "min_workers": 2,      // threads pre-warmed on startup
    "max_workers": 8       // hard ceiling on concurrent request threads
  },

  "model": {
    "name": "SmolVLM-500M-Instruct",   // model folder name under models/
    "models_dir": "models",            // path relative to project root
    "device": "cpu",                   // "cpu" for dev, "cuda" for stage/prod
    "max_new_tokens": 512              // max tokens generated per inference call
  },

  "data": {
    "input_dir": "data/input",           // unprocessed submissions
    "processed_dir": "data/processed",   // approved submissions
    "quarantine_dir": "data/quaranteen"  // quarantined submissions
  },

  "submissions": {
    "default_limit": 10    // max date folders scanned when no date filter is set
  },

  "logging": {
    "level": "DEBUG",
    "file": "logs/dev.log"
  }
}
```

### Status Values

Submission statuses are defined in `conf/statuses.json` and shared across all environments:

| Value | Label |
|---|---|
| `new` | New |
| `reviewed` | Reviewed |
| `processed` | Processed |
| `quarantine` | Quarantined |
| `error` | Error |

---

## Submission Folder Layout

Each submission is a folder following this naming pattern:

```
data/input/YYYYMMDD/vendorid_<vendor_id>/<index>/
    application.json    # submission metadata
    <label_image>.jpg   # one or two label images
```

For the same date and vendor, only the folder with the **highest index** is treated as the current submission. Lower-indexed folders are ignored.

---

## Downloading the Models

The application requires at least one SmolVLM model downloaded locally before starting.

### Install the HuggingFace CLI

```bash
pip install -U "huggingface_hub"
```

### Authenticate with HuggingFace

```bash
hf auth login
```

### Download the models

From the project root directory:

```bash
# Smaller model — used in dev (cpu)
mkdir -p models/SmolVLM-500M-Instruct
huggingface-cli download HuggingFaceTB/SmolVLM-500M-Instruct \
    --local-dir ./models/SmolVLM-500M-Instruct

# Larger model — used in stage/prod (cuda)
mkdir -p models/SmolVLM-Instruct
huggingface-cli download HuggingFaceTB/SmolVLM-Instruct \
    --local-dir ./models/SmolVLM-Instruct
```
