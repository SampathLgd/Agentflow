import httpx
import pytest

from app.tools.api_call import APICallTool


@pytest.mark.asyncio
async def test_api_call_tool_get():

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        assert request.method == "GET"

        return httpx.Response(
            200,
            json={
                "status": "ok",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:

        tool = APICallTool(
            allowed_hosts={
                "api.example.com",
            },
            client=client,
        )

        result = await tool.execute(
            {
                "url": (
                    "https://api.example.com/status"
                ),
                "method": "GET",
            }
        )

    assert result["status_code"] == 200

    assert result["body"] == {
        "status": "ok",
    }


@pytest.mark.asyncio
async def test_api_call_rejects_non_allowlisted_host():

    tool = APICallTool(
        allowed_hosts={
            "api.example.com",
        },
        client=httpx.AsyncClient(),
    )

    try:
        with pytest.raises(
            PermissionError
        ):
            await tool.execute(
                {
                    "url": (
                        "https://evil.example.com/data"
                    ),
                }
            )
    finally:
        await tool._client.aclose()


@pytest.mark.asyncio
async def test_api_call_requires_https():

    tool = APICallTool(
        allowed_hosts={
            "api.example.com",
        },
        client=httpx.AsyncClient(),
    )

    try:
        with pytest.raises(
            ValueError
        ):
            await tool.execute(
                {
                    "url": (
                        "http://api.example.com/data"
                    ),
                }
            )
    finally:
        await tool._client.aclose()