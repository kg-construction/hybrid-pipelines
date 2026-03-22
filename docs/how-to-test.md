# How to test

Tests are organized by scope:
- `tests/unit/` for service and RDF-building behavior
- `tests/controllers/` for Flask blueprints using a test client with stubbed dependencies
- `tests/infrastructure/` for the Ollama client and CSV logger
- `tests/integration/` for end-to-end request flows through the app factory with mocked Wikidata/Ollama calls

## Running tests

```bash
python -m pytest
```

## Notes

- The automated tests do not require Neo4j.
- Integration tests stub the Wikidata gateway; they do not call the live Wikidata API.
