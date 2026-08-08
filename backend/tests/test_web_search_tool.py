import httpx
import pytest

from app.tools.web_search import WebSearchTool


@pytest.mark.asyncio
async def test_web_search_tool_returns_results():

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        assert request.url.params["q"] == (
            "agent orchestration"
        )

        return httpx.Response(
            200,
            json={
                "Heading": "Agent Orchestration",
                "AbstractText": (
                    "Agent orchestration coordinates "
                    "multiple agents."
                ),
                "AbstractURL": (
                    "https://example.com/agents"
                ),
                "RelatedTopics": [],
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:

        tool = WebSearchTool(
            client=client
        )

        result = await tool.execute(
            {
                "query": "agent orchestration",
                "max_results": 5,
            }
        )

    assert (
        result["query"]
        == "agent orchestration"
    )

    assert len(
        result["results"]
    ) == 1


@pytest.mark.asyncio
async def test_web_search_requires_query():

    tool = WebSearchTool(
        client=httpx.AsyncClient()
    )

    try:
        with pytest.raises(ValueError):
            await tool.execute({})
    finally:
        await tool._client.aclose()