# LinkedIn AI Auto-Poster Design

## Overview

Automated LinkedIn posting workflow using OpenAI Agent Builder that posts daily at 10am with curated AI/GenAI news from official sources, including developer commentary and verified facts.

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Cron Job   │────▶│  OpenAI Agent   │────▶│  LinkedIn    │
│  (10am)     │     │  Builder Flow   │     │  Post API    │
└─────────────┘     └─────────────────┘     └──────────────┘
                            │
                    ┌───────┴───────┐
                    ▼               ▼
              ┌──────────┐   ┌─────────────┐
              │ RSS Feeds│   │ GNews API   │
              │ (Free)   │   │ (Free tier) │
              └──────────┘   └─────────────┘
```

## Components

### 1. Trigger: GitHub Actions Cron Job
- Runs daily at 10am (configured for user's timezone)
- Calls OpenAI workflow via webhook
- Free tier: 2000 minutes/month

### 2. News Sources

**RSS Feeds (Official AI Company Blogs):**
- OpenAI: `https://openai.com/blog/rss.xml`
- Anthropic: `https://www.anthropic.com/news/rss`
- Google AI: `https://blog.google/technology/ai/rss/`
- DeepMind: `https://deepmind.google/blog/rss.xml`
- Hugging Face: `https://huggingface.co/blog/feed.xml`
- Meta AI: `https://ai.meta.com/blog/rss/`
- Mistral AI: `https://mistral.ai/feed.xml`

**News API:**
- GNews API (100 requests/day free)
- Query: "artificial intelligence OR generative AI OR LLM"

### 3. LinkedIn Integration
- LinkedIn Share API (v2/ugcPosts)
- OAuth 2.0 authentication
- Credentials stored in environment variables

## Agent Builder Workflow Nodes

### Node 1: Webhook Trigger
- Input: HTTP POST from GitHub Actions
- Output: Trigger signal to start workflow

### Node 2: RSS Fetcher (Tool)
- Fetches latest articles from all RSS feeds
- Filters to last 48 hours
- Output: Array of `{title, summary, url, date, source}`

### Node 3: GNews API Fetcher (Tool)
- Queries GNews for AI-related articles
- Max 10 results per call
- Output: Array of `{title, summary, url, date, source}`

### Node 4: News Curator Agent
- Input: Combined articles from RSS + GNews
- Task: Rank by relevance, recency, developer interest
- Criteria:
  - New product launches/features
  - API releases
  - Major research breakthroughs
  - Developer tools and frameworks
- Output: Top 3-5 articles with reasoning

### Node 5: Content Writer Agent
- Input: Top 3-5 curated articles
- Task: Generate LinkedIn post in developer voice
- Voice characteristics:
  - Enthusiastic "new in town" energy
  - Practical/hands-on perspective
  - "Can't wait to try this in my projects"
  - Technical but accessible
- Output: Draft post with source citations

### Node 6: Fact Verifier Agent
- Input: Draft post + original source articles
- Tasks:
  - Verify every claim against source material
  - Check no hallucinated features/quotes
  - Validate dates and statistics
  - Ensure links match content
- Output: `{verified: bool, issues: [], confidence: 0-100}`

### Node 7: Quality Gate (Condition)
- If `verified=true` AND `confidence>85`: Continue to posting
- Else: Route to notification node

### Node 8: LinkedIn Poster (Tool)
- Posts verified content via LinkedIn API
- Handles OAuth token refresh
- Output: Post URL or error

### Node 9: Failure Notifier (Tool)
- Triggered when quality gate fails
- Sends email/webhook with draft + issues
- Allows manual review and posting

## Post Format

```
🚀 [Number] AI breakthroughs this week every developer should know:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

𝟏. [Bold Title]

[2-3 sentences explaining what it is and how it works]

[Technical details: benchmarks, capabilities, pricing if relevant]

💭 𝐌𝐲 𝐭𝐡𝐨𝐮𝐠𝐡𝐭𝐬: [Personal opinion, hot take, what you'll build with it]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Repeat for each item...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Engagement question] 👇

📚 𝐑𝐞𝐟𝐞𝐫𝐞𝐧𝐜𝐞𝐬:
[1] source-url-1
[2] source-url-2
[3] source-url-3

#AI #GenAI #OpenAI #Claude #Gemini #BuildInPublic
```

## Evaluations & Quality Gates

### Content Quality Graders
- **Relevance**: Is the news actually about AI/GenAI?
- **Freshness**: Is it from the last 24-48 hours?
- **Duplication**: Have we posted about this recently?
- **Link validation**: Are all URLs working?

### Post Quality Graders
- **Length**: 1500-2500 characters (LinkedIn optimal)
- **Tone**: Developer-friendly, enthusiastic voice
- **Hashtags**: Relevant tags included
- **CTA**: Engagement question present

### Truth Verification Graders
- **Source-to-summary match**: Generated content matches original
- **Claim extraction**: Every fact traceable to source
- **No fabricated quotes**: Quoted text exists verbatim
- **No invented features**: Announcements are real
- **Date accuracy**: Dates match sources

### Anti-Hallucination Checks
- Ground every statement to source URL
- Confidence scoring on each claim
- Cross-reference major claims across sources

## Technical Setup

### Environment Variables / Secrets
```
OPENAI_API_KEY=sk-your-key-here
GNEWS_API_KEY=your-gnews-key
LINKEDIN_CLIENT_ID=your-client-id
LINKEDIN_CLIENT_SECRET=your-client-secret
LINKEDIN_ACCESS_TOKEN=your-access-token
```

### GitHub Actions Workflow
```yaml
name: Daily LinkedIn AI Post
on:
  schedule:
    - cron: '30 4 * * *'  # 10am IST
  workflow_dispatch:

jobs:
  trigger-agent:
    runs-on: ubuntu-latest
    steps:
      - name: Call OpenAI Workflow
        run: |
          curl -X POST "$WORKFLOW_URL" \
            -H "Authorization: Bearer ${{ secrets.OPENAI_API_KEY }}"
```

## Cost Estimate

| Service | Cost |
|---------|------|
| GitHub Actions | Free (2000 min/month) |
| GNews API | Free (100 req/day) |
| RSS Feeds | Free |
| LinkedIn API | Free |
| OpenAI API | ~$0.05-0.10/day |
| **Total** | **~$1.50-3.00/month** |

## Fallback Behavior

- **No quality news found**: Skip posting that day
- **Verification fails**: Save draft, notify for manual review
- **API errors**: Retry 3x with exponential backoff, then notify

## Future Enhancements (Not in scope)

- Analytics tracking (post performance)
- A/B testing different formats
- Multiple social platforms
- User feedback loop to improve curation
