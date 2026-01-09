"""
Article Content Fetcher
Fetches full article content from URLs for better context.
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict
import re


def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    return text.strip()


def fetch_article_content(url: str, max_length: int = 3000) -> Dict[str, str]:
    """
    Fetch full article content from a URL.

    Args:
        url: The article URL
        max_length: Maximum content length to return

    Returns:
        Dict with title, content, and url
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script, style, nav, footer elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
            element.decompose()

        # Try to find the main article content
        article = None

        # Common article containers
        selectors = [
            'article',
            '[role="main"]',
            '.post-content',
            '.article-content',
            '.entry-content',
            '.content-body',
            'main',
            '.blog-post',
            '.post-body',
        ]

        for selector in selectors:
            article = soup.select_one(selector)
            if article:
                break

        # Fallback to body
        if not article:
            article = soup.body

        if not article:
            return {
                "title": "Could not fetch",
                "content": "Failed to extract article content",
                "url": url
            }

        # Get title
        title = ""
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            title = clean_text(title_tag.get_text())

        # Get paragraphs
        paragraphs = article.find_all(['p', 'h2', 'h3', 'li'])
        content_parts = []

        for p in paragraphs:
            text = clean_text(p.get_text())
            if len(text) > 30:  # Skip short fragments
                content_parts.append(text)

        content = '\n\n'.join(content_parts)

        # Truncate if too long
        if len(content) > max_length:
            content = content[:max_length] + "..."

        return {
            "title": title,
            "content": content,
            "url": url
        }

    except requests.exceptions.RequestException as e:
        return {
            "title": "Fetch error",
            "content": f"Could not fetch article: {str(e)}",
            "url": url
        }
    except Exception as e:
        return {
            "title": "Parse error",
            "content": f"Could not parse article: {str(e)}",
            "url": url
        }


def fetch_multiple_articles(urls: list, max_length_per_article: int = 2000) -> str:
    """
    Fetch content from multiple URLs and format for agent consumption.
    """
    output = ""

    for i, url in enumerate(urls, 1):
        print(f"  Fetching article {i}/{len(urls)}: {url[:50]}...")
        article = fetch_article_content(url, max_length_per_article)

        output += f"\n{'='*60}\n"
        output += f"ARTICLE {i}: {article['title']}\n"
        output += f"URL: {article['url']}\n"
        output += f"{'='*60}\n"
        output += f"{article['content']}\n"

    return output


if __name__ == "__main__":
    # Test
    test_urls = [
        "https://openai.com/index/tolan",
        "https://openai.com/index/introducing-chatgpt-health",
    ]

    for url in test_urls:
        print(f"\nFetching: {url}")
        result = fetch_article_content(url)
        print(f"Title: {result['title']}")
        print(f"Content preview: {result['content'][:500]}...")
