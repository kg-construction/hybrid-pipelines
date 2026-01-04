import json
from pathlib import Path

from src.application.services import KnowledgeGraphService
from src.domain.models import AnalyzeRequest, Candidate, PathStep
from src.infrastructure.rdf_builder import RDFBuilder
from src.infrastructure.prompt_repository import PromptRepository


class DummyPromptRepo(PromptRepository):
    def __init__(self, prompts: dict[str, str]):
        super().__init__(prompt_dir=Path("unused"))
        self.prompts = prompts

    def load_prompt(self, prompt_name: str) -> str:  # type: ignore[override]
        return self.prompts[prompt_name]


class StubOllamaClient:
    def __init__(self):
        self.calls = []

    def generate(self, system_prompt: str, prompt: str, prompt_name: str | None = None, input_text: str | None = None):
        self.calls.append({"system": system_prompt, "prompt_name": prompt_name, "prompt": prompt, "input_text": input_text})
        if prompt_name == "ner":
            return {"response": json.dumps({"mentions": [{"surface": "graph theory", "label": "Field", "start": 0, "end": 12, "confidence": 0.9}]})}
        if prompt_name == "path":
            return {"response": json.dumps(["A relates to B"])}
        if prompt_name == "summary":
            return {"response": "Summary of paths"}
        if prompt_name == "decision":
            return {"response": json.dumps({"iri": "http://example.org/concept/1", "label": "Graph Theory", "score": 0.95})}
        return {"response": "{}"}

    def health_check(self):
        return {"status": "ok"}


class StubGraphGateway:
    def __init__(self):
        self.search_calls = []
        self.path_calls = []

    def search_candidates(self, surface: str, limit: int = 5):
        self.search_calls.append({"surface": surface, "limit": limit})
        return [
            Candidate(iri="http://example.org/concept/1", label="Graph Theory", score=0.9),
            Candidate(iri="http://example.org/concept/2", label="Networks", score=0.8),
        ]

    def shortest_path(self, source_iri: str, target_iri: str, max_hops: int = 2, hub_threshold=None):
        self.path_calls.append({"source": source_iri, "target": target_iri, "max_hops": max_hops, "hub_threshold": hub_threshold})
        return [
            PathStep(
                subject_iri=source_iri,
                subject_label="A",
                predicate="related",
                object_iri=target_iri,
                object_label="B",
            )
        ]

    def health(self):
        return {"status": "ok"}


def test_analyze_pipeline_builds_rdf():
    prompts = {
        "ner": "NER ${USER_TEXT}",
        "system": "System prompt",
        "path": "Paths ${PATHS_JSON}",
        "summary": "Summary ${PATH_SENTENCES_JSON}",
        "decision": "Decision ${CANDIDATES_JSON}",
    }
    repo = DummyPromptRepo(prompts=prompts)
    ollama = StubOllamaClient()
    graph = StubGraphGateway()
    rdf_builder = RDFBuilder(base_namespace="http://example.org/")

    service = KnowledgeGraphService(
        prompt_repository=repo,
        default_prompt="ner",
        default_system_prompt="system",
        path_to_text_prompt="path",
        path_summary_prompt="summary",
        candidate_decision_prompt="decision",
        ollama_client=ollama,
        graph_gateway=graph,
        rdf_builder=rdf_builder,
    )

    request = AnalyzeRequest(text="graph theory advances", prompt_name="ner", system_prompt_name="system", top_k=2, max_hops=2)
    response = service.analyze(request)

    assert response.mentions.mentions[0].surface == "graph theory"
    assert response.candidate_selections[0].candidates[0].iri == "http://example.org/concept/1"
    assert response.disambiguation[0].chosen.label == "Graph Theory"
    assert "hasTopic" in response.rdf.turtle
    assert response.generation["ner"]["response"]
    assert graph.search_calls
    assert graph.path_calls
