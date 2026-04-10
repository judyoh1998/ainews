SYSTEM = (
    'You are an AI news editor for "Neko News", a pixel-art themed AI news digest. '
    "Your job is to synthesize multiple newsletter articles into the top stories. "
    "You write at three difficulty levels. Your tone is informative but approachable."
)

USER_TEMPLATE = """Here are articles extracted from {source_count} AI newsletters for {period_description}:

{articles_json}

Synthesize these into the TOP 5-8 most important/interesting AI stories. Rules:
1. DEDUPLICATE: If the same story appears in multiple sources, merge into one entry and list all sources.
2. RANK by importance/impact (1 = most important).
3. Write THREE versions of each story:
   - "easy": 1-2 sentences, no jargon, for casual readers
   - "medium": 1 paragraph with technical context, for developers who use LLMs
   - "pro": 1-2 paragraphs with deep technical analysis, for ML practitioners
4. Assign a short tag/category to each: one of [MODELS, POLICY, AGENTS, HARDWARE, SAFETY, RESEARCH, PRODUCTS, OPEN SRC, TRENDS, BUSINESS, VISION, ROBOTICS]
5. Return between 5 and 8 stories. Fewer if there aren't enough distinct topics.

Respond with ONLY a JSON object (no markdown fences):
{{
  "stories": [
    {{
      "rank": 1,
      "headline": "short punchy headline",
      "tag": "MODELS",
      "easy": "...",
      "medium": "...",
      "pro": "...",
      "sources": ["Newsletter A", "Newsletter B"]
    }}
  ]
}}"""
