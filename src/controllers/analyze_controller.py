from flask import Blueprint, jsonify, request
import requests

from ..application.services import KnowledgeGraphService
from ..domain.models import AnalyzeRequest


def create_analyze_blueprint(service: KnowledgeGraphService) -> Blueprint:
    blueprint = Blueprint("analyze", __name__)

    @blueprint.route("/health", methods=["GET"])
    def health() -> tuple:
        status = service.health()
        http_status = 200 if status.get("neo4j", {}).get("status") == "ok" and status.get("llm", {}).get("status") == "ok" else 503
        return jsonify(status), http_status

    @blueprint.route("/analyze", methods=["POST"])
    def analyze() -> tuple:
        data = request.get_json(silent=True) or {}
        text = data.get("text")
        if not text:
            return jsonify({"error": "Field 'text' is required."}), 400

        prompt_name = data.get("prompt_name")
        system_prompt_name = data.get("system_prompt_name")
        top_k = data.get("top_k", 5)
        max_hops = data.get("max_hops", 2)
        hub_threshold = data.get("hub_threshold")

        try:
            top_k = int(top_k)
            max_hops = int(max_hops)
            hub_threshold = int(hub_threshold) if hub_threshold is not None else None
        except (TypeError, ValueError):
            return jsonify({"error": "Numeric fields must be integers."}), 400

        if top_k <= 0:
            return jsonify({"error": "Field 'top_k' must be a positive integer."}), 400
        if max_hops <= 0:
            return jsonify({"error": "Field 'max_hops' must be a positive integer."}), 400

        try:
            response = service.analyze(
                AnalyzeRequest(
                    text=text,
                    prompt_name=prompt_name,
                    system_prompt_name=system_prompt_name,
                    top_k=top_k,
                    max_hops=max_hops,
                    hub_threshold=hub_threshold,
                )
            )
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except requests.RequestException as exc:
            return jsonify({"error": "Failed to generate response from model.", "details": str(exc)}), 502
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(response.to_dict()), 200

    return blueprint
