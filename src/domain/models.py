from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnalyzeRequest:
    text: str
    prompt_name: str | None = None
    system_prompt_name: str | None = None
    top_k: int = 5
    max_hops: int = 2
    hub_threshold: int | None = None
    idempotence_key: str | None = None


@dataclass(frozen=True)
class Mention:
    surface: str
    label: str | None
    start: int | None
    end: int | None
    confidence: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class MentionExtraction:
    mentions: list[Mention] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"mentions": [mention.to_dict() for mention in self.mentions]}


@dataclass(frozen=True)
class Candidate:
    iri: str
    label: str
    score: float | None

    def to_dict(self) -> dict[str, Any]:
        return {"iri": self.iri, "label": self.label, "score": self.score}


@dataclass(frozen=True)
class MentionCandidates:
    surface: str
    candidates: list[Candidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"surface": self.surface, "candidates": [c.to_dict() for c in self.candidates]}


@dataclass(frozen=True)
class PathStep:
    subject_iri: str
    subject_label: str | None
    predicate: str
    object_iri: str
    object_label: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_iri": self.subject_iri,
            "subject_label": self.subject_label,
            "predicate": self.predicate,
            "object_iri": self.object_iri,
            "object_label": self.object_label,
        }


@dataclass(frozen=True)
class PathEvidence:
    paths: list[list[PathStep]] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "paths": [[step.to_dict() for step in path] for path in self.paths],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class DisambiguatedMention:
    surface: str
    chosen: Candidate | None
    evidence: PathEvidence
    label: str | None = None
    start: int | None = None
    end: int | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "chosen": self.chosen.to_dict() if self.chosen else None,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class RDFGraphResult:
    document_uri: str
    turtle: str
    jsonld: str

    def to_dict(self) -> dict[str, Any]:
        return {"document_uri": self.document_uri, "turtle": self.turtle, "jsonld": self.jsonld}


@dataclass(frozen=True)
class AnalyzeResponse:
    text: str
    mentions: MentionExtraction
    candidate_selections: list[MentionCandidates]
    disambiguation: list[DisambiguatedMention]
    rdf: RDFGraphResult
    generation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "mentions": self.mentions.to_dict(),
            "candidate_selections": [c.to_dict() for c in self.candidate_selections],
            "disambiguation": [d.to_dict() for d in self.disambiguation],
            "rdf": self.rdf.to_dict(),
            "generation": self.generation,
        }
