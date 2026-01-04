
# Analyze

## Endpoint: `POST /analyze`
- Body:
  ```json
  {
    "text": "required",
    "prompt_name": "optional (NER prompt)",
    "system_prompt_name": "optional",
    "top_k": 5,
    "max_hops": 2,
    "hub_threshold": null
  }
  ```
- Behavior (hybrid pipeline):
  1. **LLM NER** using the configured prompt → JSON mentions with offsets/labels.
  2. **Candidate selection**: full-text search in Neo4j SKOS/ACM CCS (top-k per mention).
  3. **Shortest paths** between candidates (Neo4j/GDS or fallback BFS).
  4. **Path-to-text** LLM step, then **path summary** LLM step.
  5. **Candidate decision** LLM step picks the best concept per mention using surface/context/summary.
  6. **RDF build** (Turtle + JSON-LD) with document + mention nodes, SKOS-aligned links.
- Example request:
  ```bash
  curl -X POST http://127.0.0.1:5050/analyze \
    -H "Content-Type: application/json" \
    -d '{"text":"Graph theory underpins network science.","top_k":3,"max_hops":2}'
  ```
- Example response (shape):
  ```json
  {
    "text": "...",
    "mentions": {"mentions":[{"surface":"graph theory","label":"Field",...}]},
    "candidate_selections": [{"surface":"graph theory","candidates":[{"iri":"...","label":"...","score":0.9}]}],
    "disambiguation": [{"surface":"graph theory","chosen":{"iri":"...","label":"..."},"evidence":{"paths":[...],"summary":"..."}}],
    "rdf": {"document_uri":"http://example.org/Document/<hash>","turtle":"...","jsonld":"..."},
    "generation": {"ner": {...}, "path_translation": {...}, "path_summary": {...}, "decisions": [...]}
  }
  ```
