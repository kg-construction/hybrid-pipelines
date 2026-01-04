import json
from flask import Flask

from src.controllers.analyze_controller import create_analyze_blueprint
from src.domain.models import (
    AnalyzeResponse,
    Candidate,
    DisambiguatedMention,
    Mention,
    MentionCandidates,
    MentionExtraction,
    PathEvidence,
    RDFGraphResult,
)


class StubService:
    def __init__(self):
        self.called_with = None

    def analyze(self, request):
        self.called_with = request
        mentions = MentionExtraction(mentions=[Mention(surface="AI", label="Field", start=0, end=2, confidence=0.9)])
        candidates = [MentionCandidates(surface="AI", candidates=[Candidate(iri="http://example.org/ai", label="Artificial Intelligence", score=0.95)])]
        disambiguation = [
            DisambiguatedMention(
                surface="AI",
                label="Field",
                start=0,
                end=2,
                confidence=0.9,
                chosen=Candidate(iri="http://example.org/ai", label="Artificial Intelligence", score=0.95),
                evidence=PathEvidence(paths=[], summary="summary"),
            )
        ]
        rdf = RDFGraphResult(
            document_uri="http://example.org/Document/123",
            turtle="@prefix ex: <http://example.org/> .",
            jsonld="{}",
        )
        return AnalyzeResponse(
            text=request.text,
            mentions=mentions,
            candidate_selections=candidates,
            disambiguation=disambiguation,
            rdf=rdf,
            generation={"ner": {"response": "{}"}},
        )

    def health(self):
        return {"neo4j": {"status": "ok"}, "llm": {"status": "ok"}}


def make_client():
    service = StubService()
    app = Flask(__name__)
    app.register_blueprint(create_analyze_blueprint(service))
    app.config.update({"TESTING": True})
    return app.test_client(), service


def test_health_ok():
    client, _ = make_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["neo4j"]["status"] == "ok"
    assert data["llm"]["status"] == "ok"


def test_analyze_happy_path():
    client, service = make_client()
    payload = {"text": "AI improves science", "prompt_name": "ner", "top_k": 3}
    resp = client.post("/analyze", data=json.dumps(payload), content_type="application/json")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mentions"]["mentions"][0]["surface"] == "AI"
    assert data["rdf"]["turtle"].startswith("@prefix")
    assert service.called_with.top_k == 3


def test_analyze_missing_text_returns_400():
    client, _ = make_client()
    resp = client.post("/analyze", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400
    assert "text" in resp.get_json()["error"]


def test_analyze_validates_numeric_fields():
    client, _ = make_client()
    resp = client.post("/analyze", data=json.dumps({"text": "abc", "top_k": 0}), content_type="application/json")
    assert resp.status_code == 400
