#  How to run

## Environment variables
Defaults from `.env`:
- Prompts: 

`DEFAULT_PROMPT_NAME=prompts/ner-acm-ccs.txt`, 

`DEFAULT_SYSTEM_PROMPT_NAME=system/knowledge_graph.txt`, 

`PATH_TO_TEXT_PROMPT_NAME=prompts/path-to-text.txt`, 

`PATH_SUMMARY_PROMPT_NAME=prompts/path-summary.txt`, 

`CANDIDATE_DECISION_PROMPT_NAME=prompts/candidate-decision.txt`
- RDF log: `RDF_LOG_PATH=data/final_rdf_log.csv`
- Ollama: 

`OLLAMA_API_URL=http://localhost:11434`, 

`OLLAMA_MODEL=llama3:8b`, 

`OLLAMA_CSV_PATH=data/ollama_responses.csv` 

plus optional sampling knobs `OLLAMA_SEED`, `OLLAMA_TEMPERATURE`, `OLLAMA_TOP_K`, `OLLAMA_TOP_P`, `OLLAMA_MIN_P`, `OLLAMA_STOP`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT`
- Neo4j: 

`NEO4J_URI=bolt://localhost:7687`, 

`NEO4J_USER=neo4j`, 

`NEO4J_PASSWORD=neo4j`, 

`NEO4J_DATABASE=neo4j`, 

`NEO4J_FULLTEXT_INDEX=skos_fulltext`
- Logs: 

`RDF_LOG_PATH=data/hybrid-responses.csv`, 

`ANALYZE_LOG_PATH=data/analyze_log.jsonl`


## Requirements
- Python >=3.10
- Neo4j

## Setup

### 1. Install Python Dependencies

#### Linux / macOS (bash)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Windows (PowerShell)
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

### 2. Install and Configure Ollama

#### Install Ollama:
- **Windows/Mac**: Download from [https://ollama.ai](https://ollama.ai)

#### Download model:
```bash
ollama pull llama3:8b
```

#### Run model
```
ollama run llama3:8b
```

#### Verify Ollama is running:
```bash
ollama serve
```

### 3. Run Neo4j

1) Install Neo4j Desktop or Server (5.x) from https://neo4j.com/download/
2) Start a database listening on `bolt://localhost:7687` with user/password matching `.env`
3) Install APOC plugin (via Neo4j Desktop or by placing the jar in `plugins/` and enabling it)
4) Run the import SKOS: `python scripts/neo4j_import.py`

## Running the API
```bash
python -m src.app
```
The service listens on `http://127.0.0.1:5050`.
