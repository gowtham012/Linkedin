#!/usr/bin/env python3
"""
LinkedIn AI Auto-Poster - Main Workflow
Orchestrates the complete workflow: fetch news -> curate -> write -> verify -> post
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tools.rss_fetcher import fetch_rss_feeds, fetch_rss_feeds_as_text
from tools.gnews_fetcher import fetch_gnews, fetch_gnews_as_text
from tools.linkedin_poster import post_to_linkedin, validate_linkedin_token
from tools.article_fetcher import fetch_article_content, fetch_multiple_articles
from agents.prompts import get_curator_prompt, get_writer_prompt, get_verifier_prompt


# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def call_agent(prompt: str, system_message: str = None, model: str = "gpt-4o") -> str:
    """
    Call OpenAI API with the given prompt.
    """
    messages = []

    if system_message:
        messages.append({"role": "system", "content": system_message})

    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=4000,
    )

    return response.choices[0].message.content


def step_1_fetch_news(hours_back: int = 48) -> str:
    """Step 1: Fetch news from all sources."""
    print("\n" + "=" * 50)
    print("STEP 1: Fetching news from sources...")
    print("=" * 50)

    # Fetch from RSS feeds
    print("\nFetching RSS feeds...")
    rss_articles = fetch_rss_feeds(hours_back=hours_back)
    print(f"  Found {len(rss_articles)} articles from RSS")

    # Fetch from GNews
    print("\nFetching from GNews API...")
    gnews_articles = fetch_gnews()
    print(f"  Found {len(gnews_articles)} articles from GNews")

    # Combine all articles
    all_articles = rss_articles + gnews_articles
    print(f"\nTotal articles: {len(all_articles)}")

    if not all_articles:
        return None

    # Format for agent consumption
    output = f"Found {len(all_articles)} articles:\n\n"
    for i, article in enumerate(all_articles, 1):
        output += f"--- Article {i} ---\n"
        output += f"Source: {article['source']}\n"
        output += f"Title: {article['title']}\n"
        output += f"Date: {article['date']}\n"
        output += f"URL: {article['url']}\n"
        output += f"Summary: {article['summary'][:1000]}\n\n"

    return output


def step_2_curate_news(articles_text: str) -> str:
    """Step 2: Use AI to curate the best articles."""
    print("\n" + "=" * 50)
    print("STEP 2: Curating news with AI...")
    print("=" * 50)

    prompt = get_curator_prompt(articles_text)

    system_message = """You are an expert AI news curator for developers.
    Select only the most newsworthy and technically significant articles.
    Be strict - quality over quantity.
    IMPORTANT: Include the exact URLs for each selected article."""

    curated = call_agent(prompt, system_message)

    print("\nCurated articles selected.")
    return curated


def step_2b_fetch_full_articles(curated_text: str, all_articles: list) -> str:
    """Step 2b: Fetch full content from curated article URLs."""
    print("\n" + "=" * 50)
    print("STEP 2b: Fetching full article content...")
    print("=" * 50)

    # Extract URLs from curated text
    import re
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, curated_text)

    # Also get URLs from original articles that match curated titles
    all_urls = set(urls)
    for article in all_articles:
        if article.get('url'):
            # Check if this article's title appears in curated text
            if article.get('title', '')[:30].lower() in curated_text.lower():
                all_urls.add(article['url'])

    urls = list(all_urls)[:5]  # Max 5 articles

    if not urls:
        print("  No URLs found to fetch")
        return curated_text

    print(f"  Found {len(urls)} URLs to fetch full content")

    # Fetch full content
    full_content = fetch_multiple_articles(urls, max_length_per_article=2500)

    # Combine curated summary with full content
    enhanced = f"""CURATED ARTICLE SUMMARIES:
{curated_text}

FULL ARTICLE CONTENT:
{full_content}
"""
    print("  Full content fetched successfully")
    return enhanced


def step_3_write_post(curated_articles: str, source_articles: str) -> str:
    """Step 3: Generate the LinkedIn post."""
    print("\n" + "=" * 50)
    print("STEP 3: Writing LinkedIn post...")
    print("=" * 50)

    prompt = get_writer_prompt(curated_articles)

    system_message = """You are a developer who loves AI and shares discoveries on LinkedIn.
    Write engaging, informative posts with your personal thoughts.
    CRITICAL: Only use facts from the provided sources. Never invent information."""

    draft_post = call_agent(prompt, system_message)

    print("\nDraft post generated.")
    return draft_post


def step_4_verify_post(draft_post: str, source_articles: str) -> dict:
    """Step 4: Verify the post against sources."""
    print("\n" + "=" * 50)
    print("STEP 4: Verifying post accuracy...")
    print("=" * 50)

    prompt = get_verifier_prompt(draft_post, source_articles)

    system_message = """You are a rigorous fact-checker.
    Verify every claim against the source material.
    Be strict - flag any claim that isn't directly supported by sources."""

    verification_report = call_agent(prompt, system_message)

    # Parse the result to determine if it passed
    report_lower = verification_report.lower()

    # Check for PASSED status or PUBLISH recommendation
    passed = ("overall status: passed" in report_lower or
              "recommendation: publish" in report_lower or
              "recommendation:\npublish" in report_lower)

    # Count verified vs unverified claims (handle markdown formatting)
    # Remove markdown bold markers for counting
    report_clean = report_lower.replace("**", "").replace("*", "")
    verified_count = report_clean.count("status: verified")
    unverified_count = report_clean.count("status: unverified")
    total_claims = verified_count + unverified_count

    # Calculate confidence based on verified claims
    if total_claims > 0:
        confidence = int((verified_count / total_claims) * 100)
    else:
        confidence = 0

    # If all claims verified, mark as passed
    if unverified_count == 0 and verified_count > 0:
        passed = True
        confidence = 100

    print(f"\nVerification: {'PASSED' if passed else 'FAILED'}")
    print(f"  Claims: {verified_count} verified, {unverified_count} unverified")
    print(f"  Confidence: {confidence}%")

    return {
        "passed": passed,
        "confidence": confidence,
        "report": verification_report
    }


def step_4b_rewrite_verified_only(draft_post: str, verification_report: str, source_articles: str) -> str:
    """Step 4b: Rewrite post with only verified claims."""
    print("\n" + "=" * 50)
    print("STEP 4b: Rewriting with only VERIFIED claims...")
    print("=" * 50)

    prompt = f"""You are rewriting a LinkedIn post to include ONLY verified information.

ORIGINAL POST:
{draft_post}

VERIFICATION REPORT:
{verification_report}

SOURCE ARTICLES:
{source_articles}

STRICT RULES:
1. COMPLETELY DELETE any news item/section that has ANY unverified claims
2. Do NOT add new words, phrases, or details that aren't in the original post
3. Do NOT add adjectives or descriptions that weren't verified
4. Keep ONLY sections where ALL claims were marked VERIFIED
5. Update References to only include URLs for remaining items
6. Keep the hook, engagement question, and hashtags
7. Do NOT embellish or add "enterprise-grade", "cutting-edge", or similar terms unless they were verified

IMPORTANT: If a section had ANY unverified claim, delete the ENTIRE section. Do not try to fix it.

Write the cleaned post:"""

    system_message = """You are a strict content editor.
    Your ONLY job is to DELETE unverified sections.
    Do NOT add any new words or claims.
    Do NOT try to improve or embellish the content.
    Just remove what failed verification."""

    revised_post = call_agent(prompt, system_message)

    print("\nPost rewritten with verified claims only.")
    return revised_post


def step_5_post_to_linkedin(content: str, dry_run: bool = True) -> dict:
    """Step 5: Post to LinkedIn (or dry run)."""
    print("\n" + "=" * 50)
    print("STEP 5: Posting to LinkedIn...")
    print("=" * 50)

    if dry_run:
        print("\n[DRY RUN MODE - Not actually posting]")
        print("\n--- POST CONTENT ---")
        print(content)
        print("--- END POST ---")
        return {"success": True, "dry_run": True}

    result = post_to_linkedin(content)

    if result["success"]:
        print(f"\nPost published successfully!")
        print(f"Post ID: {result.get('post_id', 'N/A')}")
    else:
        print(f"\nFailed to post: {result.get('error', 'Unknown error')}")

    return result


def run_workflow(
    dry_run: bool = True,
    hours_back: int = 48,
    skip_verification: bool = False,
    confidence_threshold: int = 85
) -> dict:
    """
    Run the complete LinkedIn auto-poster workflow.

    Args:
        dry_run: If True, don't actually post to LinkedIn
        hours_back: How many hours back to look for news
        skip_verification: If True, skip the fact-checking step
        confidence_threshold: Minimum confidence score to publish

    Returns:
        Dict with workflow results
    """
    print("\n" + "=" * 60)
    print("  LINKEDIN AI AUTO-POSTER WORKFLOW")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {
        "started_at": datetime.now().isoformat(),
        "dry_run": dry_run,
        "steps": {}
    }

    # Step 1: Fetch news
    articles_text = step_1_fetch_news(hours_back)
    if not articles_text:
        print("\nNo articles found. Skipping post for today.")
        results["status"] = "skipped"
        results["reason"] = "No articles found"
        return results

    # Get the raw articles list for URL extraction
    rss_articles = fetch_rss_feeds(hours_back=hours_back)
    gnews_articles = fetch_gnews()
    all_articles = rss_articles + gnews_articles

    results["steps"]["fetch"] = {"articles_found": len(all_articles)}

    # Step 2: Curate
    curated = step_2_curate_news(articles_text)
    results["steps"]["curate"] = {"completed": True}

    # Step 2b: Fetch full article content
    enhanced_content = step_2b_fetch_full_articles(curated, all_articles)
    results["steps"]["fetch_full"] = {"completed": True}

    # Step 3: Write post (with full article content)
    draft_post = step_3_write_post(enhanced_content, articles_text)
    results["steps"]["write"] = {"completed": True, "draft": draft_post}

    # Step 4: Verify (optional) - use enhanced content for better verification
    if not skip_verification:
        verification = step_4_verify_post(draft_post, enhanced_content)
        results["steps"]["verify"] = verification

        # Retry loop - keep cleaning until 100% verified or max retries
        max_retries = 3
        current_verification = verification
        retry_count = 0

        while (not current_verification["passed"] or current_verification["confidence"] < 100) and retry_count < max_retries:
            retry_count += 1
            print(f"\n⚠️  Verification: {current_verification['confidence']}% (need 100%)")
            print(f"🔄 Rewriting attempt {retry_count}/{max_retries}...")

            # Rewrite with only verified claims (use enhanced content)
            draft_post = step_4b_rewrite_verified_only(
                draft_post,
                current_verification["report"],
                enhanced_content
            )
            results["steps"][f"rewrite_{retry_count}"] = {"completed": True}

            # Re-verify (use enhanced content)
            print(f"\n🔍 Re-verifying (attempt {retry_count})...")
            current_verification = step_4_verify_post(draft_post, enhanced_content)
            results["steps"][f"verify_{retry_count}"] = current_verification

            if current_verification["confidence"] == 100:
                print(f"\n✅ Post is 100% verified!")
                break

        # Final check
        if current_verification["confidence"] < 100:
            print(f"\n❌ Could not reach 100% after {max_retries} attempts.")
            print(f"    Final confidence: {current_verification['confidence']}%")
            print(f"\nSaving for manual review.")

            # Save draft for manual review
            draft_file = f"drafts/draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            os.makedirs("drafts", exist_ok=True)
            with open(draft_file, 'w') as f:
                f.write("=== DRAFT POST (BEST EFFORT) ===\n\n")
                f.write(draft_post)
                f.write("\n\n=== VERIFICATION REPORT ===\n\n")
                f.write(current_verification["report"])

            results["status"] = "draft_saved"
            results["draft_file"] = draft_file
            results["final_confidence"] = current_verification["confidence"]
            return results
    else:
        results["steps"]["verify"] = {"skipped": True}

    # Step 5: Post
    post_result = step_5_post_to_linkedin(draft_post, dry_run)
    results["steps"]["post"] = post_result
    results["status"] = "success" if post_result["success"] else "failed"

    print("\n" + "=" * 60)
    print(f"  WORKFLOW COMPLETE - Status: {results['status'].upper()}")
    print("=" * 60)

    return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="LinkedIn AI Auto-Poster")
    parser.add_argument(
        "--post",
        action="store_true",
        help="Actually post to LinkedIn (default is dry run)"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Hours back to look for news (default: 48)"
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip fact verification step"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=85,
        help="Minimum confidence threshold to publish (default: 85)"
    )

    args = parser.parse_args()

    # Validate environment
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set in environment")
        sys.exit(1)

    if args.post and not os.getenv("LINKEDIN_ACCESS_TOKEN"):
        print("ERROR: LINKEDIN_ACCESS_TOKEN not set (required for actual posting)")
        sys.exit(1)

    # Run workflow
    results = run_workflow(
        dry_run=not args.post,
        hours_back=args.hours,
        skip_verification=args.skip_verify,
        confidence_threshold=args.threshold
    )

    # Save results
    results_file = f"logs/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("logs", exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    main()
