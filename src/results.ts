// results/*.json are written by `python3 -m bench run <pattern>` on local hardware.
const files = import.meta.glob("../results/*.json", { eager: true, import: "default" }) as Record<string, any>;

export function resultsFor(pattern: string): any | null {
  const key = Object.keys(files).find((k) => k.endsWith(`/${pattern}.json`));
  const r = key ? files[key] : null;
  return r && Array.isArray(r.models) && r.models.length ? r : null;
}
