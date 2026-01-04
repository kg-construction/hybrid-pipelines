from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..domain.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Candidate,
    DisambiguatedMention,
    Mention,
    MentionCandidates,
    MentionExtraction,
    PathEvidence,
    PathStep,
)
from ..infrastructure.neo4j_client import SkosGraphGateway
from ..infrastructure.ollama_client import OllamaClient
from ..infrastructure.prompt_repository import PromptRepository
from ..infrastructure.rdf_builder import RDFBuilder
from ..infrastructure.request_logger import RequestLogger


class KnowledgeGraphService:
    """
    Orchestrates the hybrid pipeline:
    1) LLM-based NER
    2) Candidate selection via SKOS full-text search
    3) Candidate disambiguation via shortest paths + LLM reasoning
    4) RDF graph materialization (Turtle + JSON-LD)
    """

    def __init__(
        self,
        prompt_repository: PromptRepository,
        default_prompt: str,
        default_system_prompt: str,
        path_to_text_prompt: str,
        path_summary_prompt: str,
        candidate_decision_prompt: str,
        ollama_client: Optional[OllamaClient] = None,
        graph_gateway: Optional[SkosGraphGateway] = None,
        rdf_builder: Optional[RDFBuilder] = None,
        rdf_log_path: Optional[Path] = None,
        request_logger: Optional[RequestLogger] = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.default_prompt = default_prompt
        self.default_system_prompt = default_system_prompt
        self.path_to_text_prompt = path_to_text_prompt
        self.path_summary_prompt = path_summary_prompt
        self.candidate_decision_prompt = candidate_decision_prompt
        self.ollama_client = ollama_client
        self.graph_gateway = graph_gateway
        self.rdf_builder = rdf_builder or RDFBuilder()
        self.rdf_log_path = rdf_log_path
        self.request_logger = request_logger

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        start_time = datetime.now(timezone.utc)
        idempotence_key = request.idempotence_key or str(uuid4())
        if not self.ollama_client:
            raise RuntimeError("LLM client is not configured.")
        if not self.graph_gateway:
            raise RuntimeError("Graph gateway is not configured. Configure Neo4j or fallback graph.")

        system_prompt_name = request.system_prompt_name or self.default_system_prompt
        system_prompt_text = self.prompt_repository.load_prompt(system_prompt_name)

        ner_prompt_name = request.prompt_name or self.default_prompt
        ner_prompt_text = self.prompt_repository.load_prompt(ner_prompt_name)
        mentions, ner_generation = self._extract_mentions(
            text=request.text,
            prompt_name=ner_prompt_name,
            prompt_text=ner_prompt_text,
            system_prompt_text=system_prompt_text,
            idempotence_key=idempotence_key,
        )

        candidate_selections = self._select_candidates(mentions, top_k=request.top_k, idempotence_key=idempotence_key)
        paths = self._compute_paths(
            candidate_selections,
            max_hops=request.max_hops,
            hub_threshold=request.hub_threshold,
            idempotence_key=idempotence_key,
        )

        path_sentences, path_generation = self._paths_to_text(paths, system_prompt_text, idempotence_key=idempotence_key)
        summary_text, summary_generation = self._summarize_paths(path_sentences, system_prompt_text, idempotence_key=idempotence_key)
        disambiguation, decision_generations = self._decide_candidates(
            text=request.text,
            mentions=mentions,
            candidate_selections=candidate_selections,
            summary_text=summary_text,
            paths=paths,
            system_prompt_text=system_prompt_text,
            idempotence_key=idempotence_key,
        )

        rdf = self.rdf_builder.build(text=request.text, disambiguated_mentions=disambiguation)

        generation_payload = {
            "ner": ner_generation,
            "path_translation": path_generation,
            "path_summary": summary_generation,
            "decisions": decision_generations,
        }

        end_time = datetime.now(timezone.utc)
        self._log_final_rdf(start_time, end_time, request.text, rdf)

        return AnalyzeResponse(
            text=request.text,
            mentions=mentions,
            candidate_selections=candidate_selections,
            disambiguation=disambiguation,
            rdf=rdf,
            generation=generation_payload,
        )

    def health(self) -> dict:
        neo4j_status = self.graph_gateway.health() if self.graph_gateway else {"status": "unconfigured"}
        llm_status = self.ollama_client.health_check() if self.ollama_client else {"status": "unconfigured"}
        return {"neo4j": neo4j_status, "llm": llm_status}

    def _extract_mentions(
        self,
        text: str,
        prompt_name: str,
        prompt_text: str,
        system_prompt_text: str,
        idempotence_key: str,
    ) -> tuple[MentionExtraction, dict]:
        message = prompt_text.replace("${USER_TEXT}", text)
        self._log_event(idempotence_key, "ollama_request", {"stage": "ner", "prompt_name": prompt_name, "input_text": text})
        generation = self.ollama_client.generate(
            system_prompt=system_prompt_text,
            prompt=message,
            prompt_name=prompt_name,
            input_text=text,
        )
        self._log_event(
            idempotence_key,
            "ollama_response",
            {"stage": "ner", "prompt_name": prompt_name, "response": generation},
        )

        payload = generation.get("response") or "{}"
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("NER stage returned invalid JSON.") from exc

        mentions: list[Mention] = []
        for item in data.get("mentions", []):
            mentions.append(
                Mention(
                    surface=item.get("surface", ""),
                    label=item.get("label"),
                    start=item.get("start"),
                    end=item.get("end"),
                    confidence=item.get("confidence"),
                )
            )
        return MentionExtraction(mentions=mentions), generation

    def _select_candidates(self, mentions: MentionExtraction, top_k: int, idempotence_key: str) -> list[MentionCandidates]:
        selections: list[MentionCandidates] = []
        for mention in mentions.mentions:
            self._log_event(
                idempotence_key,
                "neo4j_request",
                {"stage": "candidate_selection", "surface": mention.surface, "top_k": top_k},
            )
            candidates = self.graph_gateway.search_candidates(surface=mention.surface, limit=top_k)
            self._log_event(
                idempotence_key,
                "neo4j_response",
                {"stage": "candidate_selection", "surface": mention.surface, "candidates": [c.to_dict() for c in candidates]},
            )
            selections.append(MentionCandidates(surface=mention.surface, candidates=candidates))
        return selections

    def _compute_paths(
        self,
        candidate_selections: list[MentionCandidates],
        max_hops: int,
        hub_threshold: int | None,
        idempotence_key: str,
    ) -> list[list[PathStep]]:
        paths: list[list[PathStep]] = []
        for idx, selection in enumerate(candidate_selections):
            for candidate in selection.candidates:
                # Paths to candidates in other mentions
                for other_idx, other in enumerate(candidate_selections):
                    if idx == other_idx:
                        continue
                    for other_candidate in other.candidates:
                        self._log_event(
                            idempotence_key,
                            "neo4j_request",
                            {
                                "stage": "shortest_path",
                                "source": candidate.iri,
                                "target": other_candidate.iri,
                                "max_hops": max_hops,
                                "hub_threshold": hub_threshold,
                            },
                        )
                        path = self.graph_gateway.shortest_path(
                            candidate.iri,
                            other_candidate.iri,
                            max_hops=max_hops,
                            hub_threshold=hub_threshold,
                        )
                        if path:
                            self._log_event(
                                idempotence_key,
                                "neo4j_response",
                                {
                                    "stage": "shortest_path",
                                    "source": candidate.iri,
                                    "target": other_candidate.iri,
                                    "path_length": len(path),
                                },
                            )
                            paths.append(path)

                # Optional intra-mention disambiguation (pairwise within same mention)
                for other_candidate in selection.candidates:
                    if other_candidate.iri == candidate.iri:
                        continue
                    self._log_event(
                        idempotence_key,
                        "neo4j_request",
                        {
                            "stage": "shortest_path",
                            "source": candidate.iri,
                            "target": other_candidate.iri,
                            "max_hops": max_hops,
                            "hub_threshold": hub_threshold,
                        },
                    )
                    path = self.graph_gateway.shortest_path(
                        candidate.iri,
                        other_candidate.iri,
                        max_hops=max_hops,
                        hub_threshold=hub_threshold,
                    )
                    if path:
                        self._log_event(
                            idempotence_key,
                            "neo4j_response",
                            {
                                "stage": "shortest_path",
                                "source": candidate.iri,
                                "target": other_candidate.iri,
                                "path_length": len(path),
                            },
                        )
                        paths.append(path)
        return paths

    def _paths_to_text(self, paths: list[list[PathStep]], system_prompt_text: str, idempotence_key: str) -> tuple[list[str], dict | None]:
        if not paths:
            return [], None

        prompt_text = self.prompt_repository.load_prompt(self.path_to_text_prompt)
        payload = json.dumps([[step.to_dict() for step in path] for path in paths], ensure_ascii=False)
        message = prompt_text.replace("${PATHS_JSON}", payload)
        self._log_event(idempotence_key, "ollama_request", {"stage": "path_to_text", "prompt_name": self.path_to_text_prompt})
        generation = self.ollama_client.generate(
            system_prompt=system_prompt_text,
            prompt=message,
            prompt_name=self.path_to_text_prompt,
        )
        self._log_event(
            idempotence_key,
            "ollama_response",
            {"stage": "path_to_text", "prompt_name": self.path_to_text_prompt, "response": generation},
        )
        response_text = generation.get("response") or "[]"
        try:
            path_sentences = json.loads(response_text)
            if not isinstance(path_sentences, list):
                raise ValueError("Path translation output must be a list of strings.")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("Path translation stage returned invalid JSON.") from exc

        return path_sentences, generation

    def _summarize_paths(self, path_sentences: list[str], system_prompt_text: str, idempotence_key: str) -> tuple[str, dict | None]:
        if not path_sentences:
            return "", None
        prompt_text = self.prompt_repository.load_prompt(self.path_summary_prompt)
        message = prompt_text.replace("${PATH_SENTENCES_JSON}", json.dumps(path_sentences, ensure_ascii=False))
        self._log_event(idempotence_key, "ollama_request", {"stage": "path_summary", "prompt_name": self.path_summary_prompt})
        generation = self.ollama_client.generate(
            system_prompt=system_prompt_text,
            prompt=message,
            prompt_name=self.path_summary_prompt,
        )
        self._log_event(
            idempotence_key,
            "ollama_response",
            {"stage": "path_summary", "prompt_name": self.path_summary_prompt, "response": generation},
        )
        summary = generation.get("response") or ""
        return summary.strip(), generation

    def _decide_candidates(
        self,
        text: str,
        mentions: MentionExtraction,
        candidate_selections: list[MentionCandidates],
        summary_text: str,
        paths: list[list[PathStep]],
        system_prompt_text: str,
        idempotence_key: str,
    ) -> tuple[list[DisambiguatedMention], list[dict]]:
        decisions: list[DisambiguatedMention] = []
        decision_generations: list[dict] = []
        prompt_template = self.prompt_repository.load_prompt(self.candidate_decision_prompt)

        for mention, selection in zip(mentions.mentions, candidate_selections):
            context = self._extract_context(text, mention.start, mention.end)
            candidate_payload = [c.to_dict() for c in selection.candidates]
            message = (
                prompt_template.replace("${SURFACE}", mention.surface)
                .replace("${CONTEXT}", context)
                .replace("${SUMMARY}", summary_text or "")
                .replace("${CANDIDATES_JSON}", json.dumps(candidate_payload, ensure_ascii=False))
            )
            generation = self.ollama_client.generate(
                system_prompt=system_prompt_text,
                prompt=message,
                prompt_name=self.candidate_decision_prompt,
            )
            decision_generations.append(generation)
            self._log_event(
                idempotence_key,
                "ollama_response",
                {"stage": "candidate_decision", "prompt_name": self.candidate_decision_prompt, "response": generation},
            )

            chosen_candidate = self._parse_decision(generation.get("response"), selection)
            decisions.append(
                DisambiguatedMention(
                    surface=mention.surface,
                    label=mention.label,
                    start=mention.start,
                    end=mention.end,
                    confidence=mention.confidence,
                    chosen=chosen_candidate,
                    evidence=PathEvidence(paths=paths, summary=summary_text or None),
                )
            )
        return decisions, decision_generations

    def _parse_decision(self, response_text: str | None, selection: MentionCandidates) -> Candidate | None:
        if not response_text:
            return selection.candidates[0] if selection.candidates else None
        try:
            data = json.loads(response_text)
            iri = data.get("iri")
            label = data.get("label")
            if not iri and selection.candidates:
                return selection.candidates[0]
            return Candidate(iri=iri, label=label or "", score=data.get("score"))
        except json.JSONDecodeError:
            return selection.candidates[0] if selection.candidates else None

    def _extract_context(self, text: str, start: int | None, end: int | None, window: int = 80) -> str:
        if start is None or end is None:
            return text[: window * 2]
        left = max(0, start - window)
        right = min(len(text), end + window)
        return text[left:right]

    def _log_final_rdf(self, start_time: datetime, end_time: datetime, input_text: str, rdf: RDFGraphResult) -> None:
        if not self.rdf_log_path:
            return
        self.rdf_log_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.rdf_log_path.exists()
        with self.rdf_log_path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=["start_time", "end_time", "input_text", "rdf_turtle", "model", "rdf_valid"])
            if write_header:
                writer.writeheader()
            # Heuristic: consider RDF valid if Turtle has at least one triple terminator "."
            rdf_valid = bool(rdf.turtle and "." in rdf.turtle)
            model_name = None
            if self.ollama_client:
                client_config = getattr(self.ollama_client, "config", None)
                model_name = getattr(client_config, "model", None)
            writer.writerow(
                {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "input_text": input_text,
                    "rdf_turtle": rdf.turtle,
                    "model": model_name,
                    "rdf_valid": rdf_valid,
                }
            )

    def _log_event(self, idempotence_key: str, event: str, payload: dict) -> None:
        if self.request_logger:
            self.request_logger.log(idempotence_key=idempotence_key, event=event, payload=payload)
