# Design: Issue Identification Agent — POST /analyse-report

**Date:** 2026-06-06
**Status:** Approved

---

## Overview

Replace the mock `vlm_service.py` with a real LangGraph + LiteLLM tool-calling agent that identifies city issues from an uploaded image and optional free-text description. Exposed as a new endpoint `POST /analyse-report`. The existing `POST /submit-report` endpoint is unchanged.

---

## Architecture

```
POST /analyse-report
        │
        ▼
  routers/reports.py  (new handler)
        │
        ▼
  services/agent_service.py
  ┌──────────────────────────────────────────────┐
  │  LangGraph StateGraph                        │
  │                                              │
  │  ┌─────────┐    ┌──────────┐    ┌────────┐  │
  │  │  START  │───▶│  agent   │───▶│ tools  │  │
  │  └─────────┘    │  node    │◀───│  node  │  │
  │                 └────┬─────┘    └────────┘  │
  │                      │ done                 │
  │                 ┌────▼─────┐                │
  │                 │  parse   │                │
  │                 │  output  │                │
  │                 └──────────┘                │
  │                                             │
  │  Model: ChatLiteLLM (local or Nebius)       │
  │  Tools: get_issue_taxonomy()                │
  │          validate_location(name)            │
  └─────────────────────────────────────────────┘
        │
        ▼
  {issue_type, severity, location, description, confidence, raw_label}
```

---

## Input / Output Schema

### Request (`multipart/form-data`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `image` | `UploadFile` | Yes | Photo of the city issue |
| `text_description` | `str` | No | Citizen's free-text description |

Designed for forward compatibility — `lat`, `lng`, `timestamp`, `address` will slot in without breaking existing callers.

### Response

```json
{
  "status": "success",
  "issue": {
    "issue_type": "pothole",
    "severity": 4,
    "location": "Camden",
    "description": "Large pothole on residential road, approximately 30cm diameter",
    "confidence": 0.87,
    "raw_label": null
  }
}
```

- `issue_type` — slug from the taxonomy, or `"other"` if no match
- `severity` — 1 (low) to 5 (high), set by the agent
- `location` — borough name (validated against `density.csv`)
- `confidence` — agent's self-reported certainty, 0.0–1.0
- `raw_label` — model's own label when `issue_type` is `"other"`, otherwise `null`

---

## Components

### `services/agent_service.py` (new)

LangGraph `StateGraph` with three nodes:

- **`agent` node** — calls `ChatLiteLLM` with image bytes + text description. System prompt instructs the model to call `get_issue_taxonomy()` first to retrieve valid types, then classify and produce a final structured answer.
- **`tools` node** — executes requested tool calls:
  - `get_issue_taxonomy()` — reads and returns `data/issue_types.yaml`
  - `validate_location(name: str)` — checks location against boroughs in `density.csv`
- **`parse_output` node** — extracts structured issue dict from final agent message; sets `confidence` and `raw_label`

### `data/issue_types.yaml` (new)

```yaml
issue_types:
  - slug: pothole
    label: Pothole
    severity_hint: 3
  - slug: graffiti
    label: Graffiti
    severity_hint: 2
  - slug: broken_streetlight
    label: Broken Streetlight
    severity_hint: 3
  - slug: fly_tipping
    label: Fly-tipping
    severity_hint: 2
```

New types are added by editing this file — no code changes required.

### `config.py` (new)

Loads at startup from environment variables:

| Env var | Purpose |
|---|---|
| `LITELLM_MODEL` | e.g. `ollama/llava`, `nebius/...` |
| `LITELLM_API_BASE` | Base URL for local or Nebius endpoint |
| `LITELLM_API_KEY` | API key (optional for local models) |

Builds the `ChatLiteLLM` instance once and provides it to `agent_service`.

### `routers/reports.py` (modified)

Adds `POST /analyse-report` handler alongside the existing `POST /submit-report`. Validates image readability at router level (`422` if invalid) then delegates to `agent_service.run(image_bytes, text_description)`.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Model unreachable | Raises `503` — no silent fallback to random data |
| Agent returns no structured output | Returns `issue_type: "other"`, `confidence: 0.0`, raw text in `description` |
| `get_issue_taxonomy()` fails (missing/bad YAML) | Passes empty taxonomy to model; agent may produce `"other"` more often |
| Image unreadable | `422` returned at router before agent is invoked |

---

## Out of Scope (this iteration)

- GPS / reverse geocoding (`lat`, `lng` fields)
- Timestamp and EXIF metadata
- Delegating `/submit-report` to `/analyse-report` internally
- Streaming agent responses
