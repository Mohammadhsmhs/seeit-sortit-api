from unittest.mock import AsyncMock, MagicMock, patch

from services.agent_service import _DEFAULT_RESULT, run

MOCK_ISSUE = {
    "issue_type": "pothole",
    "severity": 4,
    "location": "Camden",
    "description": "Large pothole on residential street, approximately 30cm wide.",
    "confidence": 0.92,
    "raw_label": None,
}


async def test_run_returns_issue_report_from_graph() -> None:
    mock_result = {"messages": [], "issue_report": MOCK_ISSUE}

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_get_graph.return_value = mock_graph

        result = await run(b"fake_jpeg_bytes", "There is a pothole")

    assert result["issue_type"] == "pothole"
    assert result["severity"] == 4
    assert result["location"] == "Camden"
    assert result["confidence"] == 0.92
    assert result["raw_label"] is None


async def test_run_returns_default_when_issue_report_is_none() -> None:
    mock_result = {"messages": [], "issue_report": None}

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_get_graph.return_value = mock_graph

        result = await run(b"fake_jpeg_bytes")

    assert result == dict(_DEFAULT_RESULT)


async def test_run_includes_image_in_message() -> None:
    captured: dict = {}

    async def capturing_ainvoke(state: dict) -> dict:
        captured["messages"] = state["messages"]
        return {"messages": state["messages"], "issue_report": MOCK_ISSUE}

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = capturing_ainvoke
        mock_get_graph.return_value = mock_graph

        await run(b"fake_jpeg_bytes", "big pothole near the park")

    human_msg = captured["messages"][-1]  # [SystemMessage, HumanMessage]
    content = human_msg.content
    assert any(c.get("type") == "image_url" for c in content)
    assert any(c.get("type") == "text" and "pothole" in c.get("text", "") for c in content)


async def test_run_omits_text_when_not_provided() -> None:
    captured: dict = {}

    async def capturing_ainvoke(state: dict) -> dict:
        captured["messages"] = state["messages"]
        return {"messages": state["messages"], "issue_report": MOCK_ISSUE}

    with patch("services.agent_service._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = capturing_ainvoke
        mock_get_graph.return_value = mock_graph

        await run(b"fake_jpeg_bytes")

    human_msg = captured["messages"][-1]
    content = human_msg.content
    assert len(content) == 1
    assert content[0]["type"] == "image_url"
