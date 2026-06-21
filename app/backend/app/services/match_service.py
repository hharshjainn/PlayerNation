"""
Business logic for listing matches (Phase 6).

Thin today -- it's a pass-through to the Phase 1 data access layer -- but
having it as its own service gives routes a clean dependency to call
rather than reaching into `DatasetLoader` directly, and a seam to add
filtering/pagination later without touching the route.
"""
from __future__ import annotations

from app.data.dataset_loader import DatasetLoader
from app.data.models import MatchSummary


class MatchService:
    def __init__(self, loader: DatasetLoader) -> None:
        self.loader = loader

    def list_matches(self) -> list[MatchSummary]:
        return self.loader.list_matches()
