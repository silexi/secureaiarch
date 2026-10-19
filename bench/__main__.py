"""python3 -m bench run structured-output --models qwen2.5:1.5b,qwen2.5:3b,qwen3:30b-a3b

Writes results/<pattern>.json (summary, published on the site) and
results/raw/<pattern>/<model>.jsonl (every request and reply, for audit).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import env
from .ollama import Client
from .patterns import PATTERNS

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(prog="bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("pattern", choices=sorted(PATTERNS))
    r.add_argument("--models", required=True, help="comma separated Ollama model names")
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--temperatures", default="0.0,0.7")
    r.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()

    client = Client()
    version = client.version()
    if not version:
        print("Ollama is not reachable (OLLAMA_HOST). Start it with `ollama serve`.", file=sys.stderr)
        return 1
    mod = PATTERNS[args.pattern]
    temps = tuple(float(t) for t in args.temperatures.split(","))
    out = Path(args.out)
    (out / "raw" / args.pattern).mkdir(parents=True, exist_ok=True)

    result = {
        "pattern": args.pattern,
        "generated": env.now(),
        "git_sha": env.git_sha(),
        "machine": env.label(),
        "hardware": env.hardware(),
        "ollama_version": version,
        "config": {"repeats": args.repeats, "temperatures": list(temps)},
        "models": [],
    }
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"{model}: running", file=sys.stderr)
        res = mod.run(client, model, temperatures=temps, repeats=args.repeats,
                      progress=lambda m: print(m, file=sys.stderr))
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)
        with open(out / "raw" / args.pattern / f"{safe}.jsonl", "w", encoding="utf-8") as f:
            for rec in res["records"]:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        result["models"].append({"model": model, "info": client.model_info(model),
                                 "summary": res["summary"], "examples": res["examples"]})
    (out / f"{args.pattern}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out / (args.pattern + '.json')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
