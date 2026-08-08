from mcp.server import MCPServer


mcp = MCPServer(
    "AgentFlow Test Server"
)


@mcp.tool()
def get_weather(
    city: str,
) -> dict:
    """
    Return test weather data.
    """

    return {
        "city": city,
        "temperature": 22,
    }


if __name__ == "__main__":
    mcp.run(
        transport="stdio"
    )