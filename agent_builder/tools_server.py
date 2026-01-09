#!/usr/bin/env python3
"""
Tools Server for OpenAI Agent Builder
Deploy this server to provide tools that Agent Builder can call.
"""

import os
import sys
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

# Add parent directory to path for local and deployed environments
parent_dir = os.path.join(os.path.dirname(__file__), '..')
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Also add the root directory for Render deployment
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.tools.rss_fetcher import fetch_rss_feeds
from src.tools.gnews_fetcher import fetch_gnews
from src.tools.linkedin_poster import post_to_linkedin, validate_linkedin_token
from src.tools.article_fetcher import fetch_article_content
from src.agents.prompts import CONTENT_WRITER_PROMPT, NEWS_CURATOR_PROMPT

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def call_openai(prompt: str, system_message: str = None) -> str:
    """Call OpenAI API."""
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=4000,
    )
    return response.choices[0].message.content


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route('/tools/fetch_ai_news', methods=['POST'])
def fetch_ai_news():
    """Fetch AI news from RSS feeds and GNews API."""
    try:
        data = request.json or {}
        hours_back = data.get('hours_back', 48)

        rss_articles = fetch_rss_feeds(hours_back=hours_back)
        gnews_articles = fetch_gnews()
        all_articles = rss_articles + gnews_articles

        formatted = []
        for article in all_articles:
            formatted.append({
                "title": article["title"],
                "summary": article["summary"][:1000],
                "url": article["url"],
                "date": article["date"],
                "source": article["source"]
            })

        return jsonify({
            "success": True,
            "article_count": len(formatted),
            "articles": formatted
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/tools/generate_post', methods=['POST'])
def generate_post():
    """
    Full workflow: Fetch news -> Curate -> Fetch full content -> Generate human-like post.
    """
    try:
        data = request.json or {}
        hours_back = data.get('hours_back', 48)

        # Step 1: Fetch all articles
        rss_articles = fetch_rss_feeds(hours_back=hours_back)
        gnews_articles = fetch_gnews()
        all_articles = rss_articles + gnews_articles

        if not all_articles:
            return jsonify({"success": False, "error": "No articles found"})

        # Format articles for curation
        articles_text = f"Found {len(all_articles)} articles:\n\n"
        for i, article in enumerate(all_articles, 1):
            articles_text += f"--- Article {i} ---\n"
            articles_text += f"Source: {article['source']}\n"
            articles_text += f"Title: {article['title']}\n"
            articles_text += f"URL: {article['url']}\n"
            articles_text += f"Summary: {article['summary'][:800]}\n\n"

        # Step 2: Curate best articles
        curator_prompt = NEWS_CURATOR_PROMPT.format(articles=articles_text)
        curated = call_openai(curator_prompt, "Select the most interesting AI news for developers.")

        # Step 3: Fetch full content from curated URLs
        import re
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', curated)[:4]

        full_content = curated + "\n\nFULL ARTICLE CONTENT:\n"
        for url in urls:
            article = fetch_article_content(url.rstrip(')'), 2000)
            full_content += f"\n=== {article['title']} ===\n{article['content'][:2000]}\n"

        # Step 4: Generate human-like post
        writer_prompt = CONTENT_WRITER_PROMPT.format(curated_articles=full_content)
        post_content = call_openai(writer_prompt, "Write like a real human, not an AI.")

        return jsonify({
            "success": True,
            "post": post_content,
            "articles_used": len(urls)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/tools/post_to_linkedin', methods=['POST'])
def linkedin_post():
    """Post content to LinkedIn."""
    try:
        data = request.json

        if not data or 'content' not in data:
            return jsonify({"success": False, "error": "Missing 'content' field"}), 400

        content = data['content']

        validation = validate_linkedin_token()
        if not validation.get('valid'):
            return jsonify({
                "success": False,
                "error": "LinkedIn token is invalid or expired"
            }), 401

        result = post_to_linkedin(content)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/tools/full_workflow', methods=['POST'])
def full_workflow():
    """
    Complete workflow: Generate post and optionally post to LinkedIn.
    """
    try:
        data = request.json or {}
        hours_back = data.get('hours_back', 48)
        auto_post = data.get('auto_post', False)

        # Generate post
        from flask import current_app
        with current_app.test_request_context(json={'hours_back': hours_back}):
            gen_response = generate_post()
            gen_data = gen_response.get_json()

        if not gen_data.get('success'):
            return jsonify(gen_data)

        post_content = gen_data['post']

        # Auto-post if requested
        if auto_post:
            validation = validate_linkedin_token()
            if not validation.get('valid'):
                return jsonify({
                    "success": False,
                    "post": post_content,
                    "error": "LinkedIn token invalid - post generated but not published"
                })

            result = post_to_linkedin(post_content)
            return jsonify({
                "success": result.get('success', False),
                "post": post_content,
                "linkedin_result": result
            })

        return jsonify({
            "success": True,
            "post": post_content,
            "message": "Post generated. Set auto_post=true to publish."
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/tools/validate_linkedin', methods=['GET'])
def validate_linkedin():
    """Validate LinkedIn access token."""
    result = validate_linkedin_token()
    return jsonify(result)


# OpenAI Function Definitions
TOOL_DEFINITIONS = [
    {
        "name": "generate_post",
        "description": "Generate a human-like LinkedIn post about recent AI news. Fetches news, curates top stories, and writes in a natural conversational tone.",
        "parameters": {
            "type": "object",
            "properties": {
                "hours_back": {
                    "type": "integer",
                    "description": "Hours back to look for news (default 48)",
                    "default": 48
                }
            }
        }
    },
    {
        "name": "post_to_linkedin",
        "description": "Post content to LinkedIn",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The post content"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "full_workflow",
        "description": "Complete workflow: generate AI news post and optionally publish to LinkedIn",
        "parameters": {
            "type": "object",
            "properties": {
                "hours_back": {"type": "integer", "default": 48},
                "auto_post": {"type": "boolean", "default": False}
            }
        }
    }
]


@app.route('/openai/tools', methods=['GET'])
def get_tool_definitions():
    """Get OpenAI function definitions."""
    return jsonify(TOOL_DEFINITIONS)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n{'='*60}")
    print("  LINKEDIN AI AUTO-POSTER - TOOLS SERVER")
    print(f"{'='*60}")
    print(f"\nServer: http://localhost:{port}")
    print(f"\nEndpoints:")
    print(f"  GET  /health                - Health check")
    print(f"  POST /tools/generate_post   - Generate LinkedIn post")
    print(f"  POST /tools/post_to_linkedin - Post to LinkedIn")
    print(f"  POST /tools/full_workflow   - Full workflow")
    print(f"  GET  /openai/tools          - Tool definitions")
    print(f"\n{'='*60}\n")

    app.run(host='0.0.0.0', port=port, debug=True)
