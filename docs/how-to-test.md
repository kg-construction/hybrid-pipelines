# How to test

Tests are organized by scope:
- `tests/unit/` for pure function/service tests.
- `tests/controllers/` for Flask blueprints using a test client with stubbed dependencies.
- `tests/infrastructure/` for the Ollama client + CSV logger.
- `tests/integration/` for end-to-end request flows through the app factory, including the mocked generation call and CSV write.

## Testing
```bash
python -m pytest 
```
