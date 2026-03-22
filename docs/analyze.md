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

## Behavior

1. **LLM NER** extracts mentions with offsets and broad labels.
2. **Heuristic mention completion** on the server adds salient concept mentions that the model may skip, such as common-noun objects after articles or prepositions.
3. **Candidate selection** uses Wikidata `wbsearchentities` for each mention.
4. **Path evidence** is optional. The active Wikidata gateway does not compute shortest paths, so path-to-text and summary may be skipped.
5. **Candidate decision** picks the best entity per mention using surface/context and any available summary.
6. **RDF build** emits document nodes, mention nodes, grounded Wikidata entities, and assertion nodes for supported sentence patterns such as copula + negation.

## Example request

```bash
curl -X POST http://127.0.0.1:5050/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"Mango is not a fruit from a tree.","top_k":3,"max_hops":2}'
```

## Example response shape

```json
{
  "text": "Mango is not a fruit from a tree.",
  "rdf": "rdf.."
}
```

## RDF Notes

- The response body returns only `text` and `rdf`.
- Grounded mentions appear as `ex:Mention/... ex:denotes <http://www.wikidata.org/entity/Q...>`.
- The document node links grounded entities through `ex:hasTopic`.
- For patterns such as `X is not a Y from a Z`, the RDF may include:
  - `ex:Assertion/... a ex:Assertion`
  - `ex:copulaVerb "is"`
  - `ex:negated true`
  - `ex:subject <Q...>`
  - `ex:object <Q...>`
  - `ex:contextEntity <Q...>`
  - `ex:contextPreposition "from"`
