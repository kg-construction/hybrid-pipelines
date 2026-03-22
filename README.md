# Hybrid Pipeline Knowledge Graph Construction API

Flask API that turns free text into an RDF knowledge graph using a hybrid pipeline:
1. **LLM-based NER** for entity/concept mentions with offsets
2. **Candidate selection** via Wikidata entity search
3. **Candidate disambiguation** using surface/context and optional path evidence
4. **RDF materialization** with document, mention, grounded entity, and assertion nodes

## Process Flow

![Process Flow](docs/figures/process.jpg)

## Project Layout
- `src/` Flask app (controllers/application/domain/infrastructure)
- `prompt/` system + step-specific prompts
- `scripts/` legacy preprocessing/import helpers from the earlier graph-backed pipeline
- `tests/` unit, controller, and integration coverage

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

## Sequence Diagram

![Analysis](docs/figures/analyze.png)

## Configuration

### Prompts and LLM

| Variable | Description | Default/Example |
|---|---|---|
| `DEFAULT_PROMPT_NAME` | Main NER prompt | `prompts/ner-acm-ccs.txt` |
| `DEFAULT_SYSTEM_PROMPT_NAME` | System prompt | `system/knowledge_graph.txt` |
| `PATH_TO_TEXT_PROMPT_NAME` | Path-to-text prompt | `prompts/path-to-text.txt` |
| `PATH_SUMMARY_PROMPT_NAME` | Path summary prompt | `prompts/path-summary.txt` |
| `CANDIDATE_DECISION_PROMPT_NAME` | Candidate decision prompt | `prompts/candidate-decision.txt` |
| `OLLAMA_API_URL` | Ollama API URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM model name | `llama3:8b` |
| `OLLAMA_CSV_PATH` | Path to Ollama response CSV log | `data/ollama_responses.csv` |
| `OLLAMA_SEED` | Seed for reproducibility | `42` |
| `OLLAMA_TEMPERATURE` | Sampling temperature | `0.2` |
| `OLLAMA_TOP_K` | Top-K sampling parameter | `40` |
| `OLLAMA_TOP_P` | Top-P sampling parameter | `0.9` |
| `OLLAMA_MIN_P` | Minimum probability threshold | `0.05` |
| `OLLAMA_STOP` | Stop sequence | empty |
| `OLLAMA_NUM_CTX` | Context window size | unset |
| `OLLAMA_NUM_PREDICT` | Max tokens to predict | unset |

### Wikidata and logs

| Variable | Description | Default/Example |
|---|---|---|
| `WIKIDATA_API_URL` | Wikidata Action API base URL | `https://www.wikidata.org/w/api.php` |
| `WIKIDATA_USER_AGENT` | User-Agent sent to Wikidata | `hybrid-pipelines-kg/1.0` |
| `WIKIDATA_TIMEOUT_SECONDS` | Timeout for Wikidata HTTP calls | `30` |
| `WIKIDATA_LANGUAGE` | Search language used in Wikidata lookup | `en` |
| `RDF_LOG_PATH` | Path to RDF response log | `data/hybrid-responses.csv` |
| `ANALYZE_LOG_PATH` | Path to analysis log | `data/analyze_log.jsonl` |

## Notes
- The active runtime no longer requires Neo4j for candidate lookup.
- The current Wikidata gateway does not compute shortest paths, so path evidence may be empty.
- For sentences such as `Mango is not a fruit from a tree`, the RDF may include an `ex:Assertion` node with `ex:copulaVerb`, `ex:negated`, `ex:subject`, `ex:object`, and `ex:contextEntity`.
