"""Quick test to verify LLM API key and model work."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings


async def test():
    settings = Settings()
    print(f"API Key: {settings.llm_api_key[:20]}...{settings.llm_api_key[-10:]}")
    print(f"Model: {settings.llm_model}")
    print(f"Base URL: {settings.llm_base_url}")
    print()

    import httpx
    async with httpx.AsyncClient() as client:
        print("Sending test request to Anthropic...")
        try:
            response = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": settings.llm_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Say hello in 5 words."}],
                },
                timeout=15.0,
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test())
