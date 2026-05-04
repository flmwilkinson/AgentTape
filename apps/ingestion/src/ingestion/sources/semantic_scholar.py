"""Deprecated — citation lookups moved to ``citations.py``.

The new module supports OpenAlex (no key, just a mailto contact) and
falls back to Semantic Scholar when only its API key is set. This
file remains as a re-export so any out-of-tree import keeps working.
"""
from __future__ import annotations

from ingestion.sources.citations import ArxivCitationsIngestor

__all__ = ["ArxivCitationsIngestor"]
