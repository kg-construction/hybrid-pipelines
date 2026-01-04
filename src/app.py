import os

from dotenv import load_dotenv
from flask import Flask

from .application.services import KnowledgeGraphService
from .controllers.analyze_controller import create_analyze_blueprint
from .infrastructure import (
    Neo4jConfig,
    OllamaClient,
    OllamaClientConfig,
    PromptRepository,
    RDFBuilder,
    SkosGraphGateway,
)


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
    neo4j_config = Neo4jConfig.from_env()
    graph_gateway = SkosGraphGateway(config=neo4j_config)
    rdf_builder = RDFBuilder()

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
    )
    app.register_blueprint(create_analyze_blueprint(service))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5050, debug=True)
