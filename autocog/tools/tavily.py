import os
import sys
from tavily import TavilyClient
from typing import Any


def get_client() -> TavilyClient:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable not found")

    return TavilyClient(api_key=api_key)


def web_search(
    query: str,
    topic: str = "general",
    search_depth: str = "basic",
    max_results: int = 5,
    include_answer: bool = False,
    include_raw_content: bool = False,
    include_images: bool = False,
    days: int | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Perform a search using the Tavily API.

    Args:
        query: Search query string
        topic: Search topic - "general" or "news"
        search_depth: Depth of search - "basic" or "advanced"
        max_results: Maximum number of results to return (1-20)
        include_answer: Include AI-generated answer in response
        include_raw_content: Include raw content in response
        include_images: Include images in response
        days: For news topic, number of days back to search
        include_domains: List of domains to include in search
        exclude_domains: List of domains to exclude from search
        timeout: Timeout in seconds for the request

    Returns:
        Dictionary containing search results
    """
    try:
        client = get_client()

        response = client.search(
            query=query,
            topic=topic,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
            include_images=include_images,
            days=days,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            timeout=timeout,
        )

        return response

    except Exception as e:
        print(f"Error in Tavily search: {e}", file=sys.stderr)
        return {"error": str(e), "results": []}


def web_extract(
    urls: list[str],
    extract_depth: str = "basic",
    include_images: bool = False,
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Extract content from URLs using the Tavily API.

    Args:
        urls: List of URLs to extract content from
        extract_depth: Depth of extraction - "basic" or "advanced"
        include_images: Include images in response
        timeout: Timeout in seconds for the request

    Returns:
        Dictionary containing extracted content
    """
    try:
        client = get_client()

        response = client.extract(
            urls=urls,
            extract_depth=extract_depth,
            include_images=include_images,
            timeout=timeout,
        )

        return response

    except Exception as e:
        print(f"Error in Tavily extract: {e}", file=sys.stderr)
        return {"error": str(e), "results": [], "failed_results": urls}
