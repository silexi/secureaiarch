"""python3 -m unittest discover -s tests"""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.patterns import permission_filter as P


def bag(text):
    """Deterministic stand-in for an embedding: hashed bag of words."""
    v = [0.0] * 64
    for w in text.lower().replace("?", " ").replace(",", " ").split():
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1.0
    return v


class FakeClient:
    """Echoes the first context passage, the way a model that ignores instructions would."""
    def embed(self, model, inputs):
        return [bag(t) for t in inputs]

    def chat(self, model, messages, temperature, fmt=None, num_predict=400, seed=None):
        ctx = messages[-1]["content"].split("CONTEXT:\n", 1)[1].split("\n\nQUESTION:", 1)[0]
        first = ctx.splitlines()[0] if ctx.strip() else "NOT_FOUND"
        return {"text": first, "prompt_tokens": 1, "output_tokens": 1, "seconds": 0.01}


class Data(unittest.TestCase):
    def test_corpus_shape(self):
        chunks, questions, canaries = P.load()
        self.assertEqual(len(questions), 24)
        self.assertEqual(sum(q["kind"] == "restricted" for q in questions), 12)
        for c in chunks:  # canaries never appear in chunks the user may see
            if c["clearance"] in P.ALLOWED:
                for cs in canaries.values():
                    self.assertFalse(any(x.lower() in c["text"].lower() for x in cs), c["id"])
        for d in {c["doc"] for c in chunks if c["clearance"] == "confidential"}:
            self.assertTrue(any(c["canaries"] for c in chunks if c["doc"] == d), d)
        for q in questions:
            if q["kind"] == "allowed":  # every allowed question is answerable from allowed chunks
                self.assertTrue(any(P.correct(c["text"], q["expect"]) for c in chunks if c["lang"] == q["lang"] and c["clearance"] in P.ALLOWED), q["id"])


class Arms(unittest.TestCase):
    def setUp(self):
        P._vec_cache.clear()
        self.res = P.run(FakeClient(), "fake", temperatures=(0.0,), repeats=1, progress=lambda m: None)

    def test_pre_and_post_never_expose(self):
        s = self.res["summary"]
        for arm in ("pre", "post"):
            self.assertEqual(s[f"{arm}@0.0"]["confidential_in_context_pct"], 0.0)
            self.assertEqual(s[f"{arm}@0.0"]["leak_pct"], 0.0)
        self.assertGreater(s["none@0.0"]["confidential_in_context_pct"], 0)

    def test_prompt_arm_has_same_context_as_none(self):
        recs = self.res["records"]
        none = {r["question"]: r["context"] for r in recs if r["arm"] == "none"}
        prompt = {r["question"]: r["context"] for r in recs if r["arm"] == "prompt"}
        self.assertEqual(none, prompt)

    def test_pre_fills_k_post_may_not(self):
        r = self.res["retrieval"]
        self.assertEqual(r["pre"]["chunks_in_context_mean"], P.K)
        self.assertLessEqual(r["post"]["chunks_in_context_mean"], P.K)
        self.assertEqual(r["post"]["confidential_in_context_pct"], 0.0)

    def test_leak_detection(self):
        self.assertEqual(P.leaked("The multiplier is 1.37.", ["1.37", "Halvorsen"]), ["1.37"])
        self.assertEqual(P.leaked("NOT_FOUND", ["1.37"]), [])


if __name__ == "__main__":
    unittest.main()
