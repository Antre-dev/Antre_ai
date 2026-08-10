import os
from tavily import TavilyClient


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
client = TavilyClient(api_key=TAVILY_API_KEY)


def search_web(query: str, max_results: int = 5):
    if not TAVILY_API_KEY:
        return {
            "success": False,
            "error": "TAVILY_API_KEY is not configured"
        }

    try:
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic"
        )

        results = []

        for item in response.get("results", []):
            results.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content")
            })

        return {
            "success": True,
            "query": query,
            "results": results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }