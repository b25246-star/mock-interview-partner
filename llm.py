import os
import time
from pathlib import Path

import ollama
from pydantic import ValidationError

MODEL = os.getenv("MODEL", "llama3.2:3b")
PROMPT_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def chat_json(system: str, user: str, schema, retries: int = 1):
    """Ask the local model for JSON matching a Pydantic model; validate; retry once."""
    last_err = None
    for _ in range(retries + 1):
        t0 = time.time()
        resp = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            format=schema.model_json_schema(),
            keep_alive="30m",
            options={"temperature": 0.3, "num_ctx": 4096, "num_predict": 1200},
        )
        print(
            f"[llm] model={MODEL} schema={schema.__name__} "
            f"{time.time() - t0:.1f}s, {getattr(resp, 'eval_count', '?')} tokens",
            flush=True,
        )
        try:
            return schema.model_validate_json(resp["message"]["content"])
        except ValidationError as e:
            last_err = e
    raise RuntimeError(f"Model returned invalid JSON twice: {last_err}")