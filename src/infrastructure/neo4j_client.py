from __future__ import annotations

import asyncio
import inspect
import os
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

from neo4j import Driver, GraphDatabase

# Neo4j <6 uses asyncio.iscoroutinefunction, which is deprecated in Python 3.14+.
# Patch it to the recommended inspect.iscoroutinefunction to avoid runtime warnings.
asyncio.iscoroutinefunction = inspect.iscoroutinefunction

from ..domain.models import Candidate, PathStep


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str | None
    user: str | None
    password: str | None
    database: str | None
    fulltext_index: str = "skos_fulltext"

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        return cls(
            uri=os.getenv("NEO4J_URI"),
            user=os.getenv("NEO4J_USER"),
            password=os.getenv("NEO4J_PASSWORD"),
            database=os.getenv("NEO4J_DATABASE"),
            fulltext_index=os.getenv("NEO4J_FULLTEXT_INDEX", "skos_fulltext"),
        )


class SkosGraphGateway:
    """
    Provides SKOS-aware lookups and path queries against Neo4j.
    Falls back to an in-memory adjacency map (dict[str, list[tuple[predicate, iri, label]]])
    when Neo4j is not configured.
    """

    def __init__(self, config: Neo4jConfig, fallback_graph: dict[str, list[tuple[str, str, str]]] | None = None):
        self.config = config
        self.fallback_graph = fallback_graph
        self.driver: Driver | None = None
        if config.uri and config.user and config.password:
            self.driver = GraphDatabase.driver(config.uri, auth=(config.user, config.password))

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def health(self) -> dict[str, Any]:
        if not self.driver:
            return {"status": "unconfigured", "details": "Neo4j credentials not provided."}
        try:
            with self.driver.session(database=self.config.database) as session:
                result = session.run("RETURN 1 AS ok").single()
            if result and result["ok"] == 1:
                return {"status": "ok"}
            return {"status": "degraded", "details": "Health query returned unexpected result."}
        except Exception as exc:  # pragma: no cover - defensive guard
            return {"status": "unavailable", "details": str(exc)}

    def search_candidates(self, surface: str, limit: int = 5) -> list[Candidate]:
        if self.driver:
            return self._search_candidates_neo4j(surface=surface, limit=limit)
        if self.fallback_graph is not None:
            return self._search_candidates_fallback(surface=surface, limit=limit)
        raise RuntimeError("No graph backend configured for candidate selection.")

    def shortest_path(
        self,
        source_iri: str,
        target_iri: str,
        max_hops: int = 2,
        hub_threshold: int | None = None,
    ) -> list[PathStep] | None:
        if self.driver:
            return self._shortest_path_neo4j(source_iri, target_iri, max_hops=max_hops, hub_threshold=hub_threshold)
        if self.fallback_graph is not None:
            return self._shortest_path_fallback(source_iri, target_iri, max_hops=max_hops)
        return None

    def _search_candidates_neo4j(self, surface: str, limit: int) -> list[Candidate]:
        query = """
        CALL db.index.fulltext.queryNodes($index, $term) YIELD node, score
        RETURN coalesce(node.uri, node.iri, toString(id(node))) AS iri,
               coalesce(node.prefLabel, node.altLabel, node.label, []) AS labels,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        with self.driver.session(database=self.config.database) as session:  # type: ignore[arg-type]
            records = session.run(query, {"index": self.config.fulltext_index, "term": surface, "limit": limit})
            candidates: list[Candidate] = []
            for record in records:
                labels: Iterable[str] = record["labels"] or []
                first_label = None
                for lbl in labels:
                    first_label = lbl
                    break
                candidates.append(Candidate(iri=record["iri"], label=first_label or surface, score=record["score"]))
            return candidates

    def _search_candidates_fallback(self, surface: str, limit: int) -> list[Candidate]:
        # Fallback: naive lexical match over the in-memory graph nodes.
        matches: list[Candidate] = []
        for iri, relations in self.fallback_graph.items():
            for _, target_iri, target_label in relations:
                if surface.lower() in target_label.lower():
                    matches.append(Candidate(iri=target_iri, label=target_label, score=1.0))
        return matches[:limit]

    def _shortest_path_neo4j(
        self,
        source_iri: str,
        target_iri: str,
        max_hops: int,
        hub_threshold: int | None = None,
    ) -> list[PathStep] | None:
        hops = max(1, int(max_hops))
        query = f"""
        MATCH (source {{uri: $source_iri}}) 
        MATCH (target {{uri: $target_iri}})
        MATCH p=shortestPath((source)-[:broader|narrower|related*..{hops}]-(target))
        WITH p, nodes(p) AS ns, relationships(p) AS rels
        UNWIND ns AS node
        WITH p, ns, rels, node, COUNT {{ (node)-[]-() }} AS node_degree
        WITH p, ns, rels, collect(node_degree) AS degrees
        WHERE $hub_threshold IS NULL OR ALL(deg IN degrees WHERE deg <= $hub_threshold)
        RETURN ns AS nodes, rels AS rels
        LIMIT 1
        """
        with self.driver.session(database=self.config.database) as session:  # type: ignore[arg-type]
            record = session.run(
                query,
                {
                    "source_iri": source_iri,
                    "target_iri": target_iri,
                    "max_hops": max_hops,
                    "hub_threshold": hub_threshold,
                },
            ).single()
            if not record:
                return None
            nodes = record["nodes"]
            rels = record["rels"]
            steps: list[PathStep] = []
            for idx, rel in enumerate(rels):
                subject_node = nodes[idx]
                object_node = nodes[idx + 1]
                steps.append(
                    PathStep(
                        subject_iri=subject_node.get("uri") or subject_node.get("iri") or str(subject_node.id),
                        subject_label=self._label_from_node(subject_node),
                        predicate=rel.type,
                        object_iri=object_node.get("uri") or object_node.get("iri") or str(object_node.id),
                        object_label=self._label_from_node(object_node),
                    )
                )
            return steps

    def _label_from_node(self, node: Any) -> str | None:
        for key in ("prefLabel", "altLabel", "label"):
            if key in node and node[key]:
                labels = node[key]
                if isinstance(labels, (list, tuple)):
                    return labels[0]
                return labels
        return None

    def _shortest_path_fallback(self, source_iri: str, target_iri: str, max_hops: int) -> list[PathStep] | None:
        if source_iri not in self.fallback_graph or target_iri not in self.fallback_graph:
            return None
        visited = set()
        queue: deque[tuple[str, list[PathStep]]] = deque()
        queue.append((source_iri, []))

        while queue:
            current, path = queue.popleft()
            if len(path) > max_hops:
                continue
            if current == target_iri:
                return path

            if current in visited:
                continue
            visited.add(current)

            for predicate, next_iri, next_label in self.fallback_graph.get(current, []):
                next_step = PathStep(
                    subject_iri=current,
                    subject_label=None,
                    predicate=predicate,
                    object_iri=next_iri,
                    object_label=next_label,
                )
                queue.append((next_iri, path + [next_step]))
        return None
