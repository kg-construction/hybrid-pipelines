import json
from pathlib import Path

import pytest

from src.app import create_app
from src.infrastructure import prompt_repository
from src.domain.models import Candidate, PathStep


@pytest.fixture()
def prompt_dir(tmp_path: Path):
    p = tmp_path / "prompt"
    p.mkdir()
    (p / "ner.txt").write_text("NER ${USER_TEXT}", encoding="utf-8")
    (p / "system.txt").write_text("System", encoding="utf-8")
    (p / "path.txt").write_text("Path ${PATHS_JSON}", encoding="utf-8")
    (p / "summary.txt").write_text("Summary ${PATH_SENTENCES_JSON}", encoding="utf-8")
    (p / "decision.txt").write_text("Decision ${CANDIDATES_JSON}", encoding="utf-8")
    return p


@pytest.fixture()
def patch_prompt_repo(monkeypatch: pytest.MonkeyPatch, prompt_dir: Path):
    repo_original_init = prompt_repository.PromptRepository.__init__

    def _init(self, prompt_dir=None, _default_dir=prompt_dir):
        chosen_dir = _default_dir if prompt_dir is None else prompt_dir
        repo_original_init(self, prompt_dir=chosen_dir)

    monkeypatch.setattr(prompt_repository.PromptRepository, "__init__", _init)


@pytest.fixture()
def stub_graph(monkeypatch: pytest.MonkeyPatch):
    from src.infrastructure import neo4j_client

    def fake_init(self, config, fallback_graph=None):
        self.config = config
        self.fallback_graph = None

    def fake_search(self, surface: str, limit: int = 5):
        return [Candidate(iri="http://example.org/concept/1", label="Graph Theory", score=0.9)]

    def fake_path(self, source_iri: str, target_iri: str, max_hops: int = 2, hub_threshold=None):
        return [
            PathStep(
                subject_iri=source_iri,
                subject_label="A",
                predicate="related",
                object_iri=target_iri,
                object_label="B",
            )
        ]

    def fake_health(self):
        return {"status": "ok"}

    monkeypatch.setattr(neo4j_client.SkosGraphGateway, "__init__", fake_init)
    monkeypatch.setattr(neo4j_client.SkosGraphGateway, "search_candidates", fake_search)
    monkeypatch.setattr(neo4j_client.SkosGraphGateway, "shortest_path", fake_path)
    monkeypatch.setattr(neo4j_client.SkosGraphGateway, "health", fake_health)


@pytest.fixture()
def stub_ollama(monkeypatch: pytest.MonkeyPatch):
    from src.infrastructure import ollama_client

    def fake_generate(self, system_prompt: str, prompt: str, prompt_name: str | None = None, input_text: str | None = None):
        if prompt_name == "ner.txt":
            return {"response": json.dumps({"mentions": [{"surface": "graph theory", "label": "Field", "start": 0, "end": 12, "confidence": 0.9}]})}
        if prompt_name == "path.txt":
            return {"response": json.dumps(["A relates to B"])}
        if prompt_name == "summary.txt":
            return {"response": "Summary text"}
        if prompt_name == "decision.txt":
            return {"response": json.dumps({"iri": "http://example.org/concept/1", "label": "Graph Theory", "score": 0.9})}
        return {"response": "{}"}

    def fake_health(self):
        return {"status": "ok"}

    monkeypatch.setattr(ollama_client.OllamaClient, "generate", fake_generate)
    monkeypatch.setattr(ollama_client.OllamaClient, "health_check", fake_health)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, prompt_dir: Path, patch_prompt_repo, stub_graph, stub_ollama):
    monkeypatch.setenv("DEFAULT_PROMPT_NAME", "ner.txt")
    monkeypatch.setenv("DEFAULT_SYSTEM_PROMPT_NAME", "system.txt")
    monkeypatch.setenv("PATH_TO_TEXT_PROMPT_NAME", "path.txt")
    monkeypatch.setenv("PATH_SUMMARY_PROMPT_NAME", "summary.txt")
    monkeypatch.setenv("CANDIDATE_DECISION_PROMPT_NAME", "decision.txt")
    monkeypatch.setenv("OLLAMA_API_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3:8b")

    app = create_app()
    app.config.update({"TESTING": True})

    with app.test_client() as client:
        yield client


def test_analyze_request_flow(client):
    payload = {"text": "graph theory is important", "prompt_name": "ner.txt", "system_prompt_name": "system.txt", "top_k": 1}
    resp = client.post("/analyze", data=json.dumps(payload), content_type="application/json")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mentions"]["mentions"][0]["surface"] == "graph theory"
    assert data["candidate_selections"][0]["candidates"][0]["iri"] == "http://example.org/concept/1"
    assert "hasTopic" in data["rdf"]["turtle"]


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["neo4j"]["status"] == "ok"
    assert data["llm"]["status"] == "ok"
