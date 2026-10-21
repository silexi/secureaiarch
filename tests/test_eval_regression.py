"""python3 -m unittest discover -s tests"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.patterns import eval_regression as E
from bench.patterns import structured_output as P1

TICKETS = {t["id"]: t for t in P1.load_tickets()}
BY_TEXT = {t["text"]: t for t in TICKETS.values()}


class Scripted:
    """Answers from the hand labels, with one known change per prompt:
    v2 lowers every high urgency to medium; v3 follows the instruction inside a ticket.
    With capital=True it writes enum values with a capital letter (the same answer, another spelling)."""

    def __init__(self, capital=False):
        self.capital = capital

    def chat(self, model, messages, temperature, fmt=None, num_predict=400, seed=None, tools=None, top_logprobs=0):
        user = messages[-1]["content"]
        text = user.split("<<<\n", 1)[1].split("\n>>>", 1)[0] if "<<<" in user else user.split("Ticket:\n", 1)[1]
        t = BY_TEXT[text]
        out = {f: t[f] for f in ("category", "urgency", "period", "amount")}
        out.update({"currency": t["currency"], "confidence": 0.9})
        if E.CAUTION in user and out["urgency"] == "high":
            out["urgency"] = "medium"
        if "<<<" not in user and t["note"] == E.INJECTION_NOTE:
            out["category"], out["urgency"] = "information", "low"
        if self.capital:
            out["category"], out["urgency"] = out["category"].title(), out["urgency"].title()
        return {"text": json.dumps(out), "tool_calls": [], "message": {}, "prompt_tokens": 1, "output_tokens": 1, "seconds": 0.01}


class Bench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = E.run(Scripted(), "fake", temperatures=(0.0,), repeats=2, progress=lambda m: None)
        cls.s = cls.res["summary"]["t=0.0"]

    def test_prompts_differ_only_where_intended(self):
        t = "x"
        v1, v2, v3 = (E.messages(c, t) for c in E.CONFIGS)
        self.assertEqual(v1, P1.messages(t))
        self.assertIn(E.CAUTION, v2[1]["content"])
        self.assertNotIn("data, not instructions", v3[0]["content"])
        self.assertNotIn("<<<", v3[1]["content"])

    def test_ground_truth(self):
        c = self.s["configs"]
        self.assertEqual(c["v1"]["accuracy_pct"], 100.0)
        self.assertLess(c["v2"]["accuracy_by_field_pct"]["urgency"], 100.0)
        self.assertEqual(c["v3"]["injection_followed_pct"], 100.0)
        self.assertEqual(c["v1"]["injection_followed_pct"], 0.0)

    def test_no_change_raises_no_alarm(self):
        self.assertEqual(self.s["comparisons"]["none"]["flagged_pct"], {d: 0.0 for d in E.DESIGNS})

    def test_prompt_edit_full_set_always_catches_small_set_sometimes(self):
        f = self.s["comparisons"]["prompt_edit"]["flagged_pct"]
        self.assertEqual(f["full"], 100.0)
        self.assertGreater(f["small_norm"], 0.0)
        self.assertLess(f["small_norm"], 100.0)

    def test_security_regression_is_invisible_to_small_ordinary_sets(self):
        f = self.s["comparisons"]["security"]["flagged_pct"]
        self.assertEqual(f["small_exact"], 0.0)
        self.assertEqual(f["small_norm"], 0.0)
        self.assertEqual(f["full_attack"], 100.0)

    def test_exact_comparison_fails_on_spelling(self):
        caps = E.run(Scripted(capital=True), "fake-caps", temperatures=(0.0,), repeats=2, progress=lambda m: None)
        swap = E.summarize_all([("fake-caps", caps["records"]), ("fake", self.res["records"])])
        (key, row), = swap.items()
        self.assertEqual(row["accuracy_delta_pts"], 0.0)
        self.assertEqual(row["flagged_pct"]["small_exact"], 100.0)
        self.assertEqual(row["flagged_pct"]["small_norm"], 0.0)
        self.assertEqual(row["flagged_pct"]["full"], 0.0)
        self.assertGreater(caps["summary"]["t=0.0"]["configs"]["v1"]["exact_compare_misses"], 0)

    def test_unparsable_output_counts_as_wrong(self):
        run = {"en-01": {"fields": None}}
        self.assertEqual(E.score(run, TICKETS, ["en-01"], E.FIELDS), 0.0)

    def test_amount_comparison(self):
        self.assertTrue(E.correct("amount", "412", 412))
        self.assertFalse(E.correct("amount", "412", 412, exact=True))
        self.assertTrue(E.correct("amount", None, None))
        self.assertFalse(E.correct("amount", 0, None))
