from __future__ import annotations

import hashlib

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD

from ..domain.models import DisambiguatedMention, RDFGraphResult


class RDFBuilder:
    """
    Materializes RDF (Turtle and JSON-LD) for documents, mentions, and aligned SKOS concepts.
    """

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

        turtle = graph.serialize(format="turtle")
        jsonld = graph.serialize(format="json-ld")

        return RDFGraphResult(document_uri=str(document_uri), turtle=turtle, jsonld=jsonld)
