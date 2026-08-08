from app.tools.definition import ToolDefinition


WEB_SEARCH_DEFINITION = ToolDefinition(
    name="web_search",
    description=(
        "Search the public web and return relevant results."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": [
            "query",
        ],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
            },
            "results": {
                "type": "array",
            },
        },
        "required": [
            "query",
            "results",
        ],
        "additionalProperties": False,
    },
    allowed_specialists=frozenset({
        "research",
    }),
    rate_limit_per_minute=20,
)


DATABASE_QUERY_DEFINITION = ToolDefinition(
    name="database_query",
    description=(
        "Execute a read-only SQL query against the "
        "configured AgentFlow database."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
            },
            "parameters": {
                "type": "object",
            },
        },
        "required": [
            "query",
        ],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "columns": {
                "type": "array",
            },
            "rows": {
                "type": "array",
            },
            "row_count": {
                "type": "integer",
            },
        },
        "required": [
            "columns",
            "rows",
            "row_count",
        ],
        "additionalProperties": False,
    },
    allowed_specialists=frozenset({
        "research",
        "data_analysis",
    }),
    rate_limit_per_minute=30,
)


API_CALL_DEFINITION = ToolDefinition(
    name="api_call",
    description=(
        "Call an allowlisted external HTTPS API."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "format": "uri",
            },
            "method": {
                "type": "string",
                "enum": [
                    "GET",
                    "POST",
                ],
            },
            "headers": {
                "type": "object",
            },
            "body": {},
        },
        "required": [
            "url",
        ],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "status_code": {
                "type": "integer",
            },
            "headers": {
                "type": "object",
            },
            "body": {},
        },
        "required": [
            "status_code",
            "headers",
            "body",
        ],
        "additionalProperties": False,
    },
    allowed_specialists=frozenset({
        "research",
        "data_analysis",
        "code_execution",
    }),
    rate_limit_per_minute=30,
)