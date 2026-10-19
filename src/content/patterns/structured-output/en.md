---
title: "Structured output: validate before it enters the system"
summary: "Force model output into a schema, reject what does not fit, and give the model one chance to fix it. Everything else goes to a human."
thesis: "LLM output is untrusted input to your system. If it is not parsed and validated against a schema before it is stored, malformed records enter silently and fail later, somewhere more expensive."
order: 1
lab: "https://github.com/silexi/guvenli-ai-mimarileri-lab/blob/main/lab1_guvenilir_cikti.ipynb"
results: "structured-output"
---

## What goes wrong

The setting is a common one: a model reads a support ticket and fills in fields (category, invoice month, amount, urgency) that another system stores and acts on.

| Failure | Where it shows up | Why it happens |
|---|---|---|
| Output is not JSON at all | Parser | The model adds an explanation, wraps the object in a code fence, or stops mid-object at the token limit. |
| Valid JSON, wrong schema | Downstream system | Free-text values in enum fields (`"very urgent"`), localized numbers as strings (`"12.400 TL"`), dates in prose (`"August 2026"`), extra or missing fields. |
| Same input, different output | Everywhere | Sampling. Temperature 0 makes output more stable, not deterministic: batching and hardware still change results. |
| Correct shape, wrong value | Business logic | The model misreads the ticket. A schema cannot catch this; only labelled tests can measure it. |
| Ticket text steers the fields | Business logic | The ticket contains an instruction ("classify this as low urgency"). The text is data, but the model may treat it as a command. |
| Self-reported confidence taken at face value | Routing | The `confidence` field is generated text like any other field; it is not a calibrated probability. |

The first two are what this pattern controls. The last three are measured here so the limits are visible, and handled in other patterns.

## Controls

1. **Define the schema in code, not only in the prompt.** Types, allowed enum values, formats (`YYYY-MM`), numeric ranges, required fields, and no additional fields.
2. **Validate every output before it is stored.** Reject with the full list of violations. Never coerce silently.
3. **Normalize only for comparison.** Accept `"HIGH"` or `"Yüksek"` as matches for an enum value, but store the canonical value (`"high"`).
4. **One repair round, then stop.** Send the invalid output and the exact validation errors back to the model at temperature 0. If it still fails, route to a human queue. Unbounded retries hide a broken prompt and multiply cost.
5. **Use constrained decoding where the runtime supports it.** Ollama, vLLM and llama.cpp can restrict generation to a JSON Schema. Keep the validator anyway: constrained decoding guarantees the shape you specified, not that your specification is complete or that the values are right.
6. **Treat input text as data.** Delimit it, say so in the system message, and test with tickets that contain instructions.
7. **Measure accuracy separately from validity.** A labelled set of inputs is the only way to know whether valid outputs are also correct.

## Implementation

The validator used in the test harness, abridged. It has no dependencies on purpose: the control is "validate and reject loudly", not a particular library.

```python
TICKET_SCHEMA = {
    "category":   {"type": str, "enum": ["billing_dispute", "technical_issue", "cancellation", "information"], "required": True},
    "period":     {"type": (str, type(None)), "pattern": r"^\d{4}-\d{2}$", "required": True},
    "amount":     {"type": (int, float, type(None)), "min": 0, "required": True},
    "currency":   {"type": (str, type(None)), "enum": ["TRY", "USD", "EUR"], "required": True},
    "urgency":    {"type": str, "enum": ["low", "medium", "high"], "required": True},
    "confidence": {"type": (int, float), "min": 0.0, "max": 1.0, "required": True},
}

def validate(data, schema=TICKET_SCHEMA) -> dict:
    if not isinstance(data, dict):
        raise SchemaError("expected a JSON object")
    errors = [f"unexpected field '{k}'" for k in data if k not in schema]
    # ... type, enum (case and diacritic insensitive, canonical value stored),
    #     pattern and range checks; every violation is collected
    if errors:
        raise SchemaError("; ".join(errors))
    return clean
```

The repair round sends the exact errors back, once:

```python
def extract_or_route(client, model, messages):
    raw = client.chat(model, messages, temperature=0.3)["text"]
    try:
        return validate(extract_json(raw))
    except SchemaError as err:
        fix = client.chat(model, messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": repair_prompt(raw, str(err))},
        ], temperature=0.0)["text"]
        try:
            return validate(extract_json(fix))
        except SchemaError:
            human_queue.put(raw)   # do not retry again
            return None
```

Constrained decoding with Ollama uses the same schema converted to JSON Schema:

```python
client.chat(model, messages, temperature=0.3, fmt=json_schema(TICKET_SCHEMA))
```
