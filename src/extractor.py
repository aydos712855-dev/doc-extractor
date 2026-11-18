from __future__ import annotations

import json
import os
import re
from typing import Optional

import httpx
from pydantic import ValidationError

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import DocumentExtraction

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
MAX_RETRIES = 2


class ExtractionError(Exception):
    pass


def _call_ollama(document_text: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(document_text)}"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
    }
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["response"]
    except httpx.ConnectError as e:
        raise ExtractionError(
            f"Cannot connect to Ollama at {OLLAMA_URL}. "
            "Start Ollama or set OLLAMA_URL env var."
        ) from e


def _extract_json(raw: str) -> dict:
    """Extract JSON object from raw LLM response (may have extra text)."""
    raw = raw.strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ExtractionError(f"No JSON found in LLM response: {raw[:200]}")
    return json.loads(match.group())


def extract(document_text: str) -> DocumentExtraction:
    """
    Call Ollama, parse and validate the JSON response.
    Retries up to MAX_RETRIES times on validation failure.
    Raises ExtractionError if all retries fail.
    """
    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        raw = _call_ollama(document_text)
        try:
            data = _extract_json(raw)
            return DocumentExtraction.model_validate(data)
        except (ValidationError, json.JSONDecodeError, KeyError) as e:
            last_error = e
            # On retry, append error context to help the model fix it
            if attempt < MAX_RETRIES:
                document_text = (
                    document_text
                    + f"\n\n[RETRY {attempt + 1}: previous response failed validation: {e}. Fix and return only valid JSON.]"
                )

    raise ExtractionError(
        f"Validation failed after {MAX_RETRIES + 1} attempts. Last error: {last_error}"
    ) from last_error
