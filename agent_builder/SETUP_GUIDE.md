# OpenAI Agent Builder Setup Guide

## Overview

This guide walks you through deploying your LinkedIn AI Auto-Poster to OpenAI Agent Builder.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenAI Agent Builder                      │
│  ┌──────────┐   ┌─────────┐   ┌────────┐   ┌─────────────┐ │
│  │ Webhook  │──▶│ Curator │──▶│ Writer │──▶│  Verifier   │ │
│  │ Trigger  │   │  Agent  │   │ Agent  │   │    Agent    │ │
│  └──────────┘   └─────────┘   └────────┘   └──────┬──────┘ │
│                                                    │        │
│                                              ┌─────▼─────┐  │
│                                              │  Quality  │  │
│                                              │   Gate    │  │
│                                              └─────┬─────┘  │
└───────────────────────────────────────────────────│────────┘
                                                    │
                          ┌─────────────────────────┼─────────────────────────┐
                          │                         │                         │
                          ▼                         ▼                         │
              ┌───────────────────┐     ┌───────────────────┐                │
              │  Tools Server     │     │  Tools Server     │                │
              │  /fetch_ai_news   │     │  /post_to_linkedin│                │
              │  (Your Server)    │     │  (Your Server)    │                │
              └───────────────────┘     └───────────────────┘                │
                                                                              │
                          Hosted on Railway/Render/Your Server                │
```

## Step 1: Deploy Tools Server

Your tools server provides the RSS/GNews fetching and LinkedIn posting capabilities.

### Option A: Deploy to Railway (Recommended - Free)

1. Create account at [railway.app](https://railway.app)

2. Install Railway CLI:
   ```bash
   npm install -g @railway/cli
   railway login
   ```

3. Deploy:
   ```bash
   cd /Users/gowthamkumarsolleti/Desktop/linkedin
   railway init
   railway up
   ```

4. Set environment variables in Railway dashboard:
   ```
   GNEWS_API_KEY=f4863002ee264499e20c3d87f660ce82
   LINKEDIN_ACCESS_TOKEN=<your-token>
   ```

5. Note your Railway URL (e.g., `https://linkedin-auto-poster.up.railway.app`)

### Option B: Deploy to Render (Free)

1. Create account at [render.com](https://render.com)

2. Connect GitHub repo or upload code

3. Create new Web Service:
   - Build Command: `pip install -r requirements.txt flask`
   - Start Command: `python agent_builder/tools_server.py`

4. Add environment variables

5. Note your Render URL

### Option C: Local Testing with ngrok

1. Install ngrok:
   ```bash
   brew install ngrok
   ```

2. Start tools server:
   ```bash
   python agent_builder/tools_server.py
   ```

3. In another terminal, expose it:
   ```bash
   ngrok http 5000
   ```

4. Use the ngrok URL (e.g., `https://abc123.ngrok.io`)

## Step 2: Create Workflow in Agent Builder

1. Go to [platform.openai.com/agent-builder](https://platform.openai.com/agent-builder)

2. Click **"Create new workflow"**

3. Add nodes as follows:

### Node 1: Webhook Trigger
- Type: **Trigger** → **Webhook**
- Name: `Daily Trigger`

### Node 2: Fetch News Tool
- Type: **Tool** → **HTTP Request**
- Name: `Fetch AI News`
- Method: `POST`
- URL: `<YOUR_SERVER_URL>/tools/fetch_ai_news`
- Body: `{"hours_back": 48}`

### Node 3: News Curator Agent
- Type: **Agent**
- Name: `News Curator`
- Model: `gpt-4o`
- System Prompt:
```
You are an AI News Curator for a developer-focused LinkedIn account.

Select the TOP 3-5 most interesting and newsworthy items for developers.

Selection criteria (priority order):
1. New product launches or major feature releases
2. API releases developers can use
3. Technical breakthroughs with practical applications
4. Developer tools and frameworks

Avoid:
- Opinion pieces without new information
- Company hiring/funding news
- Repeated coverage of same story
- Vague "AI is changing everything" articles

For each selected article, output:
- Title
- Source
- URL (EXACTLY as provided - do not modify)
- Why it's newsworthy for developers
- Key technical details to highlight
```

### Node 4: Content Writer Agent
- Type: **Agent**
- Name: `Content Writer`
- Model: `gpt-4o`
- System Prompt:
```
You are a LinkedIn Content Writer for a developer who loves AI.

Voice & Tone:
- Enthusiastic "new things in town" energy
- Practical mindset - "how can I use this in my projects?"
- Technical but accessible

Post Structure:
1. Hook: Attention-grabbing opener
2. For each news item (3-5):
   - 𝐁𝐨𝐥𝐝 𝐭𝐢𝐭𝐥𝐞 (LinkedIn Unicode)
   - What it is (2-3 sentences)
   - Technical details
   - 💭 𝐌𝐲 𝐭𝐡𝐨𝐮𝐠𝐡𝐭𝐬: Personal take, project ideas
3. Engagement question
4. 📚 𝐑𝐞𝐟𝐞𝐫𝐞𝐧𝐜𝐞𝐬: All URLs at bottom
5. Hashtags: #AI #GenAI #OpenAI etc.

CRITICAL:
- ONLY include facts from provided sources
- Do NOT invent features or capabilities
- Use URLs EXACTLY as provided
- Keep total length 1500-2500 characters
```

### Node 5: Fact Verifier Agent
- Type: **Agent**
- Name: `Fact Verifier`
- Model: `gpt-4o`
- System Prompt:
```
You are a Fact Verification Agent ensuring posts contain only accurate information.

For each claim in the draft post:
1. Identify the claim
2. Find the source article
3. Verify claim is supported by source

Check:
- Feature claims match source
- Numbers/benchmarks are accurate
- Release status is correct
- URLs match the right articles

Output JSON:
{
  "verified": true/false,
  "confidence": 0-100,
  "issues": ["list of problems if any"]
}

Mark as FAILED if ANY claim is not directly supported by sources.
```

### Node 6: Condition (Quality Gate)
- Type: **Condition**
- Name: `Quality Gate`
- Condition: Check if `verified == true` and `confidence >= 85`
- If true: Connect to "Post to LinkedIn"
- If false: Connect to "Manual Review"

### Node 7: Post to LinkedIn Tool
- Type: **Tool** → **HTTP Request**
- Name: `Post to LinkedIn`
- Method: `POST`
- URL: `<YOUR_SERVER_URL>/tools/post_to_linkedin`
- Body: `{"content": "{{writer_output}}"}`

### Node 8: Manual Review Output
- Type: **Output**
- Name: `Manual Review Required`
- Returns the draft for manual review

## Step 3: Connect the Nodes

Draw edges in this order:
```
Trigger → Fetch News → Curator → Writer → Verifier → Quality Gate
                                                         ↓
                                              ┌──────────┴──────────┐
                                              ↓                     ↓
                                       Post to LinkedIn      Manual Review
```

## Step 4: Test the Workflow

1. Click **Preview** in Agent Builder
2. Manually trigger the workflow
3. Watch each node execute
4. Check the output at each stage

## Step 5: Publish and Deploy

1. Click **Publish** to create a workflow version
2. Note your **Workflow ID**
3. Set up the trigger:

### Option A: Use ChatKit
- Embed in a web app that triggers daily

### Option B: Use cron + API call
Create a GitHub Action or cron job:

```yaml
# .github/workflows/daily-post.yml
name: Daily LinkedIn Post
on:
  schedule:
    - cron: '30 4 * * *'  # 10am IST
  workflow_dispatch:

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Agent Workflow
        run: |
          curl -X POST "https://api.openai.com/v1/workflows/${{ secrets.WORKFLOW_ID }}/runs" \
            -H "Authorization: Bearer ${{ secrets.OPENAI_API_KEY }}" \
            -H "Content-Type: application/json"
```

## Troubleshooting

### "Tool call failed"
- Check your tools server is running and accessible
- Verify the URL in Agent Builder matches your deployed server

### "LinkedIn post failed"
- Check your LinkedIn access token hasn't expired (60 days)
- Re-run `python get_linkedin_token.py` to refresh

### "No articles found"
- RSS feeds might be temporarily down
- Try increasing `hours_back` parameter

### "Verification failed"
- This is expected sometimes - means AI caught potential inaccuracies
- Check the draft in Manual Review output
- Edit and post manually if needed

## Maintenance

- **LinkedIn token**: Refresh every 60 days
- **Monitor costs**: Each run uses ~$0.05-0.10 in OpenAI API
- **Check logs**: Review Agent Builder run history for errors
