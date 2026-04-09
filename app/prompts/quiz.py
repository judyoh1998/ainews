SYSTEM = (
    "You generate multiple-choice quiz questions about AI news stories. "
    "Questions should test comprehension, not trivia. All options should be plausible."
)

USER_TEMPLATE = """Generate one multiple-choice question for each of these AI news stories:

{stories_json}

For each story, create a question with 4 options (A-D), exactly one correct answer.

Rules:
- Questions should test understanding of the story's significance
- Wrong answers should be plausible but clearly wrong if you read the story
- Include a brief explanation of why the correct answer is right

Respond with ONLY a JSON object (no markdown fences):
{{
  "questions": [
    {{
      "id": 1,
      "story_rank": 1,
      "question": "...",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_index": 0,
      "explanation": "..."
    }}
  ]
}}"""
