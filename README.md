# Zero-Cloud Council Prioritization Engine

This is the backend for the "Zero-Cloud Council Prioritization Engine" developed during the NVIDIA hackathon. 

The system ingests citizen reports (images) of city issues, uses a local Vision-Language Model (VLM) via NVIDIA NIM to extract data, enriches it with local crime/deprivation data (SQLite), population density (CSV), and live TfL traffic disruptions, and calculates a deterministic priority score. All AI inference runs locally without cloud APIs.

## Project Structure
- `/data/`: Contains static datasets (`density.csv`, `issue_types.yaml`, `context.db`).
- `/routers/`: FastAPI endpoint definitions.
- `/services/`: Business logic for the agentic pipeline, context enrichment, scoring, and tool definitions.
- `/scripts/`: Data pipeline scripts for building the context database.
- `/docs/`: Design documents (prioritisation criteria, superpowers).
- `/tests/`: Unit tests.
- `main.py`: Application entry point.
- `start_services.sh`: One-command startup for all services (persistent across SSH disconnects).
- `requirements.txt`: Python dependencies.

---

## 🛠️ Environment Setup

Since we are a team of 4 sharing a DGX Spark and running heavy models like **Nemotron Nano 12B VL**, it is **critical** to use a virtual environment. This prevents system-level package conflicts and ensures everyone is running the exact same dependency versions.

### Conda (Recommended for DGX)
```bash
# 1. Create a fresh conda environment
conda create -n seeit-sortit python=3.10

# 2. Activate the environment
conda activate seeit-sortit

# 3. Install requirements
pip install -r requirements.txt
```

---

## 🐳 Running the Local VLM (NVIDIA NIM)

The API relies on a local NVIDIA NIM container serving the **Nemotron Nano 12B VL** vision-language model. The container exposes an OpenAI-compatible API on port 8888.

### Prerequisites
1. Docker with NVIDIA Container Toolkit installed
2. NGC API key set: `export NGC_API_KEY=<your-key>`
3. Login to NGC registry: `echo "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin`

### Manual Start (if not using `start_services.sh`)
```bash
export LOCAL_NIM_CACHE=$HOME/.cache/nim
mkdir -p $LOCAL_NIM_CACHE

docker run -d \
  --name seeit-sortit-nim \
  --gpus all \
  --shm-size=16GB \
  --ipc=host \
  --privileged \
  --restart unless-stopped \
  -e NGC_API_KEY=$NGC_API_KEY \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8888:8000 \
  nvcr.io/nim/nvidia/nemotron-nano-12b-v2-vl:latest
```

Monitor logs: `docker logs -f seeit-sortit-nim`

---

## 🚀 Quick Start (Recommended)

The easiest way to start **all** services at once is with the startup script. It runs everything inside a `tmux` session that survives SSH disconnects:

```bash
conda activate seeit-sortit
./start_services.sh
```

This will:
1. Kill any orphaned processes on ports 8000/8888
2. Start the NIM Docker container (detached, auto-restarts on crash)
3. Launch `uvicorn` (API server) in tmux window 0
4. Launch `localtunnel` (public URL) in tmux window 1
5. Stream NIM container logs in tmux window 2

### Reconnecting After SSH Disconnect
```bash
tmux attach -t seeit-sortit
```

Switch between windows using `Ctrl+B` then `0`, `1`, or `2`.

### Manual Start (without tmux)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- API docs: `http://localhost:8000/docs`
- Public URL: `https://fixmy-council-seeit-sortit.loca.lt`

---

## 🌍 Exposing the API to the Internet

To access the API from outside the local network (e.g., from your phone on 5G):

```bash
npx localtunnel --port 8000 --subdomain fixmy-council-seeit-sortit
```

Public URL: `https://fixmy-council-seeit-sortit.loca.lt`

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/analyse-report` | **Primary endpoint.** Agentic VLM pipeline → context enrichment → priority score |
| `POST` | `/submit-report` | Same agentic pipeline with identical scoring (legacy endpoint name) |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive Swagger UI |

### Example Request
```bash
curl -X POST \
  'http://localhost:8000/analyse-report' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'image=@/path/to/test_image.jpg' \
  -F 'text_description=Large pothole near Camden High Street'
```

### Example Response
```json
{
  "status": "success",
  "priority_score": 42350.0,
  "priority_band": "HIGH",
  "analysis": {
    "issue_type": "pothole",
    "severity": 4,
    "location": "Camden",
    "description": "Large pothole on residential street, approximately 30cm wide.",
    "confidence": 0.92,
    "raw_label": null
  },
  "enrichment": {
    "tfl_delay_factor": 1.24,
    "population_density": 10500,
    "borough": "Camden"
  }
}
```

---

## 🧰 Troubleshooting

If you accidentally hit `Ctrl+Z` to suspend a process instead of `Ctrl+C` to cleanly stop it, the ports will remain locked in the background. This will cause `[Errno 98] Address already in use` for FastAPI, or cause Localtunnel to hold your subdomain hostage. 

Run these commands to forcefully free the ports:

**To forcefully kill a suspended `uvicorn` (Port 8000 in use):**
```bash
kill -9 $(lsof -t -i :8000)
```

**To forcefully kill suspended `localtunnel` instances:**
```bash
pkill -9 -f localtunnel
```

**To kill the Docker NIM container:**
```bash
docker rm -f seeit-sortit-nim
```
