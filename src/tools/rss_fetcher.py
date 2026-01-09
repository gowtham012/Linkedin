"""
RSS Feed Fetcher Tool
Fetches latest AI news from official company blogs via RSS feeds.
"""

import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any


RSS_FEEDS = {
    "OpenAI": "https://openai.com/blog/rss.xml",
    "Anthropic": "https://www.anthropic.com/news/rss",
    "Google AI": "https://blog.google/technology/ai/rss/",
    "DeepMind": "https://deepmind.google/blog/rss.xml",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "Meta AI": "https://ai.meta.com/blog/rss/",
    "Mistral AI": "https://mistral.ai/feed.xml",
}


def parse_date(entry: Dict) -> datetime:
    """Parse date from RSS entry, handling various formats."""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    return datetime.now()


def fetch_rss_feeds(hours_back: int = 48) -> List[Dict[str, Any]]:
    """
    Fetch articles from all RSS feeds within the specified time window.

    Args:
        hours_back: Number of hours to look back for articles (default 48)

    Returns:
        List of articles with title, summary, url, date, and source
    """
    articles = []
    cutoff_time = datetime.now() - timedelta(hours=hours_back)

    for source_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                pub_date = parse_date(entry)

                # Only include recent articles
                if pub_date >= cutoff_time:
                    article = {
                        "title": entry.get("title", "No title"),
                        "summary": entry.get("summary", entry.get("description", "No summary available")),
                        "url": entry.get("link", ""),
                        "date": pub_date.isoformat(),
                        "source": source_name,
                    }
                    articles.append(article)

        except Exception as e:
            print(f"Error fetching {source_name} RSS: {e}")
            continue

    # Sort by date (newest first)
    articles.sort(key=lambda x: x["date"], reverse=True)

    return articles


def fetch_rss_feeds_as_text(hours_back: int = 48) -> str:
    """
    Fetch articles and return as formatted text for agent consumption.
    """
    articles = fetch_rss_feeds(hours_back)

    if not articles:
        return "No recent articles found in RSS feeds."

    output = f"Found {len(articles)} articles from RSS feeds:\n\n"

    for i, article in enumerate(articles, 1):
        output += f"--- Article {i} ---\n"
        output += f"Source: {article['source']}\n"
        output += f"Title: {article['title']}\n"
        output += f"Date: {article['date']}\n"
        output += f"URL: {article['url']}\n"
        output += f"Summary: {article['summary'][:500]}...\n\n"

    return output


if __name__ == "__main__":
    # Test the fetcher
    print("Fetching RSS feeds...")
    articles = fetch_rss_feeds(hours_back=168)  # Last 7 days for testing
    print(f"Found {len(articles)} articles")
    for article in articles[:5]:
        print(f"\n- {article['source']}: {article['title']}")
        print(f"  {article['url']}")
