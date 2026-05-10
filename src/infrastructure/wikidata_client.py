from __future__ import annotations

import os
import re
import time
from collections import deque
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
    max_retries: int = 2
    retry_backoff_seconds: float = 2.0

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
            max_retries=_int_from_env("WIKIDATA_MAX_RETRIES", 2),
            retry_backoff_seconds=_float_from_env("WIKIDATA_RETRY_BACKOFF_SECONDS", 2.0),
        )


class WikidataGateway:
    """
    Entity lookup backed by Wikidata.

    Candidate selection uses ``wbsearchentities``. Path search uses a bounded
    breadth-first traversal over item-valued claims returned by ``wbgetentities``.
    """

    def __init__(self, config: WikidataConfig):
        self.config = config
        self.headers = {"User-Agent": self.config.user_agent}
        self._entity_cache: dict[str, dict[str, Any]] = {}
        self._label_cache: dict[str, str] = {}

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
            self._request_json(params, timeout=min(self.config.timeout_seconds, 10.0))
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
        try:
            data = self._request_json(params)
        except requests.RequestException:
            return []
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
        source_id = self._entity_id_from_iri(source_iri)
        target_id = self._entity_id_from_iri(target_iri)
        if not source_id or not target_id or source_id == target_id:
            return None

        max_depth = max(1, int(max_hops))
        queue: deque[tuple[str, list[PathStep]]] = deque([(source_id, [])])
        visited = {source_id}

        while queue:
            current_id, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            neighbors = self._claim_neighbors(current_id, hub_threshold=hub_threshold)
            for predicate, neighbor_id in neighbors:
                if neighbor_id in visited:
                    continue

                step = PathStep(
                    subject_iri=self._entity_iri(current_id),
                    subject_label=self._label_for(current_id),
                    predicate=predicate,
                    object_iri=self._entity_iri(neighbor_id),
                    object_label=self._label_for(neighbor_id),
                )
                next_path = [*path, step]
                if neighbor_id == target_id:
                    return next_path

                visited.add(neighbor_id)
                queue.append((neighbor_id, next_path))

        return None

    def _entity_id_from_iri(self, iri: str) -> str | None:
        match = re.search(r"(Q\d+)(?:$|[/?#])", iri)
        return match.group(1) if match else None

    def _entity_iri(self, entity_id: str) -> str:
        return f"http://www.wikidata.org/entity/{entity_id}"

    def _fetch_entity(self, entity_id: str) -> dict[str, Any]:
        cached = self._entity_cache.get(entity_id)
        if cached is not None:
            return cached

        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "props": "claims|labels",
            "languages": self.config.language,
            "format": "json",
            "origin": "*",
        }
        try:
            data = self._request_json(params)
        except requests.RequestException:
            self._entity_cache[entity_id] = {}
            return {}
        entity = (data.get("entities") or {}).get(entity_id) or {}
        self._entity_cache[entity_id] = entity

        label = ((entity.get("labels") or {}).get(self.config.language) or {}).get("value")
        if label:
            self._label_cache[entity_id] = label
        return entity

    def _label_for(self, entity_id: str) -> str | None:
        if entity_id not in self._label_cache:
            self._fetch_entity(entity_id)
        return self._label_cache.get(entity_id)

    def _claim_neighbors(self, entity_id: str, hub_threshold: int | None = None) -> list[tuple[str, str]]:
        entity = self._fetch_entity(entity_id)
        claims = entity.get("claims") or {}
        neighbors: list[tuple[str, str]] = []

        for property_id, statements in claims.items():
            for statement in statements or []:
                mainsnak = statement.get("mainsnak") or {}
                datavalue = mainsnak.get("datavalue") or {}
                value = datavalue.get("value")
                if not isinstance(value, dict):
                    continue
                neighbor_id = value.get("id")
                if isinstance(neighbor_id, str) and neighbor_id.startswith("Q"):
                    neighbors.append((property_id, neighbor_id))

        if hub_threshold is not None and len(neighbors) > hub_threshold:
            return []
        return neighbors

    def _request_json(self, params: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        attempts = max(0, self.config.max_retries) + 1
        last_exc: requests.RequestException | None = None
        for attempt in range(attempts):
            try:
                response = requests.get(
                    self.config.api_url,
                    params=params,
                    headers=self.headers,
                    timeout=timeout or self.config.timeout_seconds,
                )
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                last_exc = exc
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code != 429 or attempt == attempts - 1:
                    raise
                retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                delay = _float_or_default(retry_after, self.config.retry_backoff_seconds * (attempt + 1))
                time.sleep(delay)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt == attempts - 1:
                    raise
                time.sleep(self.config.retry_backoff_seconds * (attempt + 1))
        if last_exc:
            raise last_exc
        return {}


def _int_from_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_from_env(name: str, default: float) -> float:
    return _float_or_default(os.getenv(name), default)


def _float_or_default(value: str | None, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default
