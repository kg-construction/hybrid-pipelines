from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests import Response


def _int_from_env(name: str) -> int | None:
    value = os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _float_from_env(name: str) -> float | None:
    value = os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _is_likely_turtle(text: str) -> bool:
    """Lightweight heuristic to flag RDF/Turtle-like responses."""
    if not text or not isinstance(text, str):
        return False
    return "@prefix" in text and (";" in text or "." in text)


@dataclass(frozen=True)
class OllamaOptions:
    seed: int | None = None
    temperature: float | None = None
    top_k: int | None = None
    top_p: float | None = None
    min_p: float | None = None
    stop: str | None = None
    num_ctx: int | None = None
    num_predict: int | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.seed is not None:
            payload["seed"] = self.seed
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.top_k is not None:
            payload["top_k"] = self.top_k
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.min_p is not None:
            payload["min_p"] = self.min_p
        if self.stop:
            payload["stop"] = self.stop
        if self.num_ctx is not None:
            payload["num_ctx"] = self.num_ctx
        if self.num_predict is not None:
            payload["num_predict"] = self.num_predict
        return payload


@dataclass(frozen=True)
class OllamaClientConfig:
    url: str
    model: str
    csv_path: Path
    options: OllamaOptions

    @classmethod
    def from_env(cls) -> "OllamaClientConfig":
        url = os.getenv("OLLAMA_API_URL")
        model = os.getenv("OLLAMA_MODEL")
        csv_path = Path(os.getenv("OLLAMA_CSV_PATH"))
        options = OllamaOptions(
            seed=_int_from_env("OLLAMA_SEED"),
            temperature=_float_from_env("OLLAMA_TEMPERATURE"),
            top_k=_int_from_env("OLLAMA_TOP_K"),
            top_p=_float_from_env("OLLAMA_TOP_P"),
            min_p=_float_from_env("OLLAMA_MIN_P"),
            stop=os.getenv("OLLAMA_STOP"),
            num_ctx=_int_from_env("OLLAMA_NUM_CTX"),
            num_predict=_int_from_env("OLLAMA_NUM_PREDICT"),
        )
        return cls(
            url=url,
            model=model,
            csv_path=csv_path,
            options=options,
        )


class OllamaClient:
    """
    Thin HTTP client for Ollama's /api/generate endpoint with CSV logging.
    """

    def __init__(self, config: OllamaClientConfig):
        self.config = config

    def generate(
        self,
        system_prompt: str,
        prompt: str,
        prompt_name: str | None = None,
        input_text: str | None = None,
    ) -> dict[str, Any]:
        base_url = self.config.url.rstrip("/")
        target_url = base_url if base_url.endswith("/api/generate") else f"{base_url}/api/generate"

        payload: dict[str, Any] = {
            "model": self.config.model,
            "system": system_prompt,
            "prompt": prompt,
            # Disable streaming to ensure we receive a single JSON object we can log.
            "stream": False,
        }
        options_payload = self.config.options.to_payload()
        if options_payload:
            payload["options"] = options_payload

        response = requests.post(target_url, json=payload)
        response.raise_for_status()
        data = self._parse_response(response)
        self._log_to_csv(data, prompt_name=prompt_name, input_text=input_text)
        return data

    def _parse_response(self, response: Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError("Invalid JSON response from generation API") from exc

    def health_check(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.config.url}/api/tags", timeout=5)
            response.raise_for_status()
            return {"status": "ok"}
        except Exception as exc:  # pragma: no cover - defensive guard
            return {"status": "unavailable", "details": str(exc)}

    def _log_to_csv(self, data: dict[str, Any], prompt_name: str | None, input_text: str | None) -> None:
        csv_path = self.config.csv_path
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "prompt_name",
            "input_text",
            "model",
            "created_at",
            "response",
            "thinking",
            "done",
            "done_reason",
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
            "logprobs",
            "rdf_valid",
            "rdf_note",
        ]
        write_header = not csv_path.exists()
        response_text = data.get("response")
        rdf_valid = _is_likely_turtle(response_text)
        rdf_note = "" if rdf_valid else "Response not recognized as RDF/Turtle."
        with csv_path.open("a", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(
                {
                    "prompt_name": prompt_name,
                    "input_text": input_text,
                    "model": data.get("model"),
                    "created_at": data.get("created_at"),
                    "response": data.get("response"),
                    "thinking": data.get("thinking"),
                    "done": data.get("done"),
                    "done_reason": data.get("done_reason"),
                    "total_duration": data.get("total_duration"),
                    "load_duration": data.get("load_duration"),
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "prompt_eval_duration": data.get("prompt_eval_duration"),
                    "eval_count": data.get("eval_count"),
                    "eval_duration": data.get("eval_duration"),
                    "logprobs": json.dumps(data.get("logprobs")),
                    "rdf_valid": rdf_valid,
                    "rdf_note": rdf_note,
                }
            )
