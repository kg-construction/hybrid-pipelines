import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from .application.services import KnowledgeGraphService
from .controllers.analyze_controller import create_analyze_blueprint
from .infrastructure import (
    OllamaClient,
    OllamaClientConfig,
    PromptRepository,
    RDFBuilder,
    RequestLogger,
    WikidataConfig,
    WikidataGateway,
)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)

    prompt_repository = PromptRepository()
    env_default_prompt = os.getenv("DEFAULT_PROMPT_NAME", "prompts/ner-acm-ccs.txt")
    env_default_system_prompt = os.getenv("DEFAULT_SYSTEM_PROMPT_NAME", "system/knowledge_graph.txt")
    env_path_to_text_prompt = os.getenv("PATH_TO_TEXT_PROMPT_NAME", "prompts/path-to-text.txt")
    env_path_summary_prompt = os.getenv("PATH_SUMMARY_PROMPT_NAME", "prompts/path-summary.txt")
    env_candidate_decision_prompt = os.getenv("CANDIDATE_DECISION_PROMPT_NAME", "prompts/candidate-decision.txt")

    ollama_config = OllamaClientConfig.from_env()
    ollama_client = OllamaClient(config=ollama_config)
    wikidata_config = WikidataConfig.from_env()
    graph_gateway = WikidataGateway(config=wikidata_config)
    rdf_builder = RDFBuilder()
    rdf_log_path_env = os.getenv("RDF_LOG_PATH")
    rdf_log_path = Path(rdf_log_path_env) if rdf_log_path_env else None
    analyze_log_path_env = os.getenv("ANALYZE_LOG_PATH")
    analyze_log_path = Path(analyze_log_path_env) if analyze_log_path_env else None
    request_logger = RequestLogger(log_path=analyze_log_path) if analyze_log_path else None

    service = KnowledgeGraphService(
        prompt_repository,
        default_prompt=env_default_prompt,
        default_system_prompt=env_default_system_prompt,
        path_to_text_prompt=env_path_to_text_prompt,
        path_summary_prompt=env_path_summary_prompt,
        candidate_decision_prompt=env_candidate_decision_prompt,
        ollama_client=ollama_client,
        graph_gateway=graph_gateway,
        rdf_builder=rdf_builder,
        rdf_log_path=rdf_log_path,
        request_logger=request_logger,
        path_candidate_limit=_int_env("PATH_CANDIDATE_LIMIT", 1),
        path_within_mentions=_bool_env("PATH_WITHIN_MENTIONS", False),
        enable_paths=_bool_env("ENABLE_PATHS", False),
        max_mentions=_int_env("MAX_MENTIONS", 8),
        candidate_decision_mode=os.getenv("CANDIDATE_DECISION_MODE", "first"),
    )
    app.register_blueprint(create_analyze_blueprint(service))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5050, debug=True)
