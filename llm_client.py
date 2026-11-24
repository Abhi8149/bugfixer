"""
llm_client.py
-------------
Single reusable place for all OpenRouter communication.

Both Model 1 (test generation) and Model 2 (repair) use this module.
The two models are selected by passing different model_name values.

Uses the OpenAI Python SDK pointed at OpenRouter's compatible endpoint:
    base_url = https://openrouter.ai/api/v1
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

# Load .env once when this module is imported.
load_dotenv()

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def get_api_key() -> str:
    """Return the OpenRouter API key from the environment (may be empty)."""
    return os.getenv("OPENROUTER_API_KEY", "") or ""


def get_base_url() -> str:
    """Return the OpenRouter base URL, falling back to the default."""
    return os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL


def get_test_model() -> str:
    """Model 1 - test generation model name."""
    return os.getenv("TEST_MODEL", "deepseek/deepseek-v4.1-flash")


def get_repair_model() -> str:
    """Model 2 - repair model name."""
    return os.getenv("REPAIR_MODEL", "deepseek/deepseek-v4.1-flash")


def create_client() -> OpenAI:
    """
    Create an OpenAI SDK client configured for OpenRouter.

    Raises:
        ValueError: if OPENROUTER_API_KEY is missing or still a placeholder.
    """
    api_key = get_api_key()
    if not api_key or api_key == "your_openrouter_api_key_here":
        raise ValueError(
            "OPENROUTER_API_KEY is missing. "
            "Copy .env.example to .env and put your real OpenRouter key there."
        )
    base_url = get_base_url()
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client


def call_llm(prompt: str, model_name: str) -> str:
    """
    Send one prompt to a model via OpenRouter and return the text reply.

    Steps:
        1. Validate the API key (never prints the key).
        2. Send a Chat Completions request.
        3. Return the generated text.
        4. Handle API errors, missing credentials and empty responses.
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is empty. Nothing to send to the model.")
    if not model_name or not model_name.strip():
        raise ValueError("Model name is empty. Check TEST_MODEL / REPAIR_MODEL in .env.")

    # create_client raises a clear error when the key is missing.
    client = create_client()

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful Python software engineering assistant.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
    except Exception as error:
        # Do not include the API key in any message.
        raise RuntimeError(f"OpenRouter API request failed: {error}") from error

    # Extract text safely.
    try:
        text = response.choices[0].message.content
    except Exception as error:
        raise RuntimeError(f"Unexpected API response format: {error}") from error

    if text is None or not str(text).strip():
        raise RuntimeError("Model returned an empty response.")

    return str(text)
