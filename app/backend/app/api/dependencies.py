"""
Dependency-injection providers for the API layer (Phase 6).

The dataset loader, LLM service, and report cache are all expensive or
stateful enough that they must be created once and reused across
requests -- recreating `DatasetLoader` per request would mean reloading
every JSON file from disk on every single call, and recreating the cache
per request would make caching pointless. `lru_cache` on these
zero-argument factories is the standard FastAPI pattern for a singleton
dependency: each `get_*` function returns the exact same instance after
its first call, which is what makes them safe to use as
`Depends(get_report_service)` in route signatures.
"""
from __future__ import annotations

from functools import lru_cache

from app.cache.report_cache import InMemoryReportCache
from app.core.config import settings
from app.data.dataset_loader import DatasetLoader
from app.llm.llm_service import GroqReportService
from app.services.match_service import MatchService
from app.services.report_service import ReportService


@lru_cache
def get_dataset_loader() -> DatasetLoader:
    return DatasetLoader(settings.raw_data_dir, settings.default_competition)


@lru_cache
def get_match_service() -> MatchService:
    return MatchService(get_dataset_loader())


@lru_cache
def get_report_cache() -> InMemoryReportCache:
    return InMemoryReportCache()


@lru_cache
def get_llm_service() -> GroqReportService:
    return GroqReportService()


@lru_cache
def get_report_service() -> ReportService:
    return ReportService(get_dataset_loader(), llm_service=get_llm_service(), cache=get_report_cache())
