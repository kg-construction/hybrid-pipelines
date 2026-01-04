# Hybrid Pipeline Knowledge Graph Construction API

Flask API that turns free text (e.g., paper abstracts) into a SKOS-aligned RDF knowledge graph using a hybrid pipeline:
1) **LLM-based NER** (JSON mentions with offsets)
2) **Candidate selection** via Neo4j full-text search over SKOS/ACM CCS
3) **Candidate disambiguation** using shortest paths -> path-to-text -> summarization -> LLM decision
4) **RDF materialization** (Turtle + JSON-LD) with document/mention nodes and SKOS links

## Project Layout
- `src/` — Flask app (DDD-ish layering: controllers/application/domain/infrastructure)
- `prompt/` — system + step-specific prompts (NER, path translation, summary, decision)
- `scripts/` — ACM CCS SKOS import + full-text index creation
- `tests/` — unit, controller, and integration coverage

## Running
```bash
pip install -r requirements.txt
export FLASK_APP=src.app:create_app
flask run --port 5050
```

## Tests
```bash
pytest
```
