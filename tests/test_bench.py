"""python3 -m unittest discover -s tests"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench import schema as S
from bench.patterns import structured_output as P

GOOD = {"category": "billing_dispute", "period": "2026-08", "amount": 412, "currency": "USD", "urgency": "high", "confidence": 0.9}


class Schema(unittest.TestCase):
    def test_valid_and_canonical(self):
        d = dict(GOOD, urgency="HIGH")
        self.assertEqual(S.validate(d)["urgency"], "high")

    def test_turkish_fold(self):
        self.assertEqual(S.fold("YÜKSEK"), "yuksek")

    def test_every_violation_reported(self):
        bad = {"category": "fatura", "period": "Agustos 2026", "amount": "12.400 TL", "urgency": "cok_acil", "confidence": 1.4, "extra": 1}
        with self.assertRaises(S.SchemaError) as e:
            S.validate(bad)
        msg = str(e.exception)
        for part in ["category", "period", "amount", "urgency", "confidence", "currency", "extra"]:
            self.assertIn(part, msg)

    def test_bool_is_not_number(self):
        with self.assertRaises(S.SchemaError):
            S.validate(dict(GOOD, confidence=True))

    def test_extract_json(self):
        self.assertEqual(S.extract_json('Sure:\n```json\n{"a": "}"}\n```'), {"a": "}"})
        self.assertIsNone(S.extract_json("no json here"))
        self.assertIsNone(S.extract_json('{"a": 1'))

    def test_json_schema_shape(self):
        js = S.json_schema()
        self.assertFalse(js["additionalProperties"])
        self.assertIn(None, js["properties"]["currency"]["enum"])
        self.assertEqual(js["properties"]["amount"]["type"], ["number", "null"])


class FakeClient:
    """Fails schema on first prompt-arm reply for billing tickets, then repairs; constrained always valid."""
    def __init__(self):
        self.tickets = {t["text"]: t for t in P.load_tickets()}

    def chat(self, model, messages, temperature, fmt=None, num_predict=400, seed=None):
        last = messages[-1]["content"]
        if "about the weather" in last:  # constrained-decoding probe: honour the schema
            text = json.dumps(self._answer(next(iter(self.tickets.values())))) if fmt else "It is sunny."
            return {"text": text, "prompt_tokens": 1, "output_tokens": 1, "seconds": 0.1}
        if "failed schema validation" in last:
            t = self.cur
            text = json.dumps(self._answer(t))
        else:
            t = next(v for k, v in self.tickets.items() if k in last)
            self.cur = t
            ans = self._answer(t)
            if fmt is None and t["category"] == "billing_dispute":
                ans["urgency"] = "çok acil"
                text = "Here you go:\n```json\n" + json.dumps(ans, ensure_ascii=False) + "\n```"
            else:
                text = json.dumps(ans)
        return {"text": text, "prompt_tokens": 100, "output_tokens": 40, "seconds": 0.5}

    @staticmethod
    def _answer(t):
        return {"category": t["category"], "period": t["period"], "amount": t["amount"], "currency": t["currency"],
                "urgency": t["urgency"], "confidence": 0.8}


class Experiment(unittest.TestCase):
    def test_run_and_summary(self):
        res = P.run(FakeClient(), "fake", temperatures=(0.0,), repeats=1, progress=lambda m: None)
        s = res["summary"]
        self.assertEqual(s["prompt@0.0"]["n"], 24)
        self.assertEqual(s["prompt@0.0"]["valid_pct"], round(100 * 16 / 24, 1))
        self.assertEqual(s["prompt@0.0"]["repair"]["fixed"], 8)
        self.assertEqual(s["prompt@0.0"]["repair"]["valid_after_repair_pct"], 100.0)
        self.assertEqual(s["prompt@0.0"]["silently_invalid_pct"], round(100 * 8 / 24, 1))
        self.assertEqual(s["constrained@0.0"]["valid_pct"], 100.0)
        self.assertEqual(s["constrained@0.0"]["accuracy_pct"]["category"], 100.0)
        self.assertEqual(s["constrained@0.0"]["injection_followed_pct"], 0.0)
        self.assertEqual(len(res["examples"]), 1)
        self.assertIn("urgency", res["examples"][0]["error"])

    def test_constrained_crash_disables_arm(self):
        class Crashing(FakeClient):
            def chat(self, model, messages, temperature, fmt=None, num_predict=400, seed=None):
                if fmt is not None:
                    raise RuntimeError("HTTP Error 500")
                return super().chat(model, messages, temperature, fmt, num_predict, seed)
        res = P.run(Crashing(), "fake", temperatures=(0.0,), repeats=1, progress=lambda m: None)
        self.assertIn("request failed", res["constrained_error"])
        self.assertNotIn("constrained@0.0", res["summary"])
        self.assertEqual(res["summary"]["prompt@0.0"]["n"], 24)

    def test_ignored_schema_disables_arm(self):
        class Ignoring(FakeClient):
            def chat(self, model, messages, temperature, fmt=None, num_predict=400, seed=None):
                if "about the weather" in messages[-1]["content"]:
                    return {"text": "It is sunny.", "prompt_tokens": 1, "output_tokens": 1, "seconds": 0.1}
                return super().chat(model, messages, temperature, fmt, num_predict, seed)
        res = P.run(Ignoring(), "fake", temperatures=(0.0,), repeats=1, progress=lambda m: None)
        self.assertIn("schema ignored", res["constrained_error"])
        self.assertNotIn("constrained@0.0", res["summary"])

    def test_dataset_labels_are_schema_valid(self):
        for t in P.load_tickets():
            S.validate({"category": t["category"], "period": t["period"], "amount": t["amount"],
                        "currency": t["currency"], "urgency": t["urgency"], "confidence": 1})


if __name__ == "__main__":
    unittest.main()
