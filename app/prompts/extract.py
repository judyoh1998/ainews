SYSTEM = (
    "You are a newsletter content extractor. Given raw newsletter content, "
    "extract individual news articles/stories. Return structured JSON only."
)

USER_TEMPLATE = """Extract all distinct news articles from this newsletter content.

For each article, extract:
- title: The headline or topic (infer one if not explicit)
- body: The article text (preserve key facts, names, numbers)
- url: Any URL associated with the article (null if none)

Newsletter content:
---
{content}
---

Respond with ONLY a JSON object in this exact format (no markdown fences):
{{
  "articles": [
    {{"title": "...", "body": "...", "url": null}}
  ]
}}"""
