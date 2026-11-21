"""Check that the AI (Gemini) is configured and reachable. Prints no secrets.

    docker compose exec worker python scripts/check_ai.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402


async def main() -> None:
    s = get_settings()
    key = os.environ.get("GOOGLE_API_KEY", "")
    print(f"LLM_ENABLED        = {s.llm_enabled}")
    print(f"LLM_MAIN_MODEL     = {s.llm_main_model}")
    print(f"GOOGLE_API_KEY set = {bool(key)} (length {len(key)})")
    print(f"INTENT_AI_ENABLED  = {s.intent_ai_enabled}")
    print(f"VOICE_ENABLED      = {s.voice_enabled}")
    if not s.llm_enabled:
        print("\n-> The AI is switched off. Set LLM_ENABLED=true in .env, then: docker compose up -d")
        return
    if not key:
        print("\n-> GOOGLE_API_KEY is empty. Add it to .env, then: docker compose up -d")
        return

    from app.agent.llm import get_main_model

    model = get_main_model()
    if model is None:
        print("\n-> The model could not be created (see the error above). Check LLM_MAIN_MODEL.")
        return
    import time

    print(f"THINKING (main/intent) = {s.llm_thinking_level or 'default'} / {s.intent_thinking_level or 'default'}")
    try:
        t0 = time.monotonic()
        resp = await asyncio.wait_for(model.ainvoke("Reply with exactly: ok"), timeout=30)
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        print(f"\nGemini replied: {text.strip()[:80]!r} in {time.monotonic() - t0:.1f}s")
    except Exception as e:  # show the reason, not the key
        msg = str(e).replace(key, "***") if key else str(e)
        print(f"\n-> Gemini call failed: {type(e).__name__}: {msg[:400]}")
        return

    from app.agent.intent import classify
    from app.agent.llm import get_intent_model

    fast = get_intent_model() or model
    t0 = time.monotonic()
    label = await classify("my boss hasnt given me money for october", fast, timeout=30)
    took = time.monotonic() - t0
    print(f"Intent test: 'my boss hasnt given me money for october' -> {label} in {took:.1f}s")
    if took > s.intent_timeout_seconds:
        print(f"-> Slower than INTENT_TIMEOUT_SECONDS={s.intent_timeout_seconds}; Rafiq would give up. Google may be busy - try again.")
    print("\nAll good." if label == "salary_late" else "\n-> The model answered, but not with the expected topic.")


if __name__ == "__main__":
    asyncio.run(main())
