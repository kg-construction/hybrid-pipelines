import csv
import json
from pathlib import Path

from src.infrastructure.ollama_client import OllamaClient, OllamaClientConfig, OllamaOptions


def test_generate_sends_payload_and_logs_csv(monkeypatch, tmp_path: Path):
    captured: dict = {}
    sample_response = {
        "model": "llama3:8b",
        "created_at": "2024-01-01T00:00:00Z",
        "response": "Generated KG",
        "thinking": "analysis",
        "done": True,
        "done_reason": "stop",
        "total_duration": 123,
        "load_duration": 10,
        "prompt_eval_count": 11,
        "prompt_eval_duration": 12,
        "eval_count": 13,
        "eval_duration": 14,
        "logprobs": [
            {
                "token": "A",
                "logprob": 123,
                "bytes": [1],
                "top_logprobs": [{"token": "A", "logprob": 123, "bytes": [1]}],
            }
        ],
    }

    def fake_post(url, json=None, **kwargs):  # type: ignore[override]
        captured["url"] = url
        captured["json"] = json

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return sample_response

        return DummyResponse()

    monkeypatch.setattr("src.infrastructure.ollama_client.requests.post", fake_post)

    config = OllamaClientConfig(
        url="http://localhost:11434/api/generate",
        model="llama3:8b",
        csv_path=tmp_path / "logs.csv",
        options=OllamaOptions(seed=7, temperature=0.4, top_k=5, stop="STOP"),
    )
    client = OllamaClient(config=config)

    result = client.generate(system_prompt="Resolved system", prompt="User text", prompt_name="prompt.txt", input_text="User text")

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"]["model"] == "llama3:8b"
    assert captured["json"]["system"] == "Resolved system"
    assert captured["json"]["prompt"] == "User text"
    assert captured["json"]["stream"] is False
    assert captured["json"]["options"] == {"seed": 7, "temperature": 0.4, "top_k": 5, "stop": "STOP"}
    assert result == sample_response

    csv_path = tmp_path / "logs.csv"
    assert csv_path.exists()
    with csv_path.open(encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))
    assert rows[0]["prompt_name"] == "prompt.txt"
    assert rows[0]["input_text"] == "User text"
    assert rows[0]["model"] == "llama3:8b"
    assert rows[0]["response"] == "Generated KG"
    assert json.loads(rows[0]["logprobs"])[0]["token"] == "A"
    assert rows[0]["rdf_valid"] == "False"
    assert rows[0]["rdf_note"] == "Response not recognized as RDF/Turtle."
