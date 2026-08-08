from typing import Any
from urllib.parse import urlparse

import httpx

from app.tools.base import BaseTool


class APICallTool(BaseTool):
    """
    Call an explicitly allowlisted external API.

    Only HTTPS requests are allowed.
    """

    name = "api_call"

    description = (
        "Call an allowlisted external HTTP API and return "
        "the response."
    )

    allowed_specialists = [
        "research",
        "data_analysis",
        "code_execution",
    ]

    def __init__(
        self,
        allowed_hosts: set[str],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.allowed_hosts = {
            host.lower()
            for host in allowed_hosts
        }

        self._client = client
        self._owns_client = client is None

    def _validate_url(
        self,
        url: str,
    ) -> None:

        parsed = urlparse(url)

        if parsed.scheme != "https":
            raise ValueError(
                "Only HTTPS API calls are allowed."
            )

        if not parsed.hostname:
            raise ValueError(
                "API URL must contain a hostname."
            )

        hostname = parsed.hostname.lower()

        if hostname not in self.allowed_hosts:
            raise PermissionError(
                f"API host '{hostname}' is not allowlisted."
            )

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        url = arguments.get(
            "url"
        )

        if not isinstance(
            url,
            str,
        ) or not url.strip():
            raise ValueError(
                "The 'url' argument is required."
            )

        self._validate_url(url)

        method = arguments.get(
            "method",
            "GET",
        )

        if not isinstance(
            method,
            str,
        ):
            raise ValueError(
                "method must be a string."
            )

        method = method.upper()

        if method not in {
            "GET",
            "POST",
        }:
            raise ValueError(
                "Only GET and POST requests are supported."
            )

        headers = arguments.get(
            "headers",
            {},
        )

        if not isinstance(
            headers,
            dict,
        ):
            raise ValueError(
                "headers must be an object."
            )

        body = arguments.get(
            "body"
        )

        client = self._client

        if client is None:
            client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=False,
            )

        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=body,
            )

            content_type = response.headers.get(
                "content-type",
                "",
            )

            if "application/json" in content_type:
                response_body = response.json()
            else:
                response_body = response.text

            return {
                "status_code": response.status_code,
                "headers": dict(
                    response.headers
                ),
                "body": response_body,
            }

        finally:
            if self._owns_client:
                await client.aclose()