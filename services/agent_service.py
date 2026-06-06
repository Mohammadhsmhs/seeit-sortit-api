import base64
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode

from config import get_llm
from services.agent_tools import get_issue_taxonomy, validate_location

logger = logging.getLogger(__name__)

TOOLS = [get_issue_taxonomy, validate_location]

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

_DEFAULT_RESULT: dict = {
    "issue_type": "other",
    "severity": 1,
    "location": "Unknown",
    "description": "Agent could not produce a structured result.",
    "confidence": 0.0,
    "raw_label": None,
}


class AgentState(MessagesState):
    issue_report: dict | None


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
                logger.error("Agent returned invalid JSON: %s", content[:200])
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


import threading

_graph = None
_graph_lock = threading.Lock()


def _get_graph():
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                _graph = _build_graph()
    return _graph


async def run(image_bytes: bytes, text_description: str | None = None) -> dict:
    """Run the issue-identification agent on an uploaded image.

    Args:
        image_bytes: Raw bytes of the uploaded image. Must be JPEG format.
        text_description: Optional free-text description from the citizen.

    Returns:
        A dict with keys: issue_type, severity, location, description,
        confidence, raw_label. Falls back to _DEFAULT_RESULT if the agent
        cannot produce a structured result.
    """
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
    issue_report = result.get("issue_report")
    return issue_report if issue_report is not None else dict(_DEFAULT_RESULT)
