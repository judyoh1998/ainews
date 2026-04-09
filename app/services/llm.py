"""Anthropic SDK wrapper with retry logic and structured JSON output."""

from __future__ import annotations

import json
import logging
import re
import time

from app.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    pass


class LLMService:
    def __init__(self):
        self._client = None
        if settings.anthropic_api_key:
            try:
                import anthropic

                self._client = anthropic.Anthropic(
                    api_key=settings.anthropic_api_key,
                    timeout=settings.llm_timeout,
                )
            except Exception as e:
                logger.warning("Failed to initialize Anthropic client: %s", e)

    @property
    def available(self) -> bool:
        return self._client is not None

    def call_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> dict:
        """Call Claude API and return parsed JSON.

        Retries up to llm_max_retries times on transient errors.
        Strips markdown fences before parsing.
        """
        if not self.available:
            raise LLMUnavailableError("No Anthropic API key configured")

        import anthropic

        last_error = None
        for attempt in range(settings.llm_max_retries):
            try:
                response = self._client.messages.create(
                    model=settings.llm_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                text = response.content[0].text
                return _parse_json_response(text)

            except anthropic.RateLimitError:
                last_error = "Rate limited"
                wait = 2 ** (attempt + 1)
                logger.warning("Rate limited, retrying in %ds...", wait)
                time.sleep(wait)

            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = f"Server error {e.status_code}"
                    wait = 2 ** (attempt + 1)
                    logger.warning("Server error %d, retrying in %ds...", e.status_code, wait)
                    time.sleep(wait)
                else:
                    raise

            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON: {e}"
                logger.warning("JSON parse failed on attempt %d: %s", attempt + 1, e)
                # Don't retry JSON errors — the model gave a bad response
                break

            except Exception as e:
                last_error = str(e)
                logger.error("LLM call failed: %s", e)
                break

        raise RuntimeError(f"LLM call failed after retries: {last_error}")


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    # Strip ```json ... ``` wrappers
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# Module-level singleton
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
