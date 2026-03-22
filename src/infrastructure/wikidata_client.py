from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from ..domain.models import Candidate, PathStep


@dataclass(frozen=True)
class WikidataConfig:
    api_url: str = "https://www.wikidata.org/w/api.php"
    user_agent: str = "hybrid-pipelines-kg/1.0"
    timeout_seconds: float = 30.0
    language: str = "en"

    @classmethod
    def from_env(cls) -> "WikidataConfig":
        timeout_raw = os.getenv("WIKIDATA_TIMEOUT_SECONDS", "30")
        try:
            timeout_seconds = max(1.0, float(timeout_raw))
        except ValueError:
            timeout_seconds = 30.0
        return cls(
            api_url=os.getenv("WIKIDATA_API_URL", "https://www.wikidata.org/w/api.php"),
            user_agent=os.getenv("WIKIDATA_USER_AGENT", "hybrid-pipelines-kg/1.0"),
            timeout_seconds=timeout_seconds,
            language=os.getenv("WIKIDATA_LANGUAGE", "en"),
        )


class WikidataGateway:
    """
    Candidate lookup backed by Wikidata ``wbsearchentities``.
    Path search is unsupported because this pipeline no longer depends on a graph database.
    """

    def __init__(self, config: WikidataConfig):
        self.config = config
        self.headers = {"User-Agent": self.config.user_agent}

    def close(self) -> None:
        return None

    def health(self) -> dict[str, Any]:
        params = {
            "action": "wbsearchentities",
            "search": "graph theory",
            "language": self.config.language,
            "uselang": self.config.language,
            "limit": 1,
            "format": "json",
            "origin": "*",
        }
        try:
            response = requests.get(
                self.config.api_url,
                params=params,
                headers=self.headers,
                timeout=min(self.config.timeout_seconds, 10.0),
            )
            response.raise_for_status()
            return {"status": "ok"}
        except requests.RequestException as exc:
            return {"status": "unavailable", "details": str(exc)}

    def search_candidates(self, surface: str, limit: int = 5) -> list[Candidate]:
        params = {
            "action": "wbsearchentities",
            "search": surface,
            "language": self.config.language,
            "uselang": self.config.language,
            "limit": min(max(int(limit), 1), 50),
            "format": "json",
            "origin": "*",
        }
        response = requests.get(
            self.config.api_url,
            params=params,
            headers=self.headers,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        hits = data.get("search") or []
        return [
            Candidate(
                iri=hit.get("concepturi") or hit.get("url") or f"http://www.wikidata.org/entity/{hit.get('id')}",
                label=hit.get("label") or surface,
                score=hit.get("pageid"),
            )
            for hit in hits[:limit]
            if hit.get("id")
        ]

    def shortest_path(
        self,
        source_iri: str,
        target_iri: str,
        max_hops: int = 2,
        hub_threshold: int | None = None,
    ) -> list[PathStep] | None:
        return None
