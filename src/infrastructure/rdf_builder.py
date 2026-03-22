from __future__ import annotations

import hashlib
import re

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD

from ..domain.models import DisambiguatedMention, RDFGraphResult


class RDFBuilder:
    """
    Materializes RDF (Turtle and JSON-LD) for documents, mentions, and aligned SKOS concepts.
    """

    _COPULA_PATTERN = re.compile(
        r"\b(?P<subject>[A-Za-z][A-Za-z-]*)\s+"
        r"(?P<verb>am|is|are|was|were)\s+"
        r"(?P<negation>not\s+)?"
        r"(?:(?:a|an|the)\s+)?"
        r"(?P<object>[A-Za-z][A-Za-z-]*)"
        r"(?:\s+(?P<prep>from|of|in|on|at|to)\s+(?:(?:a|an|the)\s+)?(?P<context>[A-Za-z][A-Za-z-]*))?",
        flags=re.IGNORECASE,
    )

    def __init__(self, base_namespace: str = "http://example.org/"):
        self.base_namespace = base_namespace if base_namespace.endswith("/") else f"{base_namespace}/"
        self.ex = Namespace(self.base_namespace)
        self.skos = Namespace("http://www.w3.org/2004/02/skos/core#")

    def build(
        self,
        text: str,
        disambiguated_mentions: list[DisambiguatedMention],
    ) -> RDFGraphResult:
        graph = Graph()
        graph.bind("ex", self.ex)
        graph.bind("skos", self.skos)
        graph.bind("rdfs", RDFS)

        doc_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        document_uri = URIRef(f"{self.ex}Document/{doc_hash}")
        graph.add((document_uri, RDF.type, URIRef(f"{self.ex}Document")))

        for idx, mention in enumerate(disambiguated_mentions):
            mention_uri = URIRef(f"{self.ex}Mention/{doc_hash}/{idx}")
            graph.add((mention_uri, RDF.type, URIRef(f"{self.ex}Mention")))
            graph.add((mention_uri, RDFS.label, Literal(mention.surface)))
            graph.add((document_uri, URIRef(f"{self.ex}mentions"), mention_uri))

            if mention.evidence and mention.evidence.summary:
                graph.add((mention_uri, URIRef(f"{self.ex}pathSummary"), Literal(mention.evidence.summary)))

            if mention.chosen:
                concept_uri = URIRef(mention.chosen.iri)
                graph.add((mention_uri, URIRef(f"{self.ex}denotes"), concept_uri))
                graph.add((document_uri, URIRef(f"{self.ex}hasTopic"), concept_uri))
                if mention.chosen.label:
                    graph.add((concept_uri, RDFS.label, Literal(mention.chosen.label)))

            # Offsets (optional)
            if mention.start is not None:
                graph.add((mention_uri, URIRef(f"{self.ex}startOffset"), Literal(int(mention.start), datatype=XSD.integer)))
            if mention.end is not None:
                graph.add((mention_uri, URIRef(f"{self.ex}endOffset"), Literal(int(mention.end), datatype=XSD.integer)))

        mention_entities = self._mention_entity_index(disambiguated_mentions)
        for idx, assertion in enumerate(self._extract_assertions(text, mention_entities)):
            assertion_uri = URIRef(f"{self.ex}Assertion/{doc_hash}/{idx}")
            graph.add((assertion_uri, RDF.type, URIRef(f"{self.ex}Assertion")))
            graph.add((document_uri, URIRef(f"{self.ex}asserts"), assertion_uri))
            graph.add((assertion_uri, URIRef(f"{self.ex}copulaVerb"), Literal(assertion["verb"])))
            graph.add((assertion_uri, URIRef(f"{self.ex}negated"), Literal(bool(assertion["negated"]), datatype=XSD.boolean)))
            graph.add((assertion_uri, URIRef(f"{self.ex}surfaceText"), Literal(assertion["surface_text"])))

            subject_uri = assertion.get("subject_uri")
            object_uri = assertion.get("object_uri")
            context_uri = assertion.get("context_uri")
            if subject_uri:
                graph.add((assertion_uri, URIRef(f"{self.ex}subject"), URIRef(subject_uri)))
            if object_uri:
                graph.add((assertion_uri, URIRef(f"{self.ex}object"), URIRef(object_uri)))
            if context_uri:
                graph.add((assertion_uri, URIRef(f"{self.ex}contextEntity"), URIRef(context_uri)))
                graph.add((assertion_uri, URIRef(f"{self.ex}contextPreposition"), Literal(assertion["prep"])))

        turtle = graph.serialize(format="turtle")
        jsonld = graph.serialize(format="json-ld")

        return RDFGraphResult(document_uri=str(document_uri), turtle=turtle, jsonld=jsonld)

    def _mention_entity_index(self, disambiguated_mentions: list[DisambiguatedMention]) -> dict[str, str]:
        index: dict[str, str] = {}
        for mention in disambiguated_mentions:
            if mention.chosen and mention.surface:
                index[mention.surface.casefold()] = mention.chosen.iri
        return index

    def _extract_assertions(self, text: str, mention_entities: dict[str, str]) -> list[dict]:
        assertions: list[dict] = []
        for match in self._COPULA_PATTERN.finditer(text):
            subject = match.group("subject")
            obj = match.group("object")
            context = match.group("context")
            assertions.append(
                {
                    "subject_uri": mention_entities.get(subject.casefold()),
                    "object_uri": mention_entities.get(obj.casefold()),
                    "context_uri": mention_entities.get(context.casefold()) if context else None,
                    "verb": match.group("verb").lower(),
                    "negated": bool(match.group("negation")),
                    "prep": match.group("prep").lower() if match.group("prep") else None,
                    "surface_text": match.group(0),
                }
            )
        return assertions
