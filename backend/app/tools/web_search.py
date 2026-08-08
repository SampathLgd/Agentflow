from typing import Any

import httpx

from app.tools.base import BaseTool


class WebSearchTool(BaseTool):
    """
    Search the public web.

    Phase 1 uses DuckDuckGo's public Instant Answer endpoint so
    the tool can operate without introducing another API key.

    The HTTP client is injectable so tests do not require network
    access and the backend can later be replaced with a production
    search provider such as Tavily/Serper/etc.
    """

    name = "web_search"

    description = (
        "Search the public web and return relevant search results."
    )

    allowed_specialists = [
        "research",
    ]

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client
        self._owns_client = client is None

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        query = arguments.get("query")

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "The 'query' argument is required."
            )

        max_results = arguments.get(
            "max_results",
            5,
        )

        if not isinstance(max_results, int):
            raise ValueError(
                "max_results must be an integer."
            )

        if max_results < 1 or max_results > 10:
            raise ValueError(
                "max_results must be between 1 and 10."
            )

        client = self._client

        if client is None:
            client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
            )

        try:
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1",
                },
            )

            response.raise_for_status()

            data = response.json()

            results: list[dict[str, str]] = []

            abstract_text = data.get(
                "AbstractText",
                "",
            )

            abstract_url = data.get(
                "AbstractURL",
                "",
            )

            heading = data.get(
                "Heading",
                "",
            )

            if abstract_text:
                results.append(
                    {
                        "title": heading or query,
                        "url": abstract_url,
                        "snippet": abstract_text,
                    }
                )

            for topic in data.get(
                "RelatedTopics",
                []
            ):
                if len(results) >= max_results:
                    break

                if not isinstance(
                    topic,
                    dict,
                ):
                    continue

                text = topic.get(
                    "Text",
                    "",
                )

                url = topic.get(
                    "FirstURL",
                    "",
                )

                if text:
                    results.append(
                        {
                            "title": text[:120],
                            "url": url,
                            "snippet": text,
                        }
                    )

            return {
                "query": query,
                "results": results[:max_results],
            }

        finally:
            if self._owns_client:
                await client.aclose()