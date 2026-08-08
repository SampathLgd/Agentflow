from app.schemas.execution import Specialist
from app.tools.definition import ToolDefinition
from app.tools.mcp.adapter import MCPToolAdapter
from app.tools.mcp.client import MCPClient
from app.tools.registry import ToolRegistry


async def register_mcp_tools(
    *,
    client: MCPClient,
    registry: ToolRegistry,
    allowed_specialists: frozenset[str] | None = None,
) -> list[str]:
    """
    Discover MCP tools and register them with AgentFlow.

    Authorization rules:

    1. If the MCP client provides a ToolDefinition, preserve
       its explicitly declared allowed_specialists.

    2. If the MCP client provides a raw dictionary, use the
       optional AgentFlow allowed_specialists restriction.

    3. If no restriction is supplied for a raw MCP definition,
       allow the registered AgentFlow specialists.
    """

    raw_tools = await client.list_tools()

    default_specialists = frozenset(
        specialist.value
        for specialist in Specialist
    )

    registered: list[str] = []

    for raw_tool in raw_tools:

        # ----------------------------------------------------
        # Existing ToolDefinition
        # ----------------------------------------------------

        if isinstance(
            raw_tool,
            ToolDefinition,
        ):
            definition = raw_tool

        # ----------------------------------------------------
        # Raw MCP dictionary
        # ----------------------------------------------------

        elif isinstance(
            raw_tool,
            dict,
        ):
            tool_specialists = raw_tool.get(
                "allowed_specialists"
            )

            if tool_specialists is None:
                tool_specialists = (
                    allowed_specialists
                    if allowed_specialists is not None
                    else default_specialists
                )

            definition = ToolDefinition(
                name=raw_tool["name"],
                description=raw_tool.get(
                    "description",
                    "",
                ),
                input_schema=raw_tool.get(
                    "input_schema",
                    {},
                ),
                output_schema=raw_tool.get(
                    "output_schema",
                    {},
                ),
                allowed_specialists=frozenset(
                    tool_specialists
                ),
            )

        else:
            raise TypeError(
                "MCP client returned an unsupported "
                f"tool definition type: "
                f"{type(raw_tool).__name__}"
            )

        # ----------------------------------------------------
        # Register through the normal AgentFlow registry.
        # ----------------------------------------------------

        adapter = MCPToolAdapter(
            client=client,
            definition=definition,
        )

        registry.register(
            adapter,
            definition,
        )

        registered.append(
            definition.name
        )

    return registered