"""python3 -m unittest tests.test_prohibition"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.patterns import prohibition as P
from bench.patterns import tool_boundary as T


def lp(tokens):
    """Logprobs in Ollama's shape: (token, [(alternative, probability), ...])."""
    return [{"token": t, "logprob": math.log(dict(alts)[t]) if alts else 0.0,
             "top_logprobs": [{"token": a, "logprob": math.log(p)} for a, p in alts]} for t, alts in tokens]


JSON_STYLE = lp([("<tool_call>", [("<tool_call>", 0.9), ("The", 0.1)]), ("\n", []), ('{"', []), ("name", []), ('":', []), (' "', []),
                 ("get", [("get", 0.97), ("delete", 0.02), ("update", 0.01)]), ("_customer", [])])
XML_STYLE = lp([("<tool_call>", [("<tool_call>", 0.8)]), ("\n", []), ("<", []), ("function", []),
                ("=get", [("=get", 0.95), ("=", 0.04), ("=read", 0.01)]), ("_customer", [])])


class Fake:
    """Deletes in 'adjacent' scenarios only when the prompt names deletion, otherwise reads the record."""

    def capabilities(self, model):
        return ["completion", "tools"]

    def chat(self, model, messages, temperature, fmt=None, num_predict=400, seed=None, tools=None, top_logprobs=0):
        system, user = messages[0]["content"], messages[1]["content"]
        cid = "C-2001" if "C-2001" in user else "M-2001"
        if any(m["role"] == "tool" for m in messages):
            return {"text": "done", "tool_calls": [], "message": {}, "seconds": 0.01, "logprobs": []}
        named = "delete" in system.lower() or "silme" in system.lower()
        adjacent = any(w in user for w in ("Clean up", "temizle"))
        name = "delete_customer" if named and adjacent else "get_customer"
        return {"text": "", "tool_calls": [{"name": name, "arguments": {"customer_id": cid}}],
                "message": {"tool_calls": [{"function": {"name": name, "arguments": {"customer_id": cid}}}]},
                "seconds": 0.01, "logprobs": JSON_STYLE if top_logprobs else []}


class Prohibition(unittest.TestCase):
    def test_prompts_match_tool_boundary(self):
        for lang in ("en", "tr"):
            self.assertEqual(P.SYSTEM["never"][lang], T.SYSTEM[lang])
            self.assertEqual(P.SYSTEM["none"][lang], T.SYSTEM_NORULE[lang])

    def test_arms_differ_in_one_sentence_only(self):
        for lang in ("en", "tr"):
            for arm in P.ARMS:
                s = P.SYSTEM[arm][lang]
                self.assertTrue(s.startswith(P._HEAD[lang]) and s.endswith(P._TAIL[lang]), arm)
            self.assertNotIn("delet", P.SYSTEM["positive"]["en"].lower())
            self.assertNotIn("sil", P.SYSTEM["positive"]["tr"].lower())

    def test_scenarios_never_request_the_actions(self):
        _, scenarios = P.load()
        self.assertEqual(len(scenarios), 12)
        for s in scenarios:
            low = s["user"].lower()
            self.assertNotIn("delet", low)
            self.assertNotIn(" sil", low)
            self.assertNotIn("billing", low)
            self.assertNotIn("fatura", low)

    def test_name_position_json_and_xml(self):
        d = P.first_decision(JSON_STYLE)
        self.assertAlmostEqual(d["p_tool_call"], 0.9, places=5)
        self.assertTrue(d["delete_in_top"])
        self.assertAlmostEqual(d["p_delete"], 0.02, places=6)
        x = P.first_decision(XML_STYLE)
        self.assertTrue(x["name_found"])
        self.assertFalse(x["delete_in_top"])
        self.assertAlmostEqual(x["bound"], 0.01, places=6)
        self.assertAlmostEqual(x["mass"]["open"], 0.04, places=6)
        self.assertAlmostEqual(x["mass"]["other"], 0.01, places=6)
        self.assertAlmostEqual(x["unresolved"], 0.04, places=6)

    def test_open_branch_is_split_by_the_next_token(self):
        greedy_open = lp([("<tool_call>", [("<tool_call>", 0.9)]), ("\n", []), ("<", []), ("function", []),
                          ("=", [("=", 0.7), ("=get", 0.3)]), ("delete", [("delete", 0.6), ("get", 0.4)]), ("_customer", [])])
        d = P.first_decision(greedy_open)
        self.assertAlmostEqual(d["p_delete"], 0.42, places=6)
        self.assertEqual(d["chosen"], "=delete")
        self.assertTrue(d["delete_in_top"])
        self.assertAlmostEqual(d["unresolved"], 0.0, places=6)

    def test_counts_and_comparison(self):
        res = P.run(Fake(), "fake", temperatures=(1.0,), repeats=2, progress=lambda m: None)
        s = res["summary"]
        self.assertEqual(s["counts"]["never/adjacent@1.0"]["forbidden"], 4)   # EN and TR "closed", 2 repeats
        self.assertEqual(s["counts"]["none/adjacent@1.0"]["forbidden"], 0)
        self.assertEqual(s["counts"]["positive/adjacent@1.0"]["forbidden"], 0)
        self.assertEqual(s["counts"]["never/unrelated@1.0"]["forbidden"], 0)
        self.assertEqual(s["never_vs_none"]["adjacent@1.0"]["never"], "4/12")
        self.assertEqual(s["probability"]["none/unrelated"]["name_found"], 6)

    def test_fisher(self):
        self.assertEqual(P.fisher_two_sided(3, 1, 1, 3), 0.4857)
        self.assertEqual(P.fisher_two_sided(0, 10, 0, 10), 1.0)


if __name__ == "__main__":
    unittest.main()
