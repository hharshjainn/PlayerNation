"""
Centralized, environment-driven configuration.

Extended in Phase 4 with Groq LLM settings -- model id, timeout, retry
budget, temperature, and seed are all env-driven here rather than
hardcoded in `llm_service.py`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class Settings(BaseModel):
    raw_data_dir: Path = Path(__file__).resolve().parents[2] / "data" / "raw"
    default_competition: str = "World_Cup"

    # Phase 4 -- Groq (OpenAI-compatible) LLM settings.
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_request_timeout_seconds: float = 30.0
    groq_max_retries: int = 2  # additional attempts after the first try
    groq_temperature: float = 0.2  # low, for more deterministic/consistent reports
    groq_seed: Optional[int] = 42  # Groq best-effort deterministic sampling; None to disable

    @classmethod
    def from_env(cls) -> "Settings":
        raw_dir = os.environ.get("PLAYERNATION_RAW_DATA_DIR")
        competition = os.environ.get("PLAYERNATION_COMPETITION", "World_Cup")
        kwargs: dict = {"default_competition": competition}
        if raw_dir:
            kwargs["raw_data_dir"] = Path(raw_dir)

        kwargs["groq_api_key"] = os.environ.get("GROQ_API_KEY")
        if (model := os.environ.get("PLAYERNATION_GROQ_MODEL")):
            kwargs["groq_model"] = model
        if (timeout := os.environ.get("PLAYERNATION_GROQ_TIMEOUT_SECONDS")):
            kwargs["groq_request_timeout_seconds"] = float(timeout)
        if (retries := os.environ.get("PLAYERNATION_GROQ_MAX_RETRIES")):
            kwargs["groq_max_retries"] = int(retries)
        if (temperature := os.environ.get("PLAYERNATION_GROQ_TEMPERATURE")):
            kwargs["groq_temperature"] = float(temperature)
        if (seed := os.environ.get("PLAYERNATION_GROQ_SEED")):
            kwargs["groq_seed"] = int(seed)

        return cls(**kwargs)


settings = Settings.from_env()

