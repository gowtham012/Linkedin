"""
GNews API Fetcher Tool
Fetches latest AI news from GNews API for broader coverage.
"""

import os
import requests
from datetime import datetime
from typing import List, Dict, Any


GNEWS_API_URL = "https://gnews.io/api/v4/search"

# AI-related search queries
SEARCH_QUERIES = [
    "artificial intelligence",
    "generative AI",
    "large language model",
    "OpenAI GPT",
    "Claude AI",
    "Gemini AI",
]


def fetch_gnews(api_key: str = None, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch AI-related articles from GNews API.

    Args:
        api_key: GNews API key (falls back to env var GNEWS_API_KEY)
        max_results: Maximum number of results per query

    Returns:
        List of articles with title, summary, url, date, and source
    """
    api_key = api_key or os.getenv("GNEWS_API_KEY")

    if not api_key:
        print("Warning: GNEWS_API_KEY not set. Skipping GNews fetch.")
        return []

    articles = []
    seen_urls = set()

    # Combined query for efficiency (saves API calls)
    combined_query = "artificial intelligence OR generative AI OR LLM"

    try:
        params = {
            "q": combined_query,
            "lang": "en",
            "max": max_results,
            "apikey": api_key,
            "sortby": "publishedAt",
        }

        response = requests.get(GNEWS_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        for item in data.get("articles", []):
            url = item.get("url", "")

            # Deduplicate by URL
            if url in seen_urls:
                continue
            seen_urls.add(url)

            article = {
                "title": item.get("title", "No title"),
                "summary": item.get("description", "No summary available"),
                "url": url,
                "date": item.get("publishedAt", datetime.now().isoformat()),
                "source": item.get("source", {}).get("name", "Unknown"),
            }
            articles.append(article)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching from GNews: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return articles


def fetch_gnews_as_text(api_key: str = None, max_results: int = 10) -> str:
    """
    Fetch articles and return as formatted text for agent consumption.
    """
    articles = fetch_gnews(api_key, max_results)

    if not articles:
        return "No articles found from GNews API."

    output = f"Found {len(articles)} articles from GNews:\n\n"

    for i, article in enumerate(articles, 1):
        output += f"--- Article {i} ---\n"
        output += f"Source: {article['source']}\n"
        output += f"Title: {article['title']}\n"
        output += f"Date: {article['date']}\n"
        output += f"URL: {article['url']}\n"
        output += f"Summary: {article['summary'][:500]}...\n\n"

    return output


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("Fetching from GNews API...")
    articles = fetch_gnews()
    print(f"Found {len(articles)} articles")
    for article in articles[:5]:
        print(f"\n- {article['source']}: {article['title']}")
        print(f"  {article['url']}")
