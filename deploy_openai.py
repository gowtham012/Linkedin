#!/usr/bin/env python3
"""
Deploy LinkedIn Auto-Poster to OpenAI Assistants API
Everything runs through OpenAI - no external hosting needed.
"""

import os
import sys
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tools.rss_fetcher import fetch_rss_feeds
from tools.gnews_fetcher import fetch_gnews
from tools.linkedin_poster import post_to_linkedin
from tools.article_fetcher import fetch_article_content

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Assistant configuration
ASSISTANT_NAME = "LinkedIn AI News Poster"
ASSISTANT_MODEL = "gpt-4o"

ASSISTANT_INSTRUCTIONS = """You are a LinkedIn content creator who writes about AI news in a casual, human way.

Your job:
1. When given news articles, pick the 2-3 most interesting ones for developers
2. Write a LinkedIn post that sounds like a real person typing their thoughts - NOT a news summary

Writing style:
- Start mid-thought, like "So... Google just did something interesting"
- Use casual language: "kinda", "honestly", "idk", "tbh"
- Short paragraphs, lots of line breaks
- Share YOUR reactions and what YOU'd build
- Don't list items as "1. First 2. Second" - let thoughts flow naturally
- End with a real question you want answered

NEVER use these words: groundbreaking, revolutionary, game-changer, cutting-edge, dive in, leverage, robust, seamless, comprehensive, innovative, transform, empower, thrilled, excited to share

Example tone:
"So... Google's turning Gmail into more of a personal assistant. It's kinda wild to think about.

The 'Help Me Write' feature is interesting - could it actually mimic how I write? Still skeptical but gonna try it.

Also been looking at NVIDIA's Reachy Mini. Having a little AI robot buddy sounds like sci-fi but here we are...

Anyone actually built something with these yet? Curious what the experience is like.

links at bottom
#ai #tech"

When you receive articles, write a post in this style. Include links at the bottom."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_ai_news",
            "description": "Fetch latest AI news from RSS feeds and news APIs",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "Hours back to search (default 48)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_full_article",
            "description": "Fetch full content from an article URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The article URL to fetch"
                    }
                },
                "required": ["url"]
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
                        "description": "The post content"
                    }
                },
                "required": ["content"]
            }
        }
    }
]


def handle_tool_call(tool_name, arguments):
    """Handle tool calls from the assistant."""

    if tool_name == "fetch_ai_news":
        hours_back = arguments.get("hours_back", 48)

        rss = fetch_rss_feeds(hours_back=hours_back)
        gnews = fetch_gnews()
        all_articles = rss + gnews

        # Format for assistant
        result = []
        for a in all_articles[:15]:  # Limit to 15
            result.append({
                "title": a["title"],
                "source": a["source"],
                "url": a["url"],
                "summary": a["summary"][:500]
            })

        return json.dumps({"articles": result, "count": len(result)})

    elif tool_name == "fetch_full_article":
        url = arguments.get("url", "")
        article = fetch_article_content(url, max_length=2000)
        return json.dumps(article)

    elif tool_name == "post_to_linkedin":
        content = arguments.get("content", "")
        result = post_to_linkedin(content)
        return json.dumps(result)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def create_assistant():
    """Create the OpenAI Assistant."""

    # Check if assistant already exists
    assistants = client.beta.assistants.list(limit=100)
    for a in assistants.data:
        if a.name == ASSISTANT_NAME:
            print(f"Assistant already exists: {a.id}")
            return a

    # Create new assistant
    assistant = client.beta.assistants.create(
        name=ASSISTANT_NAME,
        instructions=ASSISTANT_INSTRUCTIONS,
        model=ASSISTANT_MODEL,
        tools=TOOLS
    )

    print(f"Created assistant: {assistant.id}")

    # Save assistant ID
    with open(".assistant_id", "w") as f:
        f.write(assistant.id)

    return assistant


def get_assistant():
    """Get existing assistant or create new one."""

    # Try to load saved ID
    if os.path.exists(".assistant_id"):
        with open(".assistant_id", "r") as f:
            assistant_id = f.read().strip()
        try:
            return client.beta.assistants.retrieve(assistant_id)
        except:
            pass

    return create_assistant()


def run_assistant(auto_post=False):
    """Run the assistant to generate and optionally post."""

    assistant = get_assistant()
    print(f"Using assistant: {assistant.id}")

    # Create thread
    thread = client.beta.threads.create()

    # Initial message
    if auto_post:
        user_message = "Fetch the latest AI news, write a casual LinkedIn post about the most interesting stuff, and post it to LinkedIn."
    else:
        user_message = "Fetch the latest AI news and write a casual LinkedIn post about the most interesting stuff. Don't post yet - just show me the draft."

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )

    # Run assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    print("Running assistant...")

    # Poll for completion
    while True:
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )

        if run.status == "completed":
            break

        elif run.status == "requires_action":
            # Handle tool calls
            tool_outputs = []

            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                print(f"  Calling: {tool_call.function.name}")

                args = json.loads(tool_call.function.arguments)
                result = handle_tool_call(tool_call.function.name, args)

                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": result
                })

            # Submit results
            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )

        elif run.status in ["failed", "cancelled", "expired"]:
            print(f"Run failed: {run.status}")
            if run.last_error:
                print(f"Error: {run.last_error}")
            return None

        time.sleep(1)

    # Get final message
    messages = client.beta.threads.messages.list(thread_id=thread.id)

    for msg in messages.data:
        if msg.role == "assistant":
            for content in msg.content:
                if content.type == "text":
                    print("\n" + "="*50)
                    print("ASSISTANT RESPONSE:")
                    print("="*50)
                    print(content.text.value)
                    return content.text.value

    return None


def delete_assistant():
    """Delete the assistant."""
    if os.path.exists(".assistant_id"):
        with open(".assistant_id", "r") as f:
            assistant_id = f.read().strip()
        try:
            client.beta.assistants.delete(assistant_id)
            os.remove(".assistant_id")
            print(f"Deleted assistant: {assistant_id}")
        except Exception as e:
            print(f"Error deleting: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LinkedIn AI Auto-Poster on OpenAI")
    parser.add_argument("--create", action="store_true", help="Create the assistant")
    parser.add_argument("--run", action="store_true", help="Run and generate post")
    parser.add_argument("--post", action="store_true", help="Run and post to LinkedIn")
    parser.add_argument("--delete", action="store_true", help="Delete the assistant")
    parser.add_argument("--info", action="store_true", help="Show assistant info")

    args = parser.parse_args()

    if args.create:
        assistant = create_assistant()
        print(f"\nAssistant ID: {assistant.id}")
        print(f"Name: {assistant.name}")
        print(f"Model: {assistant.model}")
        print("\nTo run: python deploy_openai.py --run")
        print("To post: python deploy_openai.py --post")

    elif args.run:
        run_assistant(auto_post=False)

    elif args.post:
        run_assistant(auto_post=True)

    elif args.delete:
        delete_assistant()

    elif args.info:
        assistant = get_assistant()
        print(f"Assistant ID: {assistant.id}")
        print(f"Name: {assistant.name}")
        print(f"Model: {assistant.model}")
        print(f"Tools: {[t.function.name for t in assistant.tools if t.type == 'function']}")

    else:
        parser.print_help()
