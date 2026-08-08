from typing import Any

from jsonschema import ValidationError
from jsonschema import validate


class ToolSchemaValidationError(ValueError):
    """
    Raised when tool input or output violates its declared schema.
    """


def validate_tool_input(
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    """
    Validate tool arguments against the declared JSON schema.
    """

    if not schema:
        return

    try:
        validate(
            instance=arguments,
            schema=schema,
        )
    except ValidationError as exc:
        raise ToolSchemaValidationError(
            f"Tool input validation failed: {exc.message}"
        ) from exc


def validate_tool_output(
    schema: dict[str, Any],
    result: Any,
) -> None:
    """
    Validate tool output against the declared JSON schema.
    """

    if not schema:
        return

    try:
        validate(
            instance=result,
            schema=schema,
        )
    except ValidationError as exc:
        raise ToolSchemaValidationError(
            f"Tool output validation failed: {exc.message}"
        ) from exc