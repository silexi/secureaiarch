"""Schema validation and repair prompt for the structured-output pattern.

Deliberately small and dependency free: the point is the control (validate before the
output enters the system, reject loudly), not a validation library.
"""
from __future__ import annotations

import json
import re

FOLD = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


class SchemaError(ValueError):
    pass


def fold(v):
    """Case and Turkish-diacritic insensitive form used only for comparison."""
    return v.translate(FOLD).lower().strip() if isinstance(v, str) else v


TICKET_SCHEMA = {
    "category": {"type": str, "enum": ["billing_dispute", "technical_issue", "cancellation", "information"], "required": True},
    "period": {"type": (str, type(None)), "pattern": r"^\d{4}-\d{2}$", "required": True},
    "amount": {"type": (int, float, type(None)), "min": 0, "required": True},
    "currency": {"type": (str, type(None)), "enum": ["TRY", "USD", "EUR"], "required": True},
    "urgency": {"type": str, "enum": ["low", "medium", "high"], "required": True},
    "confidence": {"type": (int, float), "min": 0.0, "max": 1.0, "required": True},
}


def validate(data, schema=TICKET_SCHEMA) -> dict:
    """Returns a clean dict with canonical enum values, or raises SchemaError listing every violation."""
    if data is None:
        raise SchemaError("output is not parseable JSON")
    if not isinstance(data, dict):
        raise SchemaError(f"expected object, got {type(data).__name__}")
    errors, clean = [], {}
    for key in data:
        if key not in schema:
            errors.append(f"unexpected field '{key}'")
    for field, rule in schema.items():
        if field not in data:
            if rule.get("required"):
                errors.append(f"missing field '{field}'")
            continue
        v = data[field]
        if isinstance(v, bool) or not isinstance(v, rule["type"]):
            errors.append(f"'{field}' has type {type(v).__name__} ({v!r})")
            continue
        if v is None:
            clean[field] = None
            continue
        if "enum" in rule:
            match = next((e for e in rule["enum"] if fold(e) == fold(v)), None)
            if match is None:
                errors.append(f"'{field}' value {v!r} not in {rule['enum']}")
                continue
            v = match
        if "pattern" in rule and not re.fullmatch(rule["pattern"], str(v)):
            errors.append(f"'{field}' value {v!r} does not match {rule['pattern']}")
            continue
        if "min" in rule and v < rule["min"]:
            errors.append(f"'{field}' value {v} below {rule['min']}")
            continue
        if "max" in rule and v > rule["max"]:
            errors.append(f"'{field}' value {v} above {rule['max']}")
            continue
        clean[field] = v
    if errors:
        raise SchemaError("; ".join(errors))
    return clean


def describe(schema=TICKET_SCHEMA) -> str:
    """Schema as text for the prompt."""
    lines = []
    for field, rule in schema.items():
        nullable = type(None) in (rule["type"] if isinstance(rule["type"], tuple) else (rule["type"],))
        if "enum" in rule:
            kind = "one of " + " | ".join(rule["enum"])
        elif "pattern" in rule:
            kind = "string YYYY-MM"
        elif rule["type"] in ((int, float), (int, float, type(None))):
            kind = "number"
        else:
            kind = "string"
        if "min" in rule and "max" in rule:
            kind += f" between {rule['min']} and {rule['max']}"
        lines.append(f'  "{field}": {kind}{" or null" if nullable else ""}')
    return "{\n" + ",\n".join(lines) + "\n}"


def json_schema(schema=TICKET_SCHEMA) -> dict:
    """Same schema as JSON Schema, for constrained decoding (Ollama `format`)."""
    props = {}
    for field, rule in schema.items():
        types = rule["type"] if isinstance(rule["type"], tuple) else (rule["type"],)
        nullable = type(None) in types
        if "enum" in rule:
            p = {"enum": rule["enum"] + ([None] if nullable else [])}
        else:
            base = "string" if str in types else "number"
            p = {"type": [base, "null"] if nullable else base}
            if "pattern" in rule:
                p["pattern"] = rule["pattern"]
            if "min" in rule:
                p["minimum"] = rule["min"]
            if "max" in rule:
                p["maximum"] = rule["max"]
        props[field] = p
    return {"type": "object", "properties": props, "required": [f for f, r in schema.items() if r.get("required")],
            "additionalProperties": False}


def extract_json(text: str):
    """First JSON object in a model reply (handles code fences and prose around it). None if absent."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    cand = fenced.group(1).strip() if fenced else text.strip()
    start = cand.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(cand)):
        ch = cand[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cand[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def repair_prompt(raw: str, error: str, schema=TICKET_SCHEMA) -> str:
    return (
        "Your previous output failed schema validation.\n\n"
        f"Previous output:\n{raw}\n\n"
        f"Validation errors:\n{error}\n\n"
        f"Required schema:\n{describe(schema)}\n\n"
        "Return only the corrected JSON object. No explanation."
    )
