# Issue Identification Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `POST /analyse-report` — a LangGraph tool-calling agent that identifies city issues from an uploaded image and optional text description, using LiteLLM to route to local or Nebius models.

**Architecture:** A LangGraph `StateGraph` with three nodes: `agent` (ChatLiteLLM with tools bound), `tools` (ToolNode executing `get_issue_taxonomy` and `validate_location`), and `parse` (extracts structured JSON from the agent's final message). The graph loops agent→tools→agent until the model stops calling tools, then parses the result. The new endpoint lives alongside the existing `/submit-report` with no changes to it.

**Tech Stack:** Python 3.12, FastAPI, LangGraph 0.2+, langchain-litellm, langchain-core, PyYAML, pytest, pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add langgraph, langchain-litellm, langchain-core, pyyaml, python-dotenv, pytest, pytest-asyncio, pytest-mock, httpx |
| `config.py` | Create | Build `ChatLiteLLM` instance from env vars |
| `data/issue_types.yaml` | Create | Issue type taxonomy (slugs, labels, severity hints) |
| `services/agent_tools.py` | Create | `get_issue_taxonomy` and `validate_location` LangChain tools |
| `services/agent_service.py` | Create | LangGraph StateGraph + public `run()` async function |
| `routers/reports.py` | Modify | Add `POST /analyse-report` handler |
| `pytest.ini` | Create | asyncio_mode = auto |
| `tests/__init__.py` | Create | Empty |
| `tests/test_config.py` | Create | Tests for ChatLiteLLM env var loading |
| `tests/test_agent_tools.py` | Create | Tests for each tool function |
| `tests/test_agent_service.py` | Create | Tests for run() with mocked graph |
| `tests/test_reports_analyse.py` | Create | Tests for the new endpoint |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Replace the contents of `requirements.txt` with:

```
fastapi
uvicorn
python-multipart
pandas
requests
pydantic
langgraph>=0.2.0
langchain-litellm>=0.1.0
langchain-core>=0.3.0
pyyaml>=6.0
python-dotenv>=1.0
pytest>=8.0
pytest-asyncio>=0.24.0
pytest-mock>=3.14.0
httpx>=0.27.0
```

- [ ] **Step 2: Install**

```bash
source .venv/bin/activate
uv pip install -r requirements.txt
```

Expected: All packages install without errors. `langgraph`, `langchain_litellm`, and `yaml` should be importable.

- [ ] **Step 3: Verify key imports**

```bash
python -c "from langgraph.graph import StateGraph, MessagesState, START, END; from langgraph.prebuilt import ToolNode; from langchain_litellm import ChatLiteLLM; import yaml; print('OK')"
```

Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "✨feat: add langgraph, langchain-litellm, pyyaml dependencies"
```

---

## Task 2: Create pytest.ini

**Files:**
- Create: `pytest.ini`

- [ ] **Step 1: Write pytest.ini**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: Verify**

```bash
pytest --collect-only 2>&1 | head -5
```

Expected: no `asyncio_mode` warning.

---

## Task 3: Create config.py

**Files:**
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` (empty file).

Create `tests/test_config.py`:

```python
import pytest
from unittest.mock import patch


def test_get_llm_uses_litellm_model_env_var(monkeypatch):
    monkeypatch.setenv("LITELLM_MODEL", "nebius/Qwen/Qwen2.5-VL-72B-Instruct")
    monkeypatch.setenv("LITELLM_API_BASE", "https://api.studio.nebius.com/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "test-key")

    # Import inside test so env vars are set before module loads
    import importlib
    import config
    importlib.reload(config)
    from config import get_llm

    llm = get_llm()
    assert llm.model == "nebius/Qwen/Qwen2.5-VL-72B-Instruct"


def test_get_llm_defaults_to_ollama_llava(monkeypatch):
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    monkeypatch.delenv("LITELLM_API_BASE", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)

    import importlib
    import config
    importlib.reload(config)
    from config import get_llm

    llm = get_llm()
    assert llm.model == "ollama/llava"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: `ImportError` — `config` module not found.

- [ ] **Step 3: Write config.py**

```python
import os
from dotenv import load_dotenv
from langchain_litellm import ChatLiteLLM

load_dotenv()


def get_llm() -> ChatLiteLLM:
    model = os.environ.get("LITELLM_MODEL", "ollama/llava")
    api_base = os.environ.get("LITELLM_API_BASE")
    api_key = os.environ.get("LITELLM_API_KEY", "no-key")

    kwargs: dict = {"model": model, "api_key": api_key}
    if api_base:
        kwargs["api_base"] = api_base

    return ChatLiteLLM(**kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/__init__.py tests/test_config.py pytest.ini
git commit -m "✨feat: add config.py for ChatLiteLLM env-based configuration"
```

---

## Task 4: Create data/issue_types.yaml

**Files:**
- Create: `data/issue_types.yaml`

- [ ] **Step 1: Write data/issue_types.yaml**

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
    severity_hint: 4
  - slug: damaged_pavement
    label: Damaged Pavement
    severity_hint: 3
  - slug: abandoned_vehicle
    label: Abandoned Vehicle
    severity_hint: 2
  - slug: flooding
    label: Flooding
    severity_hint: 5
  - slug: fallen_tree
    label: Fallen Tree
    severity_hint: 4
```

- [ ] **Step 2: Verify YAML parses**

```bash
python -c "import yaml; d = yaml.safe_load(open('data/issue_types.yaml')); print(len(d['issue_types']), 'types loaded')"
```

Expected: `8 types loaded`

- [ ] **Step 3: Commit**

```bash
git add data/issue_types.yaml
git commit -m "✨feat: add issue type taxonomy YAML"
```

---

## Task 5: Create services/agent_tools.py

**Files:**
- Create: `services/agent_tools.py`
- Create: `tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_agent_tools.py`:

```python
import pytest
import yaml
import pandas as pd


SAMPLE_YAML = yaml.dump({
    "issue_types": [
        {"slug": "pothole", "label": "Pothole", "severity_hint": 3},
        {"slug": "graffiti", "label": "Graffiti", "severity_hint": 2},
    ]
})


def test_get_issue_taxonomy_returns_list(tmp_path, monkeypatch):
    yaml_file = tmp_path / "issue_types.yaml"
    yaml_file.write_text(SAMPLE_YAML)
    import services.agent_tools as tools_mod
    monkeypatch.setattr(tools_mod, "ISSUE_TYPES_PATH", str(yaml_file))

    result = tools_mod.get_issue_taxonomy.invoke({})

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["slug"] == "pothole"


def test_get_issue_taxonomy_contains_required_keys(tmp_path, monkeypatch):
    yaml_file = tmp_path / "issue_types.yaml"
    yaml_file.write_text(SAMPLE_YAML)
    import services.agent_tools as tools_mod
    monkeypatch.setattr(tools_mod, "ISSUE_TYPES_PATH", str(yaml_file))

    result = tools_mod.get_issue_taxonomy.invoke({})

    for item in result:
        assert "slug" in item
        assert "label" in item
        assert "severity_hint" in item


def test_validate_location_returns_true_for_known_borough(tmp_path, monkeypatch):
    csv_file = tmp_path / "density.csv"
    csv_file.write_text("Location,Population_Density\nCamden,10500\nWestminster,12000\n")
    import services.agent_tools as tools_mod
    monkeypatch.setattr(tools_mod, "DENSITY_CSV_PATH", str(csv_file))

    assert tools_mod.validate_location.invoke({"name": "Camden"}) is True


def test_validate_location_returns_false_for_unknown_location(tmp_path, monkeypatch):
    csv_file = tmp_path / "density.csv"
    csv_file.write_text("Location,Population_Density\nCamden,10500\n")
    import services.agent_tools as tools_mod
    monkeypatch.setattr(tools_mod, "DENSITY_CSV_PATH", str(csv_file))

    assert tools_mod.validate_location.invoke({"name": "Narnia"}) is False


def test_validate_location_case_sensitive(tmp_path, monkeypatch):
    csv_file = tmp_path / "density.csv"
    csv_file.write_text("Location,Population_Density\nCamden,10500\n")
    import services.agent_tools as tools_mod
    monkeypatch.setattr(tools_mod, "DENSITY_CSV_PATH", str(csv_file))

    assert tools_mod.validate_location.invoke({"name": "camden"}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_agent_tools.py -v
```

Expected: `ImportError` — `services.agent_tools` not found.

- [ ] **Step 3: Write services/agent_tools.py**

```python
import os

import pandas as pd
import yaml
from langchain_core.tools import tool

ISSUE_TYPES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "issue_types.yaml")
DENSITY_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "density.csv")


@tool
def get_issue_taxonomy() -> list[dict]:
    """Returns the list of valid issue types for council reporting. Call this first before classifying any issue."""
    with open(ISSUE_TYPES_PATH) as f:
        data = yaml.safe_load(f)
    return data["issue_types"]


@tool
def validate_location(name: str) -> bool:
    """Check whether a location name is a known London borough in the density database."""
    df = pd.read_csv(DENSITY_CSV_PATH)
    return bool(name in df["Location"].values)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent_tools.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/agent_tools.py tests/test_agent_tools.py
git commit -m "✨feat: add get_issue_taxonomy and validate_location agent tools"
```

---

## Task 6: Create services/agent_service.py

**Files:**
- Create: `services/agent_service.py`
- Create: `tests/test_agent_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_agent_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


MOCK_ISSUE = {
    "issue_type": "pothole",
    "severity": 4,
    "location": "Camden",
    "description": "Large pothole on residential street, approximately 30cm wide.",
    "confidence": 0.92,
    "raw_label": None,
}


async def test_run_returns_issue_report_from_graph():
    mock_result = {"messages": [], "issue_report": MOCK_ISSUE}

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_get_graph.return_value = mock_graph

        from services.agent_service import run
        result = await run(b"fake_jpeg_bytes", "There is a pothole")

    assert result["issue_type"] == "pothole"
    assert result["severity"] == 4
    assert result["location"] == "Camden"
    assert result["confidence"] == 0.92
    assert result["raw_label"] is None


async def test_run_returns_default_when_issue_report_is_none():
    mock_result = {"messages": [], "issue_report": None}

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_get_graph.return_value = mock_graph

        from services.agent_service import run, _DEFAULT_RESULT
        result = await run(b"fake_jpeg_bytes")

    assert result == _DEFAULT_RESULT
    assert result["issue_type"] == "other"
    assert result["confidence"] == 0.0


async def test_run_passes_text_description_when_provided():
    captured = {}

    async def capturing_ainvoke(state):
        captured["messages"] = state["messages"]
        return {"messages": state["messages"], "issue_report": MOCK_ISSUE}

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = capturing_ainvoke
        mock_get_graph.return_value = mock_graph

        from services.agent_service import run
        await run(b"fake_jpeg_bytes", "big pothole near the park")

    human_msg = captured["messages"][-1]  # [SystemMessage, HumanMessage]
    content = human_msg.content
    assert any(c.get("type") == "image_url" for c in content)
    assert any(c.get("type") == "text" and "pothole" in c.get("text", "") for c in content)


async def test_run_omits_text_when_not_provided():
    mock_result = {"messages": [], "issue_report": MOCK_ISSUE}
    captured = {}

    async def capturing_ainvoke(state):
        captured["messages"] = state["messages"]
        return mock_result

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = capturing_ainvoke
        mock_get_graph.return_value = mock_graph

        from services.agent_service import run
        await run(b"fake_jpeg_bytes")

    human_msg = captured["messages"][-1]
    content = human_msg.content
    assert len(content) == 1
    assert content[0]["type"] == "image_url"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_agent_service.py -v
```

Expected: `ImportError` — `services.agent_service` not found.

- [ ] **Step 3: Write services/agent_service.py**

```python
import base64
import json
import re
from typing import Annotated

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode

from config import get_llm
from services.agent_tools import get_issue_taxonomy, validate_location


class AgentState(MessagesState):
    issue_report: dict | None


SYSTEM_PROMPT = """You are a city issue identification agent for council reporting in London.

Analyze the provided image and optional text description to identify the city issue.

Follow these steps in order:
1. Call get_issue_taxonomy() to retrieve the list of valid issue types.
2. Analyze the image and text to identify the issue type, severity, and location.
3. Call validate_location() to verify that the borough you identified is in the database.
4. Return your final answer as a JSON object with EXACTLY these fields:
   - issue_type: slug from the taxonomy (e.g. "pothole"), or "other" if no slug matches
   - severity: integer 1-5 (1=low impact, 5=critical/urgent)
   - location: London borough name
   - description: 1-2 sentence description of the visible issue
   - confidence: float 0.0-1.0 representing your certainty in the classification
   - raw_label: your own descriptive label string if issue_type is "other", otherwise null

Your FINAL message must be ONLY the JSON object with no surrounding text."""

TOOLS = [get_issue_taxonomy, validate_location]

_DEFAULT_RESULT: dict = {
    "issue_type": "other",
    "severity": 1,
    "location": "Unknown",
    "description": "Agent could not produce a structured result.",
    "confidence": 0.0,
    "raw_label": None,
}

_graph = None


def _build_graph():
    llm = get_llm().bind_tools(TOOLS)
    tool_node = ToolNode(TOOLS)

    def agent_node(state: AgentState) -> dict:
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "parse"

    def parse_output(state: AgentState) -> dict:
        last = state["messages"][-1]
        content = last.content if isinstance(last.content, str) else ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                return {"issue_report": parsed}
            except json.JSONDecodeError:
                pass
        return {"issue_report": None}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("parse", parse_output)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "parse": "parse"})
    graph.add_edge("tools", "agent")
    graph.add_edge("parse", END)

    return graph.compile()


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


async def run(image_bytes: bytes, text_description: str | None = None) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    content: list[dict] = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
    ]
    if text_description:
        content.append({"type": "text", "text": text_description})

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=content),
    ]

    result = await _get_graph().ainvoke({"messages": messages, "issue_report": None})
    return result.get("issue_report") or _DEFAULT_RESULT
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent_service.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/agent_service.py tests/test_agent_service.py
git commit -m "✨feat: add LangGraph agent service with tool-calling loop"
```

---

## Task 7: Add POST /analyse-report endpoint

**Files:**
- Modify: `routers/reports.py`
- Create: `tests/test_reports_analyse.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reports_analyse.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

MOCK_ISSUE = {
    "issue_type": "pothole",
    "severity": 3,
    "location": "Camden",
    "description": "Pothole on residential road.",
    "confidence": 0.85,
    "raw_label": None,
}


def test_analyse_report_returns_200_with_issue():
    with patch("routers.reports.run_agent", new=AsyncMock(return_value=MOCK_ISSUE)):
        response = client.post(
            "/analyse-report",
            files={"image": ("test.jpg", b"fake_jpeg_data", "image/jpeg")},
            data={"text_description": "There is a large pothole"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["issue"]["issue_type"] == "pothole"
    assert body["issue"]["severity"] == 3
    assert body["issue"]["confidence"] == 0.85


def test_analyse_report_works_without_text_description():
    with patch("routers.reports.run_agent", new=AsyncMock(return_value=MOCK_ISSUE)):
        response = client.post(
            "/analyse-report",
            files={"image": ("test.jpg", b"fake_jpeg_data", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_analyse_report_returns_422_for_empty_image():
    response = client.post(
        "/analyse-report",
        files={"image": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 422


def test_analyse_report_passes_text_to_agent():
    captured = {}

    async def capturing_run(image_bytes, text_description=None):
        captured["text"] = text_description
        return MOCK_ISSUE

    with patch("routers.reports.run_agent", new=capturing_run):
        client.post(
            "/analyse-report",
            files={"image": ("test.jpg", b"fake_jpeg_data", "image/jpeg")},
            data={"text_description": "graffiti on the wall"},
        )

    assert captured["text"] == "graffiti on the wall"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_reports_analyse.py -v
```

Expected: tests fail — `POST /analyse-report` does not exist yet.

- [ ] **Step 3: Add the endpoint to routers/reports.py**

Add these imports at the top of `routers/reports.py` (after existing imports):

```python
from fastapi import APIRouter, File, UploadFile, Depends, Form, HTTPException
from services.agent_service import run as run_agent
```

Then add the new endpoint at the bottom of `routers/reports.py`:

```python
@router.post("/analyse-report")
async def analyse_report(
    image: UploadFile = File(...),
    text_description: Optional[str] = Form(None),
):
    """
    Identifies the city issue in an uploaded image using a local/Nebius VLM agent.
    Accepts an optional free-text description from the citizen.
    Returns a structured issue report ready for council prioritisation.
    """
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Image file is empty")

    issue = await run_agent(image_bytes, text_description)

    return {
        "status": "success",
        "issue": issue,
    }
```

The full updated import block at the top of `routers/reports.py` should be:

```python
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import Optional

from services.vlm_service import extract_issue_data_from_image
from services.tfl_service import get_tfl_delay_factor
from services.datastore_service import get_population_density
from services.scoring_service import calculate_priority_score
from services.agent_service import run as run_agent
```

The endpoint body must wrap `run_agent` in a try/except to surface model failures as `503`:

```python
@router.post("/analyse-report")
async def analyse_report(
    image: UploadFile = File(...),
    text_description: Optional[str] = Form(None),
):
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Image file is empty")

    try:
        issue = await run_agent(image_bytes, text_description)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Model unavailable: {exc}") from exc

    return {"status": "success", "issue": issue}
```

Add this test to `tests/test_reports_analyse.py` as well:

```python
def test_analyse_report_returns_503_when_model_unavailable():
    with patch("routers.reports.run_agent", new=AsyncMock(side_effect=RuntimeError("connection refused"))):
        response = client.post(
            "/analyse-report",
            files={"image": ("test.jpg", b"fake_jpeg_data", "image/jpeg")},
        )
    assert response.status_code == 503
    assert "connection refused" in response.json()["detail"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_reports_analyse.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add routers/reports.py tests/test_reports_analyse.py
git commit -m "✨feat: add POST /analyse-report endpoint"
```

---

## Task 8: Create .env.example and smoke test

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Write .env.example**

```bash
# Local model via Ollama (default)
LITELLM_MODEL=ollama/llava
LITELLM_API_BASE=http://localhost:11434

# Nebius model (comment out above and use these for Nebius)
# LITELLM_MODEL=nebius/Qwen/Qwen2.5-VL-72B-Instruct
# LITELLM_API_BASE=https://api.studio.nebius.com/v1
# LITELLM_API_KEY=your-nebius-api-key-here
```

- [ ] **Step 2: Start the server**

```bash
source .venv/bin/activate
uvicorn main:app --reload
```

Expected: server starts on `http://localhost:8000`.

- [ ] **Step 3: Check the new endpoint appears in docs**

Open `http://localhost:8000/docs` and verify `POST /analyse-report` is listed alongside `POST /submit-report`.

- [ ] **Step 4: Test with a real image (requires a model running)**

```bash
curl -X POST http://localhost:8000/analyse-report \
  -F "image=@/path/to/test_image.jpg" \
  -F "text_description=There is a large pothole near the crossing"
```

Expected (with a real model running):
```json
{
  "status": "success",
  "issue": {
    "issue_type": "pothole",
    "severity": 4,
    "location": "Camden",
    "description": "...",
    "confidence": 0.87,
    "raw_label": null
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add .env.example
git commit -m "📝doc: add .env.example for model configuration"
```
