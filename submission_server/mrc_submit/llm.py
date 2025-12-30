from __future__ import annotations

import os
from typing import Any


def preprocess_submission(payload: dict[str, Any]) -> dict[str, Any]:
    provider = (os.getenv("MRC_LLM_PROVIDER") or "").strip().lower()
    api_key = (os.getenv("MRC_LLM_API_KEY") or "").strip()

    if not provider or not api_key:
        return {"status": "skipped", "reason": "LLM not configured"}

    return {
        "status": "skipped",
        "reason": "LLM adapter not implemented",
        "provider": provider,
    }
