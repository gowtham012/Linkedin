#!/usr/bin/env python3
"""
OpenAI Agents SDK - LinkedIn Auto-Poster
This creates an agent that can be triggered via API or scheduled.
"""

import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.tools.rss_fetcher import fetch_rss_feeds
from src.tools.gnews_fetcher import fetch_gnews
from src.tools.linkedin_poster import post_to_linkedin
from src.tools.article_fetcher import fetch_article_content
from src.agents.prompts import CONTENT_WRITER_PROMPT, NEWS_CURATOR_PROMPT

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def fetch_and_format_news(hours_back=48):
    """Fetch news from all sources and format for agent."""
    rss_articles = fetch_rss_feeds(hours_back=hours_back)
    gnews_articles = fetch_gnews()
    all_articles = rss_articles + gnews_articles

    if not all_articles:
        return None, []

    text = f"Found {len(all_articles)} articles:\n\n"
    for i, article in enumerate(all_articles, 1):
        text += f"--- Article {i} ---\n"
        text += f"Source: {article['source']}\n"
        text += f"Title: {article['title']}\n"
        text += f"URL: {article['url']}\n"
        text += f"Summary: {article['summary'][:800]}\n\n"

    return text, all_articles


def curate_articles(articles_text):
    """Use AI to select best articles."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Select the most interesting AI news for developers."},
            {"role": "user", "content": NEWS_CURATOR_PROMPT.format(articles=articles_text)}
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content


def fetch_full_content(curated_text):
    """Fetch full article content from URLs."""
    import re
    urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', curated_text)[:4]

    full_content = curated_text + "\n\nFULL ARTICLE CONTENT:\n"
    for url in urls:
        clean_url = url.rstrip(')')
        article = fetch_article_content(clean_url, 2000)
        full_content += f"\n=== {article['title']} ===\n{article['content'][:2000]}\n"

    return full_content


def generate_human_post(content):
    """Generate human-like LinkedIn post."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Write like a real human, not an AI. Be casual, use natural language."},
            {"role": "user", "content": CONTENT_WRITER_PROMPT.format(curated_articles=content)}
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content


def run_workflow(hours_back=48, post_to_linkedin_flag=False):
    """Run the complete workflow."""
    print("=" * 50)
    print("LINKEDIN AI AUTO-POSTER")
    print("=" * 50)

    # Step 1: Fetch news
    print("\n1. Fetching news...")
    articles_text, all_articles = fetch_and_format_news(hours_back)
    if not articles_text:
        print("No articles found.")
        return None
    print(f"   Found {len(all_articles)} articles")

    # Step 2: Curate
    print("\n2. Curating best articles...")
    curated = curate_articles(articles_text)
    print("   Done")

    # Step 3: Fetch full content
    print("\n3. Fetching full article content...")
    full_content = fetch_full_content(curated)
    print("   Done")

    # Step 4: Generate post
    print("\n4. Generating human-like post...")
    post = generate_human_post(full_content)
    print("   Done")

    print("\n" + "=" * 50)
    print("GENERATED POST:")
    print("=" * 50)
    print(post)
    print("=" * 50)

    # Step 5: Post to LinkedIn (optional)
    if post_to_linkedin_flag:
        print("\n5. Posting to LinkedIn...")
        result = post_to_linkedin(post)
        if result.get('success'):
            print("   Posted successfully!")
        else:
            print(f"   Failed: {result.get('error')}")
        return {"post": post, "linkedin_result": result}

    return {"post": post}


# OpenAI Agents SDK Assistant Definition
ASSISTANT_INSTRUCTIONS = """You are a LinkedIn content assistant that helps create engaging, human-like posts about AI news.

When asked to create a post:
1. Use the generate_post function to create content
2. Review the generated post
3. If the user approves, use post_to_linkedin to publish

Always write in a casual, conversational tone. Never sound like a corporate press release."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_post",
            "description": "Generate a human-like LinkedIn post about recent AI news",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "Hours back to look for news",
                        "default": 48
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "post_to_linkedin",
            "description": "Post content to LinkedIn",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The post content to publish"
                    }
                },
                "required": ["content"]
            }
        }
    }
]


def create_assistant():
    """Create an OpenAI Assistant for LinkedIn posting."""
    assistant = client.beta.assistants.create(
        name="LinkedIn AI News Poster",
        instructions=ASSISTANT_INSTRUCTIONS,
        model="gpt-4o",
        tools=TOOLS
    )
    print(f"Assistant created: {assistant.id}")
    return assistant


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--post", action="store_true", help="Post to LinkedIn")
    parser.add_argument("--hours", type=int, default=48, help="Hours back")
    parser.add_argument("--create-assistant", action="store_true", help="Create OpenAI Assistant")

    args = parser.parse_args()

    if args.create_assistant:
        create_assistant()
    else:
        run_workflow(hours_back=args.hours, post_to_linkedin_flag=args.post)
