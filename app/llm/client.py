"""LLM client for Anthropic Claude API interactions."""

import logging

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Anthropic Claude LLM client for price analysis.

    Sends structured prompts to the Anthropic Messages API and returns
    the response text. Configured via api_key, model, and base_url from
    application settings.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        base_url: str = "https://api.anthropic.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def complete(self, prompt: str) -> str:
        """Send a prompt to Claude and return the response text.

        Args:
            prompt: The user message to send to the LLM.

        Returns:
            The content string from Claude's response.

        Raises:
            LLMError: If the request times out or the API returns an error.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                # Anthropic returns content as a list of blocks
                return data["content"][0]["text"]
            except httpx.TimeoutException:
                logger.error(
                    "LLM request timed out (model=%s, base_url=%s)",
                    self.model,
                    self.base_url,
                )
                raise LLMError("LLM request timed out after 30 seconds")
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "LLM API returned HTTP %d: %s",
                    exc.response.status_code,
                    exc.response.text[:200],
                )
                raise LLMError(
                    f"LLM API error: HTTP {exc.response.status_code}"
                ) from exc


class LLMError(Exception):
    """Raised when the LLM client encounters an error."""

    pass
