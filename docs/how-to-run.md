# How to run

## Environment variables

Defaults from `.env`:

- Prompts:
  - `DEFAULT_PROMPT_NAME=prompts/ner-acm-ccs.txt`
  - `DEFAULT_SYSTEM_PROMPT_NAME=system/knowledge_graph.txt`
  - `PATH_TO_TEXT_PROMPT_NAME=prompts/path-to-text.txt`
  - `PATH_SUMMARY_PROMPT_NAME=prompts/path-summary.txt`
  - `CANDIDATE_DECISION_PROMPT_NAME=prompts/candidate-decision.txt`
- Ollama:
  - `OLLAMA_API_URL=http://localhost:11434`
  - `OLLAMA_MODEL=llama3:8b`
  - `OLLAMA_CSV_PATH=data/ollama_responses.csv`
  - optional knobs: `OLLAMA_SEED`, `OLLAMA_TEMPERATURE`, `OLLAMA_TOP_K`, `OLLAMA_TOP_P`, `OLLAMA_MIN_P`, `OLLAMA_STOP`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT`
- Wikidata:
  - `WIKIDATA_API_URL=https://www.wikidata.org/w/api.php`
  - `WIKIDATA_USER_AGENT=hybrid-pipelines-kg/1.0`
  - `WIKIDATA_TIMEOUT_SECONDS=30`
  - `WIKIDATA_LANGUAGE=en`
- Logs:
  - `RDF_LOG_PATH=data/hybrid-responses.csv`
  - `ANALYZE_LOG_PATH=data/analyze_log.jsonl`

## Requirements

- Python >= 3.10
- Internet access to reach Wikidata

## Setup

### 1. Install Python dependencies

#### Linux / macOS
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Windows PowerShell
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

### 2. Install and configure Ollama

Install Ollama:
- Windows/Mac: download from <https://ollama.ai>

Download model:
```bash
ollama pull llama3:8b
```

Run model:
```bash
ollama run llama3:8b
```

Verify Ollama service:
```bash
ollama serve
```

### 3. Configure Wikidata access

No local graph database is required for the active runtime. The API queries Wikidata directly through the Action API.

Optional environment variables:
```bash
WIKIDATA_API_URL=https://www.wikidata.org/w/api.php
WIKIDATA_USER_AGENT=hybrid-pipelines-kg/1.0
WIKIDATA_TIMEOUT_SECONDS=30
WIKIDATA_LANGUAGE=en
```

Notes:
- `WIKIDATA_LANGUAGE` controls the search language used for candidate lookup.
- The current gateway does not compute shortest paths, so path evidence may be empty.

## Running the API

```bash
python -m src.app
```

The service listens on `http://127.0.0.1:5050`.

## Example behavior

For input like:
```text
Mango is not a fruit from a tree
```

the RDF may include:
- grounded Wikidata entities for `Mango`, `fruit`, and `tree`
- an `ex:Assertion` node with `ex:copulaVerb "is"`
- `ex:negated true`
- `ex:contextPreposition "from"`
