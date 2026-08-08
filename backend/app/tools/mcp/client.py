from contextlib import AsyncExitStack
from typing import Any, Protocol

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient(Protocol):
    """
    Protocol used by AgentFlow's MCP tool adapter.
    """

    async def list_tools(
        self,
    ) -> list[Any]:
        ...

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        ...


class StdioMCPClient:
    """
    MCP client using the official MCP stdio transport.

    The MCP server runs as a child process.
    """

    def __init__(
        self,
        *,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env

        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(
        self,
    ):
        self._exit_stack = AsyncExitStack()

        await self._exit_stack.__aenter__()

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )

        read_stream, write_stream = (
            await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
        )

        self._session = (
            await self._exit_stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                )
            )
        )

        await self._session.initialize()

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        if self._exit_stack is not None:
            await self._exit_stack.__aexit__(
                exc_type,
                exc_value,
                traceback,
            )

        self._exit_stack = None
        self._session = None

    def _require_session(
        self,
    ) -> ClientSession:
        if self._session is None:
            raise RuntimeError(
                "MCP client is not connected. "
                "Use 'async with StdioMCPClient(...)'."
            )

        return self._session

    async def list_tools(
        self,
    ) -> list[dict[str, Any]]:
        session = self._require_session()

        result = await session.list_tools()

        tools: list[dict[str, Any]] = []

        for tool in result.tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": (
                        tool.description or ""
                    ),
                    "input_schema": (
                        tool.input_schema or {}
                    ),
                    "output_schema": (
                        getattr(
                            tool,
                            "output_schema",
                            {},
                        )
                        or {}
                    ),
                }
            )

        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        session = self._require_session()

        result = await session.call_tool(
            tool_name,
            arguments,
        )

        # MCP structured output.
        structured_content = getattr(
            result,
            "structured_content",
            None,
        )

        if structured_content is not None:
            return structured_content

        # Fall back to unstructured content.
        content = getattr(
            result,
            "content",
            None,
        )

        if content is not None:
            return content

        return result